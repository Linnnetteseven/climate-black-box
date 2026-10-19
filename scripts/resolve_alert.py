"""Resolve (or dismiss) an alert, and record that as evidence on the ledger.

The Evidence Gate holds a project's donated funding while its ledger shows an
open alert. Resolving is therefore a consequential, recorded act: this writes
an `alert_resolved` audit event with who resolved it and why, and appends it
to the project's on-chain ledger, which decrements the open-alert count.

    python scripts/resolve_alert.py --alert <id> --resolution resolved \\
        --note "Field visit 2026-10: canopy intact; dip was a cloud artefact" --by "Field team"
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.api.db.connection import cursor  # noqa: E402
from services.ckb import ledger_client  # noqa: E402
from services.ckb.canonical import manifest_hash  # noqa: E402
from services.ckb.manifest import resolution_manifest  # noqa: E402

load_dotenv()
log = logging.getLogger("cbb.resolve")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--alert", required=True)
    ap.add_argument("--resolution", choices=["resolved", "dismissed"], default="resolved")
    ap.add_argument("--note", required=True, help="what settled it (kept in the committed record)")
    ap.add_argument("--by", required=True, help="who resolved it")
    args = ap.parse_args()

    with cursor() as cur:
        cur.execute("SELECT project_id, status, simulation_status FROM alerts WHERE id = :a", a=args.alert)
        row = cur.fetchone()
        if row is None:
            log.error("no alert %s", args.alert)
            return 1
        project_id, status, sim = row
        if status in ("resolved", "dismissed"):
            log.error("alert %s is already %s", args.alert, status)
            return 1
        cur.execute("SELECT manifest_sha256 FROM audit_events WHERE project_id = :p ORDER BY created_at DESC, id DESC",
                    p=project_id)
        prev = cur.fetchone()

        event_id = "evt-" + hashlib.sha256(f"{project_id}|resolve|{args.alert}".encode()).hexdigest()[:16]
        manifest = resolution_manifest(
            project_id=project_id, event_id=event_id, alert_id=args.alert, resolution=args.resolution,
            note=args.note, resolved_by=args.by, simulation_status=sim, previous_event_hash=prev[0] if prev else None,
        )
        digest = manifest_hash(manifest)
        cur.execute(
            """INSERT INTO audit_events
                 (id, project_id, event_type, subject_table, subject_id, actor,
                  canonical_manifest, manifest_sha256, previous_event_sha256, simulation_status)
               VALUES (:id, :pid, 'alert_resolved', 'alerts', :aid, :actor, :m, :sha, :prev, :sim)""",
            id=event_id, pid=project_id, aid=args.alert, actor=args.by[:200], m=json.dumps(manifest),
            sha=digest, prev=manifest["previous_event_hash"], sim=sim,
        )
        cur.execute("UPDATE alerts SET status = :s WHERE id = :a", s=args.resolution, a=args.alert)
    log.info("alert %s marked %s; resolution event %s written", args.alert, args.resolution, event_id)

    if ledger_client.project_ledger(project_id):
        result = ledger_client.append_pending(project_id)
        if not result.get("ok"):
            log.error("recorded locally but NOT on the ledger yet (%s): %s", result.get("code"), result.get("message"))
            return 1
        log.info("on the ledger: open alerts now %s · %s", result.get("open_alerts"), result.get("explorer_url"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
