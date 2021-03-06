#!/usr/bin/env python3

from typing import List, Optional, TYPE_CHECKING
if TYPE_CHECKING:
    from server import Server

__all__ = ["LogItem", "GetOp", "PutOp", "NoOp", "ConfigOp"]

class LogItem:
    __slots__ = ["term", "command"]
    def __init__(self, term: int, command: str) -> None:
        self.term = term
        self.command = command

class GetOp(LogItem):
    __slots__ = ["key"]
    def __init__(self, term: int, key: str) -> None:
        super().__init__(term, "get")
        self.key = key
    def handle(self, server: "Server") -> Optional[int]:
        try:
            return server.stateMachine[self.key]
        except KeyError:
            return None
    def __str__(self) -> str:
        return "({}?,{})".format(self.key, self.term)

class PutOp(LogItem):
    __slots__ = ["key", "value"]
    def __init__(self, term: int, key: str, value: int) -> None:
        super().__init__(term, "put")
        self.key = key
        self.value = value
    def handle(self, server: "Server") -> None:
        server.stateMachine[self.key] = self.value
    def __str__(self) -> str:
        return "({}<-{},{})".format(self.key, self.value, self.term)

class NoOp(LogItem):
    def __init__(self, term: int) -> None:
        super().__init__(term, "no-op")
    def handle(self, server: "Server") -> None:
        pass
    def __str__(self) -> str:
        return "(nop,{})".format(self.term)

class ConfigOp(LogItem):
    def __init__(self, term: int, config: List[int], new_config: Optional[List[int]]=None) -> None:
        super().__init__(term, "config")
        self.config = config
        self.new_config = new_config
    def handle(self, server: "Server") -> None:
        pass
    def __str__(self) -> str:
        if self.new_config is None:
            return "({}, {})".format(self.config, self.term)
        else:
            return "({};{}, {})".format(self.config, self.new_config, self.term)
