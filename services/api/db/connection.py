"""Database connections.

One place decides whether we are talking to the local development container
or to Autonomous Database, so promoting to ADB is a change to .env and
nothing else. The rest of the codebase never reads these variables.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from functools import lru_cache
from typing import Iterator

import oracledb


class DatabaseUnavailable(RuntimeError):
    """Raised when the database cannot be reached.

    Caught at the route layer and turned into a labelled degraded state
    rather than a stack trace: the demo stays on its feet if Oracle blinks.
    """


@lru_cache(maxsize=1)
def _pool() -> oracledb.ConnectionPool:
    mode = os.getenv("ORACLE_MODE", "local").lower()
    common = dict(min=1, max=8, increment=1, getmode=oracledb.POOL_GETMODE_WAIT)

    if mode == "adb":
        wallet = os.getenv("TNS_ADMIN")
        if not wallet:
            raise DatabaseUnavailable("ORACLE_MODE=adb but TNS_ADMIN is not set")
        return oracledb.create_pool(
            user=os.environ["ADB_USER"],
            password=os.environ["ADB_PASSWORD"],
            dsn=os.environ["ADB_DSN"],
            config_dir=wallet,
            wallet_location=wallet,
            wallet_password=os.getenv("ADB_WALLET_PASSWORD"),
            **common,
        )

    return oracledb.create_pool(
        user=os.getenv("ORACLE_APP_USER", "cbb"),
        password=os.environ.get("ORACLE_APP_PASSWORD", ""),
        dsn=os.getenv("ORACLE_DSN", "localhost:1521/FREEPDB1"),
        **common,
    )


@contextmanager
def cursor() -> Iterator[oracledb.Cursor]:
    """Yield a cursor, committing on success and rolling back on failure."""
    try:
        connection = _pool().acquire()
    except (oracledb.DatabaseError, KeyError) as exc:
        raise DatabaseUnavailable(str(exc)) from exc

    try:
        with connection.cursor() as cur:
            yield cur
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        _pool().release(connection)


def describe_backend() -> str:
    """Human-readable backend label, shown on the health endpoint.

    Deliberately explicit: on stage we must never call local Oracle
    "Autonomous Database".
    """
    if os.getenv("ORACLE_MODE", "local").lower() == "adb":
        return "Oracle Autonomous Database"
    return "Oracle Database 23ai Free (local container)"
