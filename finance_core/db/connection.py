"""Database connection helpers shared by the API and the Telegram bot.

SQLite remains the default for local development and tests. When a
``DATABASE_URL`` points at PostgreSQL (Supabase), the same repositories run
through a small compatibility layer so the SQL does not need two versions:
``?`` placeholders, ``CURRENT_TIMESTAMP`` text values, ``lastrowid``, and
``with connection:`` keep working. Repositories never commit on their own; the
caller wraps writes in :func:`transaction`.
"""

from __future__ import annotations

import re
import sqlite3
import threading
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from typing import Any

try:  # PostgreSQL support stays optional so SQLite-only installs keep working.
    import psycopg
    from psycopg_pool import ConnectionPool
except ImportError:  # pragma: no cover - exercised only without the extra
    psycopg = None  # type: ignore[assignment]
    ConnectionPool = None  # type: ignore[assignment]

# SQLite stores timestamps as ``YYYY-MM-DD HH:MM:SS`` text. PostgreSQL columns
# mirror that format so API responses keep the exact same shape.
_POSTGRES_TIMESTAMP = "to_char(now() AT TIME ZONE 'UTC', 'YYYY-MM-DD HH24:MI:SS')"
_CURRENT_TIMESTAMP = "CURRENT_TIMESTAMP"
_INSERT_OR_IGNORE = re.compile(r"INSERT\s+OR\s+IGNORE\s+INTO", re.IGNORECASE)


class Row(Mapping[str, Any]):
    """Row with both name and position access, like ``sqlite3.Row``."""

    __slots__ = ("_names", "_values", "_positions")

    def __init__(self, names: Sequence[str], values: Sequence[Any]) -> None:
        self._names = tuple(names)
        self._values = tuple(values)
        self._positions = {name: index for index, name in enumerate(self._names)}

    def keys(self) -> list[str]:  # type: ignore[override]
        return list(self._names)

    def __getitem__(self, key: str | int) -> Any:
        if isinstance(key, str):
            return self._values[self._positions[key]]
        return self._values[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._names)

    def __len__(self) -> int:
        return len(self._names)

    def __repr__(self) -> str:
        pairs = ", ".join(f"{name}={value!r}" for name, value in zip(self._names, self._values))
        return f"Row({pairs})"


def _translate(sql: str, *, has_params: bool) -> str:
    """Turn one SQLite-flavoured statement into PostgreSQL-compatible SQL."""

    if _INSERT_OR_IGNORE.search(sql):
        sql = _INSERT_OR_IGNORE.sub("INSERT INTO", sql)
        if "ON CONFLICT" not in sql.upper():
            sql = sql.rstrip().rstrip(";") + " ON CONFLICT DO NOTHING"

    out: list[str] = []
    index = 0
    length = len(sql)
    in_single = False
    in_double = False

    while index < length:
        char = sql[index]

        if in_single:
            if char == "'":
                if index + 1 < length and sql[index + 1] == "'":
                    out.append("''")
                    index += 2
                    continue
                in_single = False
                out.append(char)
            elif char == "%" and has_params:
                out.append("%%")
            else:
                out.append(char)
            index += 1
            continue

        if in_double:
            if char == '"':
                in_double = False
            if char == "%" and has_params:
                out.append("%%")
            else:
                out.append(char)
            index += 1
            continue

        if char == "'":
            in_single = True
            out.append(char)
            index += 1
            continue
        if char == '"':
            in_double = True
            out.append(char)
            index += 1
            continue
        if char == "?":
            out.append("%s")
            index += 1
            continue
        if char == "%" and has_params:
            out.append("%%")
            index += 1
            continue
        if sql[index : index + len(_CURRENT_TIMESTAMP)].upper() == _CURRENT_TIMESTAMP:
            out.append(_POSTGRES_TIMESTAMP)
            index += len(_CURRENT_TIMESTAMP)
            continue

        out.append(char)
        index += 1

    return "".join(out)


class PostgresCursor:
    """Cursor wrapper that returns :class:`Row` objects and emulates lastrowid."""

    def __init__(self, cursor: Any, connection: Any) -> None:
        self._cursor = cursor
        self._connection = connection
        self._lastrowid: int | None = None
        names = [column.name for column in cursor.description] if cursor.description else []
        self._names = names

    @property
    def lastrowid(self) -> int | None:
        """Return the id of the row the current transaction just inserted.

        PostgreSQL has no cursor-level ``lastrowid``, but ``lastval()`` reports
        the last sequence value used on this connection, which is exactly what
        SQLite callers expect right after an ``INSERT``.
        """

        if self._lastrowid is None:
            row = self._connection.execute("SELECT lastval()").fetchone()
            self._lastrowid = int(row[0]) if row is not None else None
        return self._lastrowid

    @property
    def rowcount(self) -> int:
        return self._cursor.rowcount

    def fetchone(self) -> Row | None:
        row = self._cursor.fetchone()
        return None if row is None else Row(self._names, row)

    def fetchall(self) -> list[Row]:
        return [Row(self._names, row) for row in self._cursor.fetchall()]

    def __iter__(self) -> Iterator[Row]:
        return (Row(self._names, row) for row in self._cursor)

    def close(self) -> None:
        self._cursor.close()


class PostgresConnection:
    """Connection wrapper that gives PostgreSQL SQLite-like ergonomics."""

    dialect = "postgres"

    def __init__(self, connection: Any, pool: Any = None) -> None:
        self._connection = connection
        self._pool = pool
        self._context: Any = None
        self._depth = 0

    # Repositories set this on SQLite connections; keep it a harmless no-op.
    @property
    def row_factory(self) -> Any:
        return Row

    @row_factory.setter
    def row_factory(self, _value: Any) -> None:
        return None

    def execute(self, sql: str, params: Sequence[Any] | None = None) -> PostgresCursor:
        has_params = bool(params)
        translated = _translate(sql, has_params=has_params)

        cursor = self._connection.cursor()
        try:
            cursor.execute(translated, params if has_params else None)
        except Exception:
            cursor.close()
            raise

        return PostgresCursor(cursor, self._connection)

    def executemany(self, sql: str, params_seq: Sequence[Sequence[Any]]) -> PostgresCursor:
        translated = _translate(sql, has_params=True)
        cursor = self._connection.cursor()
        try:
            cursor.executemany(translated, params_seq)
        except Exception:
            cursor.close()
            raise
        return PostgresCursor(cursor, self._connection)

    @contextmanager
    def transaction(self) -> Iterator[PostgresConnection]:
        """Outer transaction, or a savepoint when already inside one.

        psycopg turns nested ``connection.transaction()`` blocks into
        savepoints automatically, which mirrors the nesting support SQLite
        gives the repositories. Any implicit read transaction left open by a
        previous statement is committed first so the outermost block really
        owns the commit.
        """

        if self._depth == 0:
            self._connection.commit()

        self._depth += 1
        try:
            with self._connection.transaction():
                yield self
        finally:
            self._depth -= 1

    def __enter__(self) -> PostgresConnection:
        self._context = self.transaction()
        self._context.__enter__()
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> Any:
        context = self._context
        self._context = None
        return context.__exit__(exc_type, exc, traceback)

    def commit(self) -> None:
        self._connection.commit()

    def rollback(self) -> None:
        self._connection.rollback()

    def close(self) -> None:
        if self._pool is not None:
            try:
                self._connection.rollback()
            except Exception:  # pragma: no cover - connection already broken
                pass
            self._pool.putconn(self._connection)
            self._pool = None
        else:
            self._connection.close()


_pools: dict[str, Any] = {}
_pools_lock = threading.Lock()


def _pool_for(url: str) -> Any:
    if ConnectionPool is None:
        raise RuntimeError(
            "psycopg is not installed. Install psycopg[binary] and psycopg-pool "
            "to use DATABASE_URL."
        )

    with _pools_lock:
        pool = _pools.get(url)
        if pool is None:
            pool = ConnectionPool(
                url,
                open=True,
                min_size=0,
                max_size=5,
                max_idle=300,
                timeout=10.0,
                check=ConnectionPool.check_connection,
                kwargs={
                    # Supabase's transaction pooler (pgbouncer) cannot keep
                    # server-side prepared statements between requests.
                    "prepare_threshold": None,
                    "autocommit": False,
                    "connect_timeout": 10,
                },
            )
            _pools[url] = pool
        return pool


def connect_url(url: str) -> PostgresConnection:
    """Open one logical PostgreSQL connection backed by the shared pool."""

    pool = _pool_for(url)
    return PostgresConnection(pool.getconn(), pool)


def close_pools() -> None:
    """Close every pooled PostgreSQL connection. Used by tests and shutdown."""

    with _pools_lock:
        pools = list(_pools.values())
        _pools.clear()
    for pool in pools:
        pool.close()


def is_postgres(connection: Any) -> bool:
    """Return True when the connection talks to PostgreSQL."""

    return getattr(connection, "dialect", None) == "postgres"


@contextmanager
def transaction(connection: Any) -> Iterator[Any]:
    """Run a block as one database transaction.

    Repositories never commit on their own, so a caller can compose several
    writes and get all-or-nothing behaviour by wrapping them in this context
    manager. Nested use becomes a savepoint on PostgreSQL.
    """

    if is_postgres(connection):
        with connection.transaction():
            yield connection
        return

    try:
        yield connection
    except BaseException:
        connection.rollback()
        raise
    else:
        connection.commit()


def connect(
    database_path: str | Any,
    *,
    check_same_thread: bool = True,
) -> sqlite3.Connection:
    """Open a SQLite connection with the project-wide pragmas applied.

    ``check_same_thread`` stays enabled by default. Only the Telegram bot, which
    shares one connection across handler executions, passes ``False``.
    """

    path = str(database_path)
    connection = sqlite3.connect(path, check_same_thread=check_same_thread, timeout=5.0)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 5000")
    return connection


def open_database(
    database_path: str | Any = "bot04.sqlite3",
    *,
    url: str | None = None,
    check_same_thread: bool = True,
) -> Any:
    """Open the configured database: PostgreSQL when a URL is set, else SQLite."""

    if url:
        return connect_url(url)
    return connect(database_path, check_same_thread=check_same_thread)