#!/usr/bin/env python3

import json
import time
import threading
import queue
import asyncio
from config import Config
from connection import ClientConnection
from messages import *

class Client:
    def __init__(self):
        self.leader = 0
        self.msgId = 0
        self.sendQ = queue.Queue()
        self.recQ = queue.Queue()
        self._conn = ClientConnection()
        self._loop = asyncio.get_event_loop()
        self._id = self._conn.client_id
    
    def find_leader(self):
        return self.leader

    def put(self, key, value):
        # push put message onto sendQ
        return None

    def get (self, key):
        # push get message onto sendQ
        return None

    def sendInstruction(self):
        # should be threaded to run continuously
        """  
        while true
            if sendQ is not empty
                pop sendQ
                sendSuccess = false
                while (not sendSuccess)
                    set ID of message to send (using msgID)
                    send instruction to self.leader
                    time.sleep(3): sleep for 3 seconds
                    pop all elements of recQ with lower msgID: these are ignored
                    if...
                        recQ is empty, i.e. response timed out
                            increment leader index 
                            increment msgId 
                        response is false
                            update leader index to sent index
                            increment msgId
                        response is success
                            sendSuccess = true
        """
        return None

    def receiveInstruction(self):
        # should be threaded
        # push message onto recQ
        return None

    def test_handler(self, msg):
        print(self._id, ':', msg)

    async def client_testing(self):
        print("I'm Client", self._id)
        msg = Test(self._id)
        while True:
            await asyncio.gather(*(self._conn.send_message_to_server(msg, id)
                for id in range(len(Config.SERVER_NAMES))))
            print("sent")
            await asyncio.sleep(1)
            # msg = await self._conn.receive_message_from_server()
            # msg.handle(self)

    def run(self):
        print(self._loop)
        with self._conn:
            self._loop.run_until_complete(Client.client_testing(self))


if __name__ == "__main__":
    client = Client()
    client.run()