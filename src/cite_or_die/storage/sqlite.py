import sqlite3
from abc import ABC, abstractmethod
from pathlib import Path


class SqliteStore(ABC):
    def __init__(self, sqlite_path: Path) -> None:
        self.sqlite_path = sqlite_path
        self.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.sqlite_path)
        connection.row_factory = sqlite3.Row
        return connection

    @abstractmethod
    def _init(self) -> None:
        raise NotImplementedError
