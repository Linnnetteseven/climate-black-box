"""Recording an intervention, and measuring what happened afterwards.

Interventions are append-only and always `simulated` -- the database enforces
the latter with a CHECK constraint, because this system has no field team and
must not be able to claim otherwise even by accident.

Logging one writes an audit event, so the action joins the same evidence chain
as the observations and the alert. What was done, by whom, and when is evidence
about the project just as much as a satellite reading is.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone

from services.analytics.alerts import Period
from services.analytics.seasonal import build_climatology, deseasonalise
from services.analytics.trend import TrendComparison, compare, recommendation
from services.api.db.coerce import as_text
from services.api.db.connection import cursor
from services.api.schemas.contracts import Intervention, InterventionCreate

BASELINE_BEFORE = "2025"


def _id(prefix: str, *parts: str) -> str:
    return f"{prefix}-{hashlib.sha256('|'.join(parts).encode()).hexdigest()[:16]}"


def create_intervention(payload: InterventionCreate) -> Intervention:
    """Record an intervention and append it to the audit trail."""
    intervention_id = _id("int", payload.project_id, payload.action,
                          payload.action_date.isoformat())

    with cursor() as cur:
        cur.execute("DELETE FROM interventions WHERE id = :i", i=intervention_id)
        cur.execute(
            """INSERT INTO interventions
                 (id, project_id, alert_id, action, actor, action_date,
                  expected_outcome, followup_date, status, simulation_status)
               VALUES (:id, :pid, :aid, :action, :actor, :adate,
                       :outcome, :followup, 'planned', 'simulated')""",
            id=intervention_id, pid=payload.project_id, aid=payload.alert_id,
            action=payload.action, actor=payload.actor, adate=payload.action_date,
            outcome=payload.expected_outcome, followup=payload.followup_date,
        )

        # Join the evidence chain: link to whatever event currently ends it.
        cur.execute(
            """SELECT manifest_sha256 FROM audit_events
                WHERE project_id = :p ORDER BY created_at DESC FETCH FIRST 1 ROWS ONLY""",
            p=payload.project_id,
        )
        row = cur.fetchone()
        previous = row[0] if row else None

    from services.ckb.canonical import manifest_hash

    event_id = _id("evt", payload.project_id, intervention_id)
    manifest = {
        "schema_version": "1.0",
        "project_id": payload.project_id,
        "event_id": event_id,
        "event_type": "intervention_logged",
        "intervention_id": intervention_id,
        "action": payload.action,
        "actor": payload.actor,
        "action_date": payload.action_date.isoformat(),
        "expected_outcome": payload.expected_outcome,
        "alert_id": payload.alert_id,
        "previous_event_hash": previous,
        "created_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "simulation_status": "simulated",
    }
    digest = manifest_hash(manifest)

    with cursor() as cur:
        cur.execute("DELETE FROM audit_events WHERE id = :i", i=event_id)
        cur.execute(
            """INSERT INTO audit_events
                 (id, project_id, event_type, subject_table, subject_id, actor,
                  canonical_manifest, manifest_sha256, previous_event_sha256,
                  simulation_status)
               VALUES (:id, :pid, 'intervention_logged', 'interventions', :sid, :actor,
                       :manifest, :sha, :prev, 'simulated')""",
            id=event_id, pid=payload.project_id, sid=intervention_id,
            actor=payload.actor, manifest=json.dumps(manifest), sha=digest, prev=previous,
        )

    return get_intervention(intervention_id)  # type: ignore[return-value]


def get_intervention(intervention_id: str) -> Intervention | None:
    with cursor() as cur:
        cur.execute(
            """SELECT id, project_id, alert_id, action, actor, action_date,
                      expected_outcome, followup_date, status, simulation_status, created_at
                 FROM interventions WHERE id = :i""",
            i=intervention_id,
        )
        row = cur.fetchone()
    if not row:
        return None
    return Intervention(
        id=row[0], project_id=row[1], alert_id=row[2], action=as_text(row[3]),
        actor=row[4],
        action_date=row[5].date() if isinstance(row[5], datetime) else row[5],
        expected_outcome=as_text(row[6]),
        followup_date=row[7].date() if isinstance(row[7], datetime) else row[7],
        status=row[8], simulation_status=row[9], created_at=row[10],
    )


def list_interventions(project_id: str) -> list[Intervention]:
    with cursor() as cur:
        cur.execute(
            "SELECT id FROM interventions WHERE project_id = :p ORDER BY action_date",
            p=project_id,
        )
        ids = [r[0] for r in cur]
    return [i for i in (get_intervention(i) for i in ids) if i]


def trend_for(project_id: str) -> dict:
    """Beats 8 and 9: what happened after the intervention, and what to do."""
    interventions = list_interventions(project_id)
    with cursor() as cur:
        cur.execute(
            """SELECT period_key, value, valid_pixel_fraction FROM observations
                WHERE project_id = :p AND metric = 'ndvi_mean' ORDER BY period_key""",
            p=project_id,
        )
        rows = cur.fetchall()
        cur.execute(
            "SELECT COUNT(*) FROM alerts WHERE project_id = :p AND status = 'open'",
            p=project_id,
        )
        alert_open = cur.fetchone()[0] > 0

    periods = [
        Period(r[0], i, float(r[1]) if r[1] is not None else None, float(r[2] or 0))
        for i, r in enumerate(rows)
    ]
    baseline = [p for p in periods if p.period_id < BASELINE_BEFORE]
    observed = [p for p in periods if p.period_id >= BASELINE_BEFORE]

    if not interventions:
        return {
            "project_id": project_id, "metric": "ndvi_mean", "intervention": None,
            "trend": None, "recommendation": None,
            "note": "No intervention recorded, so there is nothing to measure against.",
        }

    latest = interventions[-1]
    # Comparison is on seasonally-adjusted anomalies: comparing raw NDVI across
    # an intervention date would mostly measure the calendar.
    climatology = build_climatology(baseline)
    anomalies = deseasonalise(observed, climatology)

    trend: TrendComparison = compare(anomalies, latest.action_date.strftime("%Y-%m"))
    action, why = recommendation(trend, alert_open=alert_open)

    return {
        "project_id": project_id,
        "metric": "ndvi_mean",
        "intervention": latest,
        "trend": {
            "pre_mean": trend.pre_mean, "post_mean": trend.post_mean,
            "pre_periods": trend.pre_periods, "post_periods": trend.post_periods,
            "change_abs": trend.change_abs, "sufficient": trend.sufficient,
            "direction": trend.direction, "note": trend.note,
            "causal_note": trend.causal_note,
        },
        "recommendation": {"action": action, "reasoning": why},
        "note": None,
    }
