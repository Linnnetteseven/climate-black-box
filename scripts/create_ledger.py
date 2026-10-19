"""Create a project's on-chain Evidence Ledger (once per project).

After this, `make anchor` appends the project's events to the ledger instead
of anchoring loose cells, and the chain builder stops rebuilding history: the
ledger's type script would refuse a rewrite anyway.

Needs CKB_SIGNER_PRIVATE_KEY (the recorder) with ~200 testnet CKB for the cell.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.api.db.connection import cursor  # noqa: E402
from services.ckb import ledger_client  # noqa: E402

load_dotenv()
log = logging.getLogger("cbb.ledger")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default="mau-transmara-demo")
    ap.add_argument("--payout", help="CKB address that receives released donations (default: the recorder)")
    args = ap.parse_args()

    existing = ledger_client.project_ledger(args.project)
    if existing:
        log.info("%s already has a ledger: type_id %s (created in %s)",
                 args.project, existing["type_id"], existing["create_tx_hash"])
        return 0

    result = ledger_client.run("create")
    if not result.get("ok"):
        log.error("could not create the ledger (%s): %s", result.get("code"), result.get("message"))
        return 1

    with cursor() as cur:
        cur.execute(
            """INSERT INTO ckb_ledgers
                 (project_id, network, type_id, type_hash, recorder_lock_hash, recorder_address,
                  payout_address, create_tx_hash)
               VALUES (:p, 'ckb-testnet', :tid, :th, :rl, :ra, :pa, :tx)""",
            p=args.project, tid=result["type_id"], th=result["type_hash"], rl=result["recorder_lock_hash"],
            ra=result["recorder_address"], pa=args.payout or result["recorder_address"], tx=result["tx_hash"],
        )
    log.info("ledger created for %s", args.project)
    log.info("  type_id   %s", result["type_id"])
    log.info("  type_hash %s  (donations' Evidence Gates point here)", result["type_hash"])
    log.info("  %s", result["explorer_url"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
