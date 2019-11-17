#!/usr/bin/env python3

import asyncio
import pickle
import enum
import random
from contextlib import suppress

from config import Config
from connection import ServerConnection
from messages import *

class Storage:
    __slots__ = ["_id"]

    def read(self, id):
        self._id = id
        try:
            with open("server"+str(id)+".storage", "rb") as f:
                currentTerm = pickle.load(f)
                votedFor = pickle.load(f)
                log = pickle.load(f)
        except OSError:
            currentTerm = 0
            votedFor = 0
            log = [{"term": 0}]
        return (currentTerm, votedFor, log)

    def store(self, currentTerm, votedFor, log):
        with open("server"+str(self._id)+".storage", "wb") as f:
            pickle.dump(currentTerm, f)
            pickle.dump(votedFor, f)
            pickle.dump(log, f)

class State(enum.Enum):
    follower = "Follower"
    candidate = "Candidate"
    leader = "Leader"

class Server:
    __slots__ = ["_conn", "_id", "_server_num", "_loop", "_storage", "_voted_for_me", "_msg_resend_timer", "_election_timer",
        "currentTerm", "votedFor", "log", "commitIndex", "lastApplied", "nextIndex", "matchIndex", "state"]

    def __init__(self, config=Config, storage=Storage()):
        self._conn = ServerConnection(config)
        self._id = self._conn.server_id
        self._server_num = len(config.SERVER_NAMES)
        self._loop = asyncio.get_event_loop()
        self._storage = storage
        self._voted_for_me = set()
        self._msg_resend_timer = {}
        self._election_timer = None

    async def init(self):
        self.currentTerm, self.votedFor, self.log = self._storage.read(self._id)
        self.commitIndex = 0
        self.lastApplied = 0
        self.nextIndex = [len(self.log) for i in range(self._server_num)]
        self.matchIndex = [0 for i in range(self._server_num)]
        if self.currentTerm == 0 and self._id == 0:
            await self.enter_leader_state()
        else:
            self.enter_follower_state()

    async def test_handler(self, msg):
        print(self._id, ':', msg)

    async def request_vote_handler(self, msg):
        print("Received RequestVote from Server {} for term {} with ({},{})".format(msg.candidateId, msg.term, msg.lastLogTerm, msg.lastLogIndex))
        voteGranted = False
        if msg.term >= self.currentTerm:
            if self.votedFor is None or self.votedFor == msg.candidateId:
                if msg.lastLogTerm > self.log[-1]['term'] or ( msg.lastLogTerm == self.log[-1]['term'] and msg.lastLogIndex >= len(self.log)-1):
                    voteGranted = True
                    self.currentTerm = msg.term
                    self.votedFor = msg.candidateId
                    self.reset_election_timer()
        self._storage.store(self.currentTerm, self.votedFor, self.log) # persistent storage before responding
        reply_msg = RequestVoteReply(msg.messageId, self.currentTerm, voteGranted, self._id)
        await self._conn.send_message_to_server(reply_msg, msg.candidateId)

    async def request_vote_reply_handler(self, msg):
        if self.state == State.candidate and msg.messageId in self._msg_resend_timer:
            #cancel the resender
            self._msg_resend_timer[msg.messageId].cancel()
            print("Received RequestVoteReply from Server {}, {} granted".format(msg.senderId, "" if msg.voteGranted else "not"))
            if msg.voteGranted:
                self._voted_for_me.add(msg.senderId)
                if len(self._voted_for_me) + 1 > self._server_num // 2:
                    await self.enter_leader_state()

    async def append_entry_handler(self, msg):
        if self.state == State.candidate:
            self.votedFor = msg.leaderId
            self.enter_follower_state()
        if self.state != State.leader:
            if msg.entry is None: #heartbeat
                self.reset_election_timer()
                print("Received heartbeat from Server {}".format(msg.leaderId))

    async def append_entry_reply_handler(self, msg):
        pass

    async def get_handler(self, msg):
        pass

    async def put_handler(self, msg):
        pass


    def exit_current_state(self):
        # cancel all the resend timers when exit
        for t in self._msg_resend_timer.values():
            t.cancel()
        self._msg_resend_timer = {}

    def enter_follower_state(self):
        self.exit_current_state()
        self.state = State.follower
        self.reset_election_timer()
        print("Server {}: follower of term {}".format(self._id, self.currentTerm))

    async def msg_sender(self, msg, id, count=0, timeout=Config.RESEND_TIMEOUT, try_limit=Config.TRY_LIMIT):
        try:
            if count > 0:
                await asyncio.sleep(timeout)
            await self._conn.send_message_to_server(msg, id)
            if count != try_limit: # ulimited retry if try_limit == -1
                self._msg_resend_timer[msg.messageId] = self._loop.create_task(self.msg_sender(msg, id, count+1, timeout, try_limit))
        except asyncio.CancelledError:
            pass

    async def enter_candidate_state(self):
        self.exit_current_state()
        self.state = State.candidate
        self._voted_for_me = set()
        self.currentTerm += 1
        self.votedFor = self._id
        self.reset_election_timer(True)
        print("Server {}: starting election for term {}".format(self._id, self.currentTerm))

        for id in range(self._server_num):
            if id != self._id:
                msg = RequestVote(self.currentTerm, self._id, len(self.log)-1, self.log[-1]["term"])
                await self.msg_sender(msg, id)

    async def enter_leader_state(self):
        self.exit_current_state()
        self.state = State.leader
        self.cancel_election_timer()
        self.nextIndex = [len(self.log) for i in range(self._server_num)]
        self.matchIndex = [0 for i in range(self._server_num)]
        print("Server {}: leader of term {}".format(self._id, self.currentTerm))

        for id in range(self._server_num):
            if id != self._id:
                msg = AppendEntry(self.currentTerm, self._id, 0, 0, None, 0) #heartbeat
                await self.msg_sender(msg, id, timeout=Config.HEARTBEAT_TIMEOUT, try_limit=-1)

    async def election_timout(self):
        try:
            timeout = random.uniform(Config.ELECTION_TIMEOUT, 2 * Config.ELECTION_TIMEOUT)
            await asyncio.sleep(timeout)
            await self.enter_candidate_state()
        except asyncio.CancelledError:
            pass

    def cancel_election_timer(self, timeouted=False):
        if self._election_timer is not None and not timeouted:
            self._election_timer.cancel()

    def reset_election_timer(self, timeouted=False):
        self.cancel_election_timer(timeouted)
        self._election_timer = self._loop.create_task(self.election_timout())

    async def server_handler(self):
        while True:
            msg = await self._conn.receive_message_from_server()
            # update term immediately
            if msg.term > self.currentTerm:
                self.currentTerm = msg.term
                self.votedFor = None
                self.enter_follower_state()
            await msg.handle(self)

    async def client_handler(self):
        while True:
            msg = await self._conn.receive_message_from_client()
            await msg.handle(self)

    def run(self):
        try:
            with self._conn:
                self._loop.create_task(Server.init(self))
                self._loop.create_task(Server.server_handler(self))
                self._loop.create_task(Server.client_handler(self))
                self._loop.run_forever()
        except (KeyboardInterrupt, SystemExit):
            #self._storage.store(self.currentTerm, self.votedFor, self.log)
            print()
            print("Server", self._id, "crashes")
        finally:
            pending = [t for t in asyncio.Task.all_tasks()]
            for t in pending:
                t.cancel()
                with suppress(asyncio.CancelledError):
                    self._loop.run_until_complete(t)
            self._loop.close()

if __name__ == "__main__":
    server = Server()
    server.run()