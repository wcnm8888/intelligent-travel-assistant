"""Offline tests for the F-002 SQLite connection boundary."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from intelligent_travel_assistant.adapters.persistence import (
    SqliteConnectionConfig,
    SqliteDatabase,
    sqlite_transaction,
)


def _database(path: Path) -> SqliteDatabase:
    return SqliteDatabase(SqliteConnectionConfig(path=path))


def test_connection_applies_frozen_pragmas(tmp_path: Path) -> None:
    database = _database(tmp_path / "first.sqlite3")

    with database as connection:
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert connection.execute("PRAGMA busy_timeout").fetchone()[0] == 5000
        assert connection.execute("PRAGMA journal_mode").fetchone()[0].lower() == "wal"
        assert connection.execute("PRAGMA synchronous").fetchone()[0] == 2
        assert isinstance(connection.row_factory, type(sqlite3.Row))


def test_connection_open_and_close_are_explicit_and_idempotent(tmp_path: Path) -> None:
    database = _database(tmp_path / "lifecycle.sqlite3")

    with pytest.raises(RuntimeError, match="not_open"):
        _ = database.connection

    database.open()
    with pytest.raises(RuntimeError, match="already_open"):
        database.open()

    database.close()
    database.close()
    with pytest.raises(RuntimeError, match="not_open"):
        _ = database.connection


def test_transaction_commits_and_rolls_back(tmp_path: Path) -> None:
    database = _database(tmp_path / "transactions.sqlite3")
    with database as connection:
        with sqlite_transaction(connection):
            connection.execute("CREATE TABLE values_table(value INTEGER NOT NULL)")
            connection.execute("INSERT INTO values_table(value) VALUES (1)")

        with pytest.raises(RuntimeError, match="rollback_marker"):
            with sqlite_transaction(connection):
                connection.execute("INSERT INTO values_table(value) VALUES (2)")
                raise RuntimeError("rollback_marker")

        values = connection.execute("SELECT value FROM values_table ORDER BY value").fetchall()
        assert [row[0] for row in values] == [1]


def test_transaction_rejects_nesting(tmp_path: Path) -> None:
    database = _database(tmp_path / "nested.sqlite3")
    with database as connection:
        with sqlite_transaction(connection):
            with pytest.raises(RuntimeError, match="already_open"):
                with sqlite_transaction(connection):
                    pass


def test_separate_database_paths_are_isolated(tmp_path: Path) -> None:
    first = _database(tmp_path / "first.sqlite3")
    second = _database(tmp_path / "second.sqlite3")

    with first as first_connection:
        first_connection.execute("CREATE TABLE only_first(value INTEGER NOT NULL)")
    with second as second_connection:
        table_names = second_connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()

    assert table_names == []
