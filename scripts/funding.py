"""Evidence-gated funding, for operators.

    make keeper  PROJECT=...   collect due donations into their Evidence Gates (CKB_KEEPER_PRIVATE_KEY)
    make collect PROJECT=...   the project withdraws released donations (CKB_PROJECT_PRIVATE_KEY)

Both read the project's ledger identity from the database and hand off to
services/ckb/funding.mjs. Keys stay in the Node process's environment.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.api.db.connection import cursor  # noqa: E402
from services.ckb import ledger_client  # noqa: E402

load_dotenv()
log = logging.getLogger("cbb.funding")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("job", choices=["keep", "collect"])
    ap.add_argument("--project", default="mau-transmara-demo")
    args = ap.parse_args()

    ledger = ledger_client.project_ledger(args.project)
    if ledger is None:
        log.error("%s has no on-chain ledger (make ledger-create)", args.project)
        return 1
    with cursor() as cur:
        cur.execute("SELECT NVL(payout_address, recorder_address) FROM ckb_ledgers WHERE project_id = :p", p=args.project)
        payout = cur.fetchone()[0]

    extra = [payout] if args.job == "keep" else []
    import subprocess
    result = subprocess.run(
        ["node", "funding.mjs", args.job, ledger["type_id"], ledger["recorder_lock_hash"], *extra],
        cwd=ledger_client.CKB_DIR, capture_output=True, text=True, timeout=900,
    )
    text = (result.stdout or result.stderr).strip()
    try:
        payload = json.loads(text.splitlines()[-1])
    except (ValueError, IndexError):
        log.error("funding tool failed: %s", text[:300])
        return 1
    log.info(json.dumps(payload, indent=2))
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
