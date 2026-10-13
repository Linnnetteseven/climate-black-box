"""Verify a project's evidence chain against CKB testnet.

For every anchored event: re-canonicalise the stored manifest, re-hash it,
and compare that against what is actually in the cell on chain. Then check
that each event's `previous_event_hash` really is the hash of the event before
it, so the chain is a chain and not a list.

What a pass means: the manifest you are reading now is byte-identical to the
one committed at that time. It does not mean the measurement was right.
"""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.api.db.connection import cursor  # noqa: E402
from services.ckb.canonical import manifest_hash  # noqa: E402

load_dotenv()
log = logging.getLogger("cbb.verify")
CKB_DIR = Path(__file__).resolve().parents[1] / "services" / "ckb"


def _manifest(raw) -> dict:
    if isinstance(raw, (dict, list)):
        return raw
    return json.loads(raw.read() if hasattr(raw, "read") else raw)


def verify_onchain(tx_hash: str, index: int, expected: str) -> dict:
    try:
        result = subprocess.run(
            ["node", "verify.mjs", tx_hash, str(index), f"0x{expected}"],
            cwd=CKB_DIR, capture_output=True, text=True, timeout=120,
        )
        return json.loads((result.stdout or result.stderr).strip().splitlines()[-1])
    except Exception as exc:
        return {"state": "chain_unavailable", "verified": False, "detail": str(exc)}


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default="mau-transmara-demo")
    ap.add_argument("--tamper", metavar="FIELD",
                    help="mutate this manifest field on the LAST event before verifying, "
                         "to demonstrate that verification fails")
    args = ap.parse_args()

    with cursor() as cur:
        cur.execute(
            """SELECT e.id, e.event_type, e.manifest_sha256, e.previous_event_sha256,
                      e.canonical_manifest, a.tx_hash, a.output_index, a.status
                 FROM audit_events e
                 LEFT JOIN chain_anchors a ON a.event_id = e.id
                WHERE e.project_id = :p
                ORDER BY e.created_at""",
            p=args.project,
        )
        rows = cur.fetchall()

    if not rows:
        log.error("no audit events for %s", args.project)
        return 1

    log.info("project: %s   %d events\n", args.project, len(rows))
    previous = None
    all_ok = True

    for i, (event_id, etype, stored_sha, prev_sha, raw, tx_hash, index, status) in enumerate(rows):
        manifest = _manifest(raw)

        if args.tamper and i == len(rows) - 1:
            before = manifest.get(args.tamper)
            manifest = dict(manifest)
            manifest[args.tamper] = "0.000000" if isinstance(before, str) else "tampered"
            log.info("  !! tampering with %r on the last event: %r -> %r",
                     args.tamper, before, manifest[args.tamper])

        recomputed = manifest_hash(manifest)
        local_ok = recomputed == stored_sha
        chain_link_ok = (prev_sha is None and i == 0) or prev_sha == previous

        if tx_hash and status == "confirmed":
            chain = verify_onchain(tx_hash, index, recomputed)
            state, chain_ok = chain.get("state"), bool(chain.get("verified"))
        else:
            state, chain_ok = (status or "not_anchored"), False

        mark = "PASS" if (local_ok and chain_ok and chain_link_ok) else "FAIL"
        if mark == "FAIL":
            all_ok = False
        log.info("  %d. %-22s %s", i + 1, etype, mark)
        log.info("       stored   %s", stored_sha)
        log.info("       computed %s  %s", recomputed, "match" if local_ok else "MISMATCH")
        log.info("       on-chain %-18s link:%s", state, "ok" if chain_link_ok else "BROKEN")
        previous = stored_sha

    log.info("\n  chain verifies: %s", all_ok)
    if rows[0][5]:
        log.info("  explorer: https://pudge.explorer.nervos.org/transaction/%s", rows[0][5])
    return 0 if all_ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
