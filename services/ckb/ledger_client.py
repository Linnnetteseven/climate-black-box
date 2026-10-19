"""Python side of the on-chain Evidence Ledger (see services/ckb/ledger.mjs).

Each project gets one ledger cell on CKB whose type script recomputes a
running commitment over every event appended to it. This module maps audit
events to ledger entries, appends what hasn't been recorded yet, and asks the
chain whether a given event sits where our database says it does.

The private key never enters this process: it is read by the Node signer
from the environment, exactly as for anchor.mjs.
"""

from __future__ import annotations

import json
import logging
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

log = logging.getLogger("cbb.ledger")
CKB_DIR = Path(__file__).resolve().parent
TIMEOUT_S = 180

#: audit_events.event_type → ledger kind (must match ledger-core.mjs and the script)
KIND_OF_EVENT = {
    "observation_recorded": 1,
    "remeasurement_recorded": 1,
    "alert_raised": 2,
    "alert_resolved": 3,
    "commitment_approved": 4,
    "investigation_recorded": 4,
    "intervention_logged": 4,
}


def run(cmd: str, *args: str, stdin: Any = None, timeout: int = TIMEOUT_S) -> dict:
    """Run ledger.mjs and return its JSON (or a structured failure)."""
    try:
        result = subprocess.run(
            ["node", "ledger.mjs", cmd, *args], cwd=CKB_DIR, capture_output=True, text=True,
            input=json.dumps(stdin) if stdin is not None else None, timeout=timeout,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "code": "ledger_unavailable", "state": "chain_unavailable", "message": str(exc)[:200]}
    text = (result.stdout or result.stderr).strip()
    try:
        return json.loads(text.splitlines()[-1])
    except (ValueError, IndexError):
        return {"ok": False, "code": "ledger_failed", "message": text[:300]}


def period_of(event_type: str, manifest: dict, alert_period: str | None = None) -> str:
    """The month an event is about, as YYYY-MM.

    Observations carry their own period. An alert is about the last month it
    rests on (the script requires that month to be already observed). Other
    events are filed under the month they were recorded.
    """
    if event_type in ("observation_recorded", "remeasurement_recorded"):
        return manifest["period_key"]
    if event_type in ("alert_raised", "alert_resolved") and alert_period:
        return alert_period
    created = manifest.get("created_at") or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return created[:7]


def entry_for(event_type: str, manifest: dict, sha256: str, alert_period: str | None = None) -> dict:
    if event_type not in KIND_OF_EVENT:
        raise ValueError(f"no ledger kind for event type {event_type!r}")
    return {"kind": KIND_OF_EVENT[event_type], "period": period_of(event_type, manifest, alert_period),
            "sha256": sha256.removeprefix("0x")}


# ── Database helpers (imported lazily so the pure functions test without Oracle) ──

def project_ledger(project_id: str) -> dict | None:
    from services.api.db.connection import cursor
    with cursor() as cur:
        cur.execute(
            """SELECT type_id, type_hash, recorder_lock_hash, recorder_address, create_tx_hash
                 FROM ckb_ledgers WHERE project_id = :p""", p=project_id)
        row = cur.fetchone()
    return None if row is None else dict(
        type_id=row[0], type_hash=row[1], recorder_lock_hash=row[2], recorder_address=row[3], create_tx_hash=row[4])


def _alert_period(cur, alert_id: str) -> str | None:
    """Latest observed month an alert rests on."""
    cur.execute("SELECT evidence_ids FROM alerts WHERE id = :a", a=alert_id)
    row = cur.fetchone()
    if not row:
        return None
    raw = row[0].read() if hasattr(row[0], "read") else row[0]
    ids = json.loads(raw or "[]")
    if not ids:
        return None
    binds = {f"i{n}": v for n, v in enumerate(ids)}
    cur.execute(f"SELECT MAX(period_key) FROM observations WHERE id IN ({', '.join(':' + k for k in binds)})", **binds)
    return cur.fetchone()[0]


def _manifest(raw) -> dict:
    if isinstance(raw, (dict, list)):
        return raw
    return json.loads(raw.read() if hasattr(raw, "read") else raw)


def append_pending(project_id: str) -> dict:
    """Append every event of this project that isn't on its ledger yet, in order, in one tx."""
    from services.api.db.connection import cursor
    ledger = project_ledger(project_id)
    if ledger is None:
        return {"ok": False, "code": "no_ledger", "message": "Create the project's ledger first (make ledger-create)."}

    with cursor() as cur:
        cur.execute(
            """SELECT e.id, e.event_type, e.subject_id, e.canonical_manifest, e.manifest_sha256
                 FROM audit_events e
                WHERE e.project_id = :p
                  AND NOT EXISTS (SELECT 1 FROM chain_anchors a
                                   WHERE a.event_id = e.id AND a.anchor_kind = 'ledger' AND a.status = 'confirmed')
                ORDER BY e.created_at, e.id""", p=project_id)
        events = cur.fetchall()
        cur.execute("""SELECT NVL(MAX(ledger_seq), 0) FROM chain_anchors a JOIN audit_events e ON e.id = a.event_id
                        WHERE e.project_id = :p AND a.anchor_kind = 'ledger'""", p=project_id)
        recorded = int(cur.fetchone()[0])
        entries = []
        for event_id, etype, subject_id, raw, digest in events:
            manifest = _manifest(raw)
            alert_period = _alert_period(cur, subject_id) if etype in ("alert_raised", "alert_resolved") else None
            entries.append((event_id, digest, entry_for(etype, manifest, digest, alert_period)))

    if not entries:
        return {"ok": True, "appended": 0, "message": "Nothing new to record."}

    # Our count must agree with the chain before we append, or positions would drift
    state = run("state", ledger["type_id"], ledger["recorder_lock_hash"])
    if not state.get("ok"):
        return state
    if int(state["seq"]) != recorded:
        return {"ok": False, "code": "seq_mismatch",
                "message": f"Database says {recorded} events are on the ledger; the chain says {state['seq']}. "
                           "Refusing to append until they agree."}

    result = run("append", ledger["type_id"], stdin=[e for _, _, e in entries])
    if not result.get("ok"):
        return result

    with cursor() as cur:
        for n, (event_id, digest, _) in enumerate(entries, start=recorded + 1):
            cur.execute(
                """INSERT INTO chain_anchors
                     (id, event_id, network, tx_hash, output_index, manifest_sha256, status,
                      explorer_url, anchored_at, anchor_kind, ledger_seq)
                   VALUES (:id, :ev, 'ckb-testnet', :tx, 0, :sha, 'confirmed', :url, :ts, 'ledger', :seq)""",
                id=f"anc-l-{event_id}"[:64], ev=event_id, tx=result["tx_hash"], sha=digest,
                url=result["explorer_url"], ts=datetime.now(timezone.utc), seq=n)
    log.info("  appended %d events to the ledger (seq %s..%s): %s",
             len(entries), recorded + 1, result["to_seq"], result["explorer_url"])
    return {**result, "appended": len(entries)}


def check_event(ledger: dict, seq: int, event_type: str, manifest: dict, sha256: str, alert_period: str | None = None) -> dict:
    e = entry_for(event_type, manifest, sha256, alert_period)
    return run("check", ledger["type_id"], ledger["recorder_lock_hash"], str(seq), str(e["kind"]),
               e["period"], f"0x{e['sha256']}", timeout=90)
