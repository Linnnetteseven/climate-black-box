"""Verify a stored evidence manifest against its on-chain commitment.

This is the server side of the demo's sharpest moment. It re-canonicalises the
manifest we hold, re-hashes it, and asks CKB what was actually committed.

The five states are deliberately distinct, because conflating them would be
dishonest in different directions:

  verified          the manifest is byte-identical to what was committed
  modified          it is not -- the record changed after anchoring
  not_anchored      no commitment exists for this event yet
  pending           an anchor was attempted but is not confirmed
  chain_unavailable we could not reach CKB, which says nothing either way

A failure to reach the chain must never render as "modified", and a pending
anchor must never render as "verified".
"""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path
from typing import Any

from services.api.db.connection import cursor
from services.api.schemas.contracts import VerificationResult, VerificationState
from services.ckb.canonical import manifest_hash

log = logging.getLogger("cbb.verify")
CKB_DIR = Path(__file__).resolve().parents[2] / "services" / "ckb"
VERIFY_TIMEOUT_S = 60


def _manifest_of(raw: Any) -> dict:
    if isinstance(raw, (dict, list)):
        return raw
    return json.loads(raw.read() if hasattr(raw, "read") else raw)


def _load_event(event_id: str) -> dict | None:
    with cursor() as cur:
        cur.execute(
            """SELECT e.id, e.canonical_manifest, e.manifest_sha256,
                      a.tx_hash, a.output_index, a.status, a.explorer_url, a.anchored_at
                 FROM audit_events e
                 LEFT JOIN chain_anchors a ON a.event_id = e.id
                WHERE e.id = :eid""",
            eid=event_id,
        )
        row = cur.fetchone()
    if row is None:
        return None
    return dict(
        id=row[0], manifest=_manifest_of(row[1]), stored_sha=row[2],
        tx_hash=row[3], output_index=row[4], anchor_status=row[5],
        explorer_url=row[6], anchored_at=row[7],
    )


#: Fields that describe the record's position in the chain rather than its
#: content. Altering one of these would still break the hash, but it would not
#: demonstrate the thing the button exists to demonstrate: that a changed
#: *measurement* is detectable.
STRUCTURAL_FIELDS = frozenset({
    "schema_version", "event_id", "event_type", "project_id",
    "previous_event_hash", "created_at",
})


def pick_tamper_field(manifest: dict, requested: str | None) -> str | None:
    """Choose a field to alter, preferring the caller's choice.

    The caller cannot know what is in every manifest -- an observation has
    `metric_value`, an alert has `observed_value`, an intervention has neither.
    Previously a request naming an absent field silently changed nothing and
    the response came back `verified`, which made the tamper button look like
    proof of the opposite of what it proves.

    So: use the requested field when it exists, otherwise the first substantive
    one, and tell the caller which was actually used.
    """
    if requested and requested in manifest:
        return requested
    for key in sorted(manifest):
        if key in STRUCTURAL_FIELDS:
            continue
        if isinstance(manifest[key], (str, list, dict)) and manifest[key]:
            return key
    return None


def _ask_chain(tx_hash: str, index: int, expected_hex: str) -> dict:
    try:
        result = subprocess.run(
            ["node", "verify.mjs", tx_hash, str(index), f"0x{expected_hex}"],
            cwd=CKB_DIR, capture_output=True, text=True, timeout=VERIFY_TIMEOUT_S,
        )
        return json.loads((result.stdout or result.stderr).strip().splitlines()[-1])
    except Exception as exc:
        log.warning("chain verify failed for %s: %s", tx_hash, exc)
        return {"state": "chain_unavailable", "verified": False, "detail": str(exc)[:200]}


def verify_event(event_id: str, tamper_field: str | None = None) -> VerificationResult | None:
    """Verify one event. With ``tamper_field`` set, mutate that field first.

    The tamper path exists so the failure can be demonstrated live against a
    real transaction. It never writes: the stored manifest is untouched, and
    only this response reflects the mutation.
    """
    event = _load_event(event_id)
    if event is None:
        return None

    manifest = dict(event["manifest"])
    tampered = False
    altered_field: str | None = None

    if tamper_field is not None:
        altered_field = pick_tamper_field(manifest, tamper_field)
        if altered_field is None:
            # Nothing substantive to change. Say so rather than returning a
            # pass, which would read as "tampering did not break it".
            return VerificationResult(
                evidence_id=event_id,
                verified=False,
                state=VerificationState.NOT_ANCHORED,
                detail="This record has no substantive field to alter, so the "
                       "tamper demonstration cannot run against it.",
            )
        before = manifest[altered_field]
        manifest[altered_field] = (
            "0.000000" if isinstance(before, str) and before.replace(".", "").replace("-", "").isdigit()
            else "TAMPERED"
        )
        tampered = True

    recomputed = manifest_hash(manifest)

    if not event["tx_hash"] or event["anchor_status"] != "confirmed":
        state = (VerificationState.PENDING if event["anchor_status"] == "pending"
                 else VerificationState.NOT_ANCHORED)
        return VerificationResult(
            evidence_id=event_id, verified=False, state=state,
            manifest_hash_recomputed=recomputed,
            detail=("An anchoring transaction was submitted but is not yet confirmed."
                    if state is VerificationState.PENDING else
                    "This event has not been anchored on CKB."),
        )

    chain = _ask_chain(event["tx_hash"], event["output_index"], recomputed)
    state = VerificationState(chain.get("state", "chain_unavailable"))

    detail = chain.get("detail")
    if tampered:
        note = ""
        if altered_field != tamper_field:
            note = (f" (this record has no {tamper_field!r} field, so "
                    f"{altered_field!r} was altered instead)")
        detail = (f"Field {altered_field!r} was altered before verifying{note}. "
                  "The recomputed hash no longer matches the commitment made on chain.")

    return VerificationResult(
        evidence_id=event_id,
        verified=bool(chain.get("verified")) and not tampered,
        state=state,
        manifest_hash_recomputed=recomputed,
        manifest_hash_onchain=(chain.get("manifest_hash_onchain") or "").removeprefix("0x") or None,
        network="ckb-testnet",
        tx_hash=event["tx_hash"],
        output_index=event["output_index"],
        anchored_at=event["anchored_at"],
        explorer_url=event["explorer_url"],
        detail=detail,
    )
