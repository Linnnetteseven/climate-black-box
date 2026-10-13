"""Anchor any audit events that do not yet have a confirmed commitment.

Separate from build_evidence_chain.py on purpose. That script rebuilds the
chain from the observations and would discard events created through the
application -- an intervention logged in the UI, for instance. This one only
ever adds anchors for what is already there.

All outstanding hashes go into a single transaction: separate ones would each
claim the same unconfirmed input cell and CKB would reject them as
replace-by-fee conflicts.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.api.db.connection import cursor  # noqa: E402

load_dotenv()
log = logging.getLogger("cbb.anchor")
CKB_DIR = Path(__file__).resolve().parents[1] / "services" / "ckb"


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default="mau-transmara-demo")
    args = ap.parse_args()

    with cursor() as cur:
        cur.execute(
            """SELECT e.id, e.manifest_sha256, e.event_type
                 FROM audit_events e
                 LEFT JOIN chain_anchors a
                   ON a.event_id = e.id AND a.status = 'confirmed'
                WHERE e.project_id = :p AND a.id IS NULL
                ORDER BY e.created_at""",
            p=args.project,
        )
        pending = cur.fetchall()

    if not pending:
        log.info("nothing to anchor: every event already has a confirmed commitment")
        return 0

    log.info("anchoring %d event(s):", len(pending))
    for _, _, etype in pending:
        log.info("  %s", etype)

    result = subprocess.run(
        ["node", "anchor.mjs", *(f"0x{sha}" for _, sha, _ in pending)],
        cwd=CKB_DIR, capture_output=True, text=True, timeout=180,
    )
    if result.returncode != 0:
        log.error("anchoring failed: %s", result.stderr.strip()[:300])
        return 1

    payload = json.loads(result.stdout.strip().splitlines()[-1])
    by_hash = {a["manifest_sha256"].lower(): a["output_index"] for a in payload["anchors"]}

    for event_id, sha, _ in pending:
        anchor_id = "anc-" + hashlib.sha256(f"{event_id}|{payload['tx_hash']}".encode()).hexdigest()[:16]
        with cursor() as cur:
            cur.execute("DELETE FROM chain_anchors WHERE event_id = :e AND status <> 'confirmed'",
                        e=event_id)
            cur.execute(
                """INSERT INTO chain_anchors
                     (id, event_id, network, tx_hash, output_index, manifest_sha256,
                      status, explorer_url, anchored_at)
                   VALUES (:id, :ev, 'ckb-testnet', :tx, :idx, :sha, 'confirmed', :url, :ts)""",
                id=anchor_id, ev=event_id, tx=payload["tx_hash"],
                idx=by_hash[f"0x{sha}".lower()], sha=sha,
                url=payload["explorer_url"], ts=datetime.now(timezone.utc),
            )

    log.info("anchored in %s", payload["tx_hash"])
    log.info("%s", payload["explorer_url"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
