"""Run a .sql file against the configured Oracle database.

Oracle's own clients are not installed everywhere, and sqlplus is not in this
environment at all, so migrations go through python-oracledb in thin mode --
no Instant Client needed. The file is split on statement boundaries because
oracledb executes one statement per call.

`--tolerant` lets a script continue past errors, which is what a drop script
needs on a clean database.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

import oracledb


def connect():
    """Connect to local Oracle, or to Autonomous Database when ORACLE_MODE=adb."""
    mode = os.getenv("ORACLE_MODE", "local").lower()
    if mode == "adb":
        wallet = os.getenv("TNS_ADMIN")
        if not wallet:
            sys.exit("ORACLE_MODE=adb requires TNS_ADMIN pointing at the unzipped wallet")
        return oracledb.connect(
            user=os.environ["ADB_USER"],
            password=os.environ["ADB_PASSWORD"],
            dsn=os.environ["ADB_DSN"],
            config_dir=wallet,
            wallet_location=wallet,
            wallet_password=os.getenv("ADB_WALLET_PASSWORD"),
        )
    return oracledb.connect(
        user=os.getenv("ORACLE_APP_USER", "cbb"),
        password=os.environ["ORACLE_APP_PASSWORD"],
        dsn=os.getenv("ORACLE_DSN", "localhost:1521/FREEPDB1"),
    )


def split_statements(sql: str) -> list[str]:
    """Split a script into executable statements.

    Comments are stripped first so a semicolon inside one cannot split a
    statement. PL/SQL blocks are not supported and we do not use any.
    """
    sql = re.sub(r"^\s*--.*$", "", sql, flags=re.MULTILINE)
    return [s.strip() for s in sql.split(";") if s.strip()]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", type=Path)
    parser.add_argument("--tolerant", action="store_true",
                        help="log and continue on error (for drop scripts)")
    args = parser.parse_args()

    statements = split_statements(args.path.read_text(encoding="utf-8"))
    failures = 0

    with connect() as conn, conn.cursor() as cur:
        for statement in statements:
            try:
                cur.execute(statement)
            except oracledb.DatabaseError as exc:
                failures += 1
                head = " ".join(statement.split())[:70]
                if args.tolerant:
                    print(f"  skip: {head}... ({exc.args[0].message.splitlines()[0]})")
                else:
                    print(f"\nFAILED: {head}...\n  {exc}", file=sys.stderr)
                    return 1
        conn.commit()

    label = args.path.name
    if args.tolerant:
        print(f"{label}: {len(statements) - failures}/{len(statements)} applied, {failures} skipped")
    else:
        print(f"{label}: {len(statements)} statements applied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
