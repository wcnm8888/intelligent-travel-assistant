"""Lifecycle and transaction primitives for the local SQLite adapter."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class SqliteConnectionConfig:
    """Validated connection settings owned by the persistence adapter."""

    path: str | Path
    busy_timeout_ms: int = 5000
    timeout_seconds: float = 5.0

    def __post_init__(self) -> None:
        if not isinstance(self.path, (str, Path)) or not str(self.path):
            raise ValueError("sqlite_path_invalid")
        if type(self.busy_timeout_ms) is not int or self.busy_timeout_ms < 0:
            raise ValueError("sqlite_busy_timeout_invalid")
        if type(self.timeout_seconds) is not float or self.timeout_seconds <= 0:
            raise ValueError("sqlite_timeout_invalid")


class SqliteDatabase:
    """Explicitly opened and closed SQLite connection lifecycle."""

    def __init__(self, config: SqliteConnectionConfig) -> None:
        self._config = config
        self._connection: sqlite3.Connection | None = None

    @property
    def connection(self) -> sqlite3.Connection:
        if self._connection is None:
            raise RuntimeError("sqlite_database_not_open")
        return self._connection

    def open(self) -> sqlite3.Connection:
        if self._connection is not None:
            raise RuntimeError("sqlite_database_already_open")

        connection = sqlite3.connect(
            self._config.path,
            timeout=self._config.timeout_seconds,
            isolation_level=None,
            check_same_thread=True,
        )
        connection.row_factory = sqlite3.Row
        try:
            configure_sqlite_connection(
                connection,
                busy_timeout_ms=self._config.busy_timeout_ms,
            )
        except BaseException:
            connection.close()
            raise
        self._connection = connection
        return connection

    def close(self) -> None:
        connection = self._connection
        self._connection = None
        if connection is None:
            return
        if connection.in_transaction:
            connection.rollback()
        connection.close()

    def __enter__(self) -> sqlite3.Connection:
        return self.open()

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        self.close()


def configure_sqlite_connection(
    connection: sqlite3.Connection,
    *,
    busy_timeout_ms: int = 5000,
) -> None:
    """Apply the F-002 connection contract to an opened connection."""

    if type(busy_timeout_ms) is not int or busy_timeout_ms < 0:
        raise ValueError("sqlite_busy_timeout_invalid")
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute(f"PRAGMA busy_timeout = {busy_timeout_ms}")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA synchronous = FULL")


@contextmanager
def sqlite_transaction(
    connection: sqlite3.Connection,
    *,
    immediate: bool = True,
) -> Iterator[sqlite3.Connection]:
    """Run one explicit transaction and roll it back on every failure."""

    if connection.in_transaction:
        raise RuntimeError("sqlite_transaction_already_open")
    connection.execute("BEGIN IMMEDIATE" if immediate else "BEGIN")
    try:
        yield connection
    except BaseException:
        if connection.in_transaction:
            connection.rollback()
        raise
    else:
        connection.commit()
