"""All SQL lives here.

Two rules, both load-bearing:

* **Bind variables only.** No f-strings, no concatenation, no exceptions.
* **Rows become contract objects here**, not in routes. A route that builds a
  dict by hand is a route that will drift from the schema.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from services.api.db.connection import cursor
from services.api.schemas.contracts import (
    Alert,
    AuditEvent,
    AnchorRef,
    Commitment,
    Observation,
    Project,
    SimulationStatus,
)


def _json(value: Any) -> Any:
    """Oracle hands JSON-constrained columns back as a dict, a str or a LOB
    depending on version and column type. Normalise all three."""
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    if hasattr(value, "read"):
        value = value.read()
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None
    return None


def _text(value: Any) -> str | None:
    if value is None:
        return None
    return value.read() if hasattr(value, "read") else str(value)


def _flags(value: Any) -> list[str]:
    raw = _text(value)
    return [f.strip() for f in raw.split(",") if f.strip()] if raw else []


# --- projects --------------------------------------------------------------

_PROJECT_COLUMNS = """
  id, name, country, region, owner_org, status,
  boundary_geojson, boundary_is_survey,
  reporting_start, reporting_end, simulation_status
"""


def _to_project(row: tuple) -> Project:
    return Project(
        id=row[0], name=row[1], country=row[2], region=row[3], owner_org=row[4],
        status=row[5], boundary=_json(row[6]), boundary_is_survey=bool(row[7]),
        reporting_start=row[8].date() if isinstance(row[8], datetime) else row[8],
        reporting_end=row[9].date() if isinstance(row[9], datetime) else row[9],
        simulation_status=SimulationStatus(row[10]),
    )


def list_projects() -> list[Project]:
    with cursor() as cur:
        cur.execute(f"SELECT {_PROJECT_COLUMNS} FROM projects ORDER BY name")
        return [_to_project(r) for r in cur]


def get_project(project_id: str) -> Project | None:
    with cursor() as cur:
        cur.execute(f"SELECT {_PROJECT_COLUMNS} FROM projects WHERE id = :pid", pid=project_id)
        row = cur.fetchone()
        return _to_project(row) if row else None


# --- commitments -----------------------------------------------------------

def list_commitments(project_id: str) -> list[Commitment]:
    with cursor() as cur:
        cur.execute(
            """SELECT id, project_id, metric, target_value, unit, due_date,
                      baseline_start, baseline_end, source_document, source_text_span,
                      extraction_status, extraction_model, prompt_version,
                      reviewer, reviewed_at, simulation_status
                 FROM commitments
                WHERE project_id = :pid
                ORDER BY metric""",
            pid=project_id,
        )
        return [
            Commitment(
                id=r[0], project_id=r[1], metric=r[2], target_value=r[3], unit=r[4],
                due_date=r[5], baseline_start=r[6], baseline_end=r[7],
                source_document=r[8], source_text_span=_text(r[9]),
                extraction_status=r[10], extraction_model=r[11], prompt_version=r[12],
                reviewer=r[13], reviewed_at=r[14],
                simulation_status=SimulationStatus(r[15]),
            )
            for r in cur
        ]


# --- observations ----------------------------------------------------------

def list_observations(
    project_id: str,
    metric: str | None = None,
    frm: datetime | None = None,
    to: datetime | None = None,
) -> list[Observation]:
    sql = """
      SELECT o.id, o.project_id, o.metric, o.value, o.unit,
             o.period_start, o.period_end, o.observed_at,
             o.valid_pixel_fraction, o.cloud_cover_pct, o.quality_flags,
             e.source_dataset, e.source_id,
             o.processing_version, o.evidence_asset_id, o.simulation_status
        FROM observations o
        LEFT JOIN evidence_assets e ON e.id = o.evidence_asset_id
       WHERE o.project_id = :pid
    """
    params: dict[str, Any] = {"pid": project_id}
    if metric:
        sql += " AND o.metric = :metric"
        params["metric"] = metric
    if frm:
        sql += " AND o.period_start >= :frm"
        params["frm"] = frm
    if to:
        sql += " AND o.period_end <= :tto"
        params["tto"] = to
    sql += " ORDER BY o.period_start"

    with cursor() as cur:
        cur.execute(sql, **params)
        return [
            Observation(
                id=r[0], project_id=r[1], metric=r[2], value=r[3], unit=r[4],
                period_start=r[5], period_end=r[6], observed_at=r[7],
                valid_pixel_fraction=r[8], cloud_cover_scene_pct=r[9],
                quality_flags=_flags(r[10]),
                source_dataset=r[11], source_scene_id=r[12],
                processing_version=r[13], evidence_asset_id=r[14],
                simulation_status=SimulationStatus(r[15]),
            )
            for r in cur
        ]


# --- alerts ----------------------------------------------------------------

_ALERT_COLUMNS = """
  id, project_id, metric, rule_version, method, severity, status,
  observed_value, expected_value, expected_low, expected_high,
  deviation_abs, deviation_pct, consecutive_periods,
  period_start, period_end, quality_flags, evidence_ids,
  explanation, limitations, created_at, simulation_status
"""


def _to_alert(r: tuple) -> Alert:
    return Alert(
        id=r[0], project_id=r[1], metric=r[2], rule_version=r[3], method=r[4],
        severity=r[5], status=r[6],
        observed_value=r[7], expected_value=r[8], expected_low=r[9], expected_high=r[10],
        deviation_abs=r[11], deviation_pct=r[12], consecutive_periods=r[13] or 0,
        period_start=r[14], period_end=r[15],
        quality_flags=_flags(r[16]), evidence_ids=_json(r[17]) or [],
        explanation=_text(r[18]) or "", limitations=_text(r[19]) or "",
        created_at=r[20], simulation_status=SimulationStatus(r[21]),
    )


def list_alerts(project_id: str | None = None) -> list[Alert]:
    sql = f"SELECT {_ALERT_COLUMNS} FROM alerts"
    params: dict[str, Any] = {}
    if project_id:
        sql += " WHERE project_id = :pid"
        params["pid"] = project_id
    sql += " ORDER BY created_at DESC"
    with cursor() as cur:
        cur.execute(sql, **params)
        return [_to_alert(r) for r in cur]


def get_alert(alert_id: str) -> Alert | None:
    with cursor() as cur:
        cur.execute(f"SELECT {_ALERT_COLUMNS} FROM alerts WHERE id = :aid", aid=alert_id)
        row = cur.fetchone()
        return _to_alert(row) if row else None


def latest_alert(project_id: str) -> Alert | None:
    alerts = list_alerts(project_id)
    return alerts[0] if alerts else None


# --- audit trail -----------------------------------------------------------

def list_audit_events(project_id: str) -> list[AuditEvent]:
    """The ordered evidence chain, with each event's anchor state attached."""
    with cursor() as cur:
        cur.execute(
            """SELECT event_id, project_id, event_type, subject_table, subject_id,
                      actor, manifest_sha256, previous_event_sha256, created_at,
                      simulation_status, network, tx_hash, output_index,
                      anchor_status, explorer_url, anchored_at
                 FROM v_audit_timeline
                WHERE project_id = :pid
                ORDER BY created_at""",
            pid=project_id,
        )
        events = []
        for r in cur:
            anchor = (
                AnchorRef(
                    network=r[10], tx_hash=r[11], output_index=r[12],
                    status=r[13], explorer_url=r[14], anchored_at=r[15],
                )
                if r[10] else None
            )
            events.append(
                AuditEvent(
                    id=r[0], project_id=r[1], event_type=r[2], subject_table=r[3],
                    subject_id=r[4], actor=r[5], manifest_sha256=r[6],
                    previous_event_sha256=r[7], anchor=anchor, created_at=r[8],
                    simulation_status=SimulationStatus(r[9]),
                )
            )
        return events
