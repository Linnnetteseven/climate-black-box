"""Orchestration for beat 5: gather evidence, investigate, persist, return.

Investigations are cached by alert id. Re-running the model on every page load
would be slow, non-deterministic and pointless -- the evidence has not changed.
A caller that genuinely wants a fresh answer passes refresh=True.
"""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import asdict

from services.analytics.seasonal import MIN_SAMPLES_PER_MONTH  # noqa: F401  (documented dependency)
from services.api.db.coerce import as_json, as_text
from services.api.db.connection import cursor
from services.genai.evidence import build_packet
from services.genai.investigate import Investigation, investigate

log = logging.getLogger("cbb.genai.service")

SEASONAL_NOTE = (
    "Each month is compared with the same calendar month in the approved baseline "
    "window, so ordinary dry-season decline is not mistaken for divergence."
)


def _load_alert(alert_id: str) -> dict | None:
    with cursor() as cur:
        cur.execute(
            """SELECT id, project_id, metric, rule_version, method, observed_value,
                      expected_value, expected_low, expected_high, consecutive_periods,
                      evidence_ids
                 FROM alerts WHERE id = :a""",
            a=alert_id,
        )
        row = cur.fetchone()
    if not row:
        return None
    keys = ("id", "project_id", "metric", "rule_version", "method", "observed_value",
            "expected_value", "expected_low", "expected_high", "consecutive_periods",
            "evidence_ids")
    alert = dict(zip(keys, row))
    alert["evidence_ids"] = as_json(alert["evidence_ids"], default=[])
    return alert


def _load_observations(project_id: str) -> list[dict]:
    """The NDVI series, with its rainfall context attached by period.

    Rainfall is stored as its own observation rows (metric `precipitation_mm`),
    so each rainfall figure the investigation cites has a real id and real
    provenance rather than being carried along unrecorded in a fixture.
    """
    with cursor() as cur:
        cur.execute(
            """SELECT id, period_key, value, valid_pixel_fraction FROM observations
                WHERE project_id = :p AND metric = 'ndvi_mean' ORDER BY period_key""",
            p=project_id,
        )
        rows = [dict(id=r[0], period_key=r[1], value=r[2], valid_pixel_fraction=r[3])
                for r in cur]
        cur.execute(
            """SELECT id, period_key, value FROM observations
                WHERE project_id = :p AND metric = 'precipitation_mm'""",
            p=project_id,
        )
        rain = {r[1]: (r[0], r[2]) for r in cur}

    for row in rows:
        entry = rain.get(row["period_key"])
        if entry:
            row["rainfall_id"], row["precipitation_mm"] = entry
    return rows


def _project_name(project_id: str) -> str:
    with cursor() as cur:
        cur.execute("SELECT name FROM projects WHERE id = :p", p=project_id)
        row = cur.fetchone()
    return row[0] if row else project_id


def _stored(alert_id: str) -> dict | None:
    with cursor() as cur:
        cur.execute(
            """SELECT id, summary, hypotheses_json, evidence_ids_json, missing_evidence,
                      model_id, prompt_version, simulation_status, created_at
                 FROM investigations WHERE alert_id = :a
                ORDER BY created_at DESC FETCH FIRST 1 ROWS ONLY""",
            a=alert_id,
        )
        row = cur.fetchone()
    if not row:
        return None
    return {
        "id": row[0], "alert_id": alert_id, "summary": as_text(row[1]),
        "hypotheses": as_json(row[2], default=[]), "evidence_ids": as_json(row[3], default=[]),
        "missing_evidence": as_text(row[4]), "model_id": row[5], "prompt_version": row[6],
        "simulation_status": row[7], "created_at": row[8],
    }


def _persist(alert_id: str, result: Investigation) -> dict:
    investigation_id = "inv-" + hashlib.sha256(
        f"{alert_id}|{result.prompt_version}|{result.simulation_status}".encode()
    ).hexdigest()[:16]
    with cursor() as cur:
        cur.execute("DELETE FROM investigations WHERE id = :i", i=investigation_id)
        cur.execute(
            """INSERT INTO investigations
                 (id, alert_id, summary, hypotheses_json, evidence_ids_json,
                  missing_evidence, model_id, prompt_version, simulation_status)
               VALUES (:id, :a, :summary, :hyp, :ev, :missing, :model, :pv, :sim)""",
            id=investigation_id, a=alert_id, summary=result.summary,
            hyp=json.dumps([asdict(h) for h in result.hypotheses]),
            ev=json.dumps(result.evidence_ids), missing=result.missing_evidence,
            model=result.model_id, pv=result.prompt_version, sim=result.simulation_status,
        )
    return _stored(alert_id)


def investigation_for(alert_id: str, refresh: bool = False) -> dict | None:
    """Return the investigation for an alert, generating it if needed."""
    if not refresh:
        existing = _stored(alert_id)
        if existing:
            return existing

    alert = _load_alert(alert_id)
    if alert is None:
        return None

    packet = build_packet(
        project_id=alert["project_id"],
        project_name=_project_name(alert["project_id"]),
        alert=alert,
        observations=_load_observations(alert["project_id"]),
        seasonal_note=SEASONAL_NOTE,
    )
    log.info("investigating %s with %d facts (%d bytes)",
             alert_id, len(packet.facts), len(packet.to_json().encode()))
    return _persist(alert_id, investigate(packet))
