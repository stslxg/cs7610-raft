#!/usr/bin/env python3

import asyncio
from config import Config
from connection import ServerConnection
from messages import *

class Server:
    __slots__ = ["_conn", "_id", "_server_num", "_loop"]

    def __init__(self, config=Config):
        self._conn = ServerConnection(config)
        self._id = self._conn.server_id
        self._server_num = len(config.SERVER_NAMES)
        self._loop = asyncio.get_event_loop()

    def test_handler(self, msg):
        print(self._id, ':', msg)

    async def server_handler(self):
        print("I'm Server", self._id)
        msg = Test(self._id)
        while True:
            await asyncio.gather(*(self._conn.send_message_to_server(msg, id)
                for id in range(self._server_num) if id != self._id))
            await asyncio.sleep(1)
            msg = await self._conn.receive_message_from_server()
            msg.handle(self)
            msg = Test(self._id)
        while True:
            await asyncio.sleep(5)
            print('aaaaaaa')

    async def client_handler(self):
        while True:
            print("b")
            #msg = await self._conn.receive_message_from_client()
            print('....................')
            #msg.handle(self)
            print('....................')
            #msg = Test(self._id)
            #await self._conn.send_message_to_client(msg, 0)

    def run(self):
        with self._conn:
            self._loop.run_until_complete(asyncio.gather(Server.server_handler(self), Server.client_handler(self)))

if __name__ == "__main__":
    server = Server()
    server.run()