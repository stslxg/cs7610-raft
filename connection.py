#!/usr/bin/env python3

import asyncio
import socket
import pickle

from config import Config

__all__ = ["ServerConnection", "ClientConnection"]

class Resolver:
    """
    For resolving host names to IP addresses, and getting my address and id
    """
    __slots__ = ["_my_id", "_my_address", "_host_addresses"]

    def __init__(self, host_names):
        self._my_id = None
        my_name = socket.gethostname()
        self._my_address = socket.gethostbyname(my_name)
        self._host_addresses = list(map(socket.gethostbyname, host_names))
    
    @property
    def my_id(self):
        if not self._my_id:
            self._my_id = self._host_addresses.index(self._my_address)
        return self._my_id

    @property
    def host_addresses(self):
        return self._host_addresses

    @property
    def my_address(self):
        return self._my_address

class Connection:
    """
    ContextManager class for asynchronous connectless UDP "connection"
    Inspired by aio_echo.py of bashkirtsevich:
    (https://gist.github.com/bashkirtsevich/1659c18ac6d05d688426e5f150c9f6fc)
    """
    __slots__ = ["_socket", "_resolver", "_host_addresses", "_port", "_loop", "_fd"]

    def __init__(self, host_names, port):
        self._socket = None
        self._resolver = Resolver(host_names)
        self._host_addresses = self._resolver.host_addresses
        self._port = port
        self._loop = asyncio.get_event_loop()
        self._fd = None

    def __enter__(self):
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._socket.setblocking(False)
        self._socket.bind((self._resolver.my_address, self._port))
        print ("binding to", self._resolver.my_address, self._port)
        self._fd = self._socket.fileno()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._socket.close()

    # the following two functions will return future
    def receive_data(self, fut=None, registed=False):
        if fut is None:
            fut = self._loop.create_future()
        if registed:
            self._loop.remove_reader(self._fd)
        
        try:
            data, _ = self._socket.recvfrom(Config.BUF_SIZE)
        except (BlockingIOError, InterruptedError):
            self._loop.add_reader(self._fd, Connection.receive_data, self, fut, True)
        else:
            print("R:", data)
            fut.set_result(data)
        return fut

    def send_data(self, data, id, fut=None, registed=False):
        if fut is None:
            fut = self._loop.create_future()
        if registed:
            self._loop.remove_writer(self._fd)
        
        try:
            send_len = self._socket.sendto(data, (self._host_addresses[id], self._port))
        except (BlockingIOError, InterruptedError):
            self._loop.add_writer(self._fd, Connection.send_data, self, data, id, fut, True)
        else:
            print("S:", data, "to", self._host_addresses[id], self._port)
            fut.set_result(send_len)
        return fut

class ClientConnection:
    """
    ContextManager class for connections used by Client
    """
    __slots__ = ["_client_to_server_conn", "_client_resolver"]

    def __init__(self, config=Config):
        self._client_to_server_conn = Connection(config.SERVER_NAMES, config.CLIENT_PORT)
        print(self._client_to_server_conn._host_addresses)
        self._client_resolver = Resolver(config.CLIENT_NAMES)
    
    @property
    def client_id(self):
        return self._client_resolver.my_id

    def __enter__(self):
        self._client_to_server_conn.__enter__()
        return self
    
    def __exit__(self, exc_type, exc_value, traceback):
        self._client_to_server_conn.__exit__(exc_type, exc_value, traceback)
    
    async def receive_message_from_server(self):
        data = await self._client_to_server_conn.receive_data()
        return pickle.loads(data)

    def send_message_to_server(self, msg, server_id):
        data = pickle.dumps(msg)
        return self._client_to_server_conn.send_data(data, server_id)

class ServerConnection:
    """
    ContextManager class for connections used by Server
    """
    __slots__ = ["_server_to_server_conn", "_server_to_client_conn", "_server_resolver"]

    def __init__(self, config=Config):
        self._server_to_server_conn = Connection(config.SERVER_NAMES, config.SERVER_PORT)
        self._server_to_client_conn = Connection(config.CLIENT_NAMES, config.CLIENT_PORT)
        print(self._server_to_client_conn._host_addresses)
        self._server_resolver = Resolver(config.SERVER_NAMES)

    @property
    def server_id(self):
        return self._server_resolver.my_id

    def __enter__(self):
        self._server_to_server_conn.__enter__()
        self._server_to_client_conn.__enter__()
        return self
    
    def __exit__(self, exc_type, exc_value, traceback):
        self._server_to_server_conn.__exit__(exc_type, exc_value, traceback)
        self._server_to_client_conn.__exit__(exc_type, exc_value, traceback)

    async def receive_message_from_server(self):
        data = await self._server_to_server_conn.receive_data()
        return pickle.loads(data)

    async def receive_message_from_client(self):
        data = await self._server_to_client_conn.receive_data()
        return pickle.loads(data)

    def send_message_to_server(self, msg, server_id):
        data = pickle.dumps(msg)
        return self._server_to_server_conn.send_data(data, server_id)
    
    def send_message_to_client(self, msg, client_id):
        data = pickle.dumps(msg)
        return self._server_to_client_conn.send_data(data, client_id)

if __name__ == "__main__":
    # test
    with Connection(Config.SERVER_NAMES, Config.SERVER_PORT) as conn:
        pass
    with ServerConnection() as conn:
        pass
    with ClientConnection() as conn:
        pass