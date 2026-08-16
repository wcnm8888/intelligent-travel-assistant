"""Transactional, checksum-verified SQLite migrations for F-002."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from dataclasses import dataclass

from intelligent_travel_assistant.adapters.persistence.connection import sqlite_transaction
from intelligent_travel_assistant.adapters.persistence.schema import INITIAL_SCHEMA_STATEMENTS


class MigrationError(RuntimeError):
    """Base error for fail-closed migration handling."""


class MigrationConfigurationError(MigrationError):
    """The code-owned migration list is invalid."""


class MigrationHistoryError(MigrationError):
    """The database history cannot be safely reconciled with the code."""


@dataclass(frozen=True, slots=True)
class Migration:
    version: int
    name: str
    statements: tuple[str, ...]

    def __post_init__(self) -> None:
        if type(self.version) is not int or self.version < 1:
            raise ValueError("migration_version_invalid")
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("migration_name_invalid")
        if not isinstance(self.statements, tuple) or not self.statements:
            raise ValueError("migration_statements_invalid")
        if any(
            not isinstance(statement, str) or not statement.strip() for statement in self.statements
        ):
            raise ValueError("migration_statement_invalid")

    @property
    def checksum(self) -> str:
        canonical = json.dumps(
            {
                "name": self.name,
                "statements": self.statements,
                "version": self.version,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()


INITIAL_SCHEMA_MIGRATION = Migration(
    version=1,
    name="initial_schema",
    statements=INITIAL_SCHEMA_STATEMENTS,
)
DEFAULT_MIGRATIONS: tuple[Migration, ...] = (INITIAL_SCHEMA_MIGRATION,)


class MigrationRunner:
    """Apply the code-owned migration sequence without automatic downgrade."""

    def __init__(self, migrations: tuple[Migration, ...] = DEFAULT_MIGRATIONS) -> None:
        if not isinstance(migrations, tuple) or not migrations:
            raise MigrationConfigurationError("migration_list_empty")
        versions = tuple(migration.version for migration in migrations)
        if versions != tuple(sorted(versions)) or len(set(versions)) != len(versions):
            raise MigrationConfigurationError("migration_versions_not_strictly_ascending")
        if versions[0] != 1:
            raise MigrationConfigurationError("migration_initial_version_must_be_one")
        self._migrations = migrations

    @property
    def migrations(self) -> tuple[Migration, ...]:
        return self._migrations

    def run(self, connection: sqlite3.Connection) -> tuple[int, ...]:
        self._ensure_metadata_table(connection)
        applied = self._read_applied(connection)
        self._validate_history(applied)

        for migration in self._migrations[len(applied) :]:
            with sqlite_transaction(connection):
                for statement in migration.statements:
                    connection.execute(statement)
                connection.execute(
                    """
                    INSERT INTO schema_migrations(version, name, checksum, applied_at)
                    VALUES (?, ?, ?, strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
                    """,
                    (migration.version, migration.name, migration.checksum),
                )

        return tuple(migration.version for migration in self._migrations)

    @staticmethod
    def _ensure_metadata_table(connection: sqlite3.Connection) -> None:
        with sqlite_transaction(connection):
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY CHECK (version >= 1),
                    name TEXT NOT NULL CHECK (length(name) > 0),
                    checksum TEXT NOT NULL CHECK (
                        length(checksum) = 64 AND checksum = lower(checksum)
                    ),
                    applied_at TEXT NOT NULL
                )
                """
            )

    @staticmethod
    def _read_applied(connection: sqlite3.Connection) -> tuple[sqlite3.Row, ...]:
        return tuple(
            connection.execute(
                "SELECT version, name, checksum FROM schema_migrations ORDER BY version"
            ).fetchall()
        )

    def _validate_history(self, applied: tuple[sqlite3.Row, ...]) -> None:
        known = {migration.version: migration for migration in self._migrations}
        applied_versions = tuple(int(row["version"]) for row in applied)
        expected_prefix = tuple(migration.version for migration in self._migrations[: len(applied)])
        if applied_versions != expected_prefix:
            raise MigrationHistoryError("migration_history_gap_or_unknown_version")

        for row in applied:
            migration = known.get(int(row["version"]))
            if migration is None:
                raise MigrationHistoryError("migration_version_not_supported")
            if row["name"] != migration.name or row["checksum"] != migration.checksum:
                raise MigrationHistoryError("migration_checksum_mismatch")
