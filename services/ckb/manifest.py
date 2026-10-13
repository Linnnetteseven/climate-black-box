"""Build the evidence manifests that get hashed and anchored.

A manifest is a compact, self-contained statement of one evidence event: what
was measured, where it came from, how good the measurement was, and what came
before it. It is the thing a verifier re-hashes, so its construction has to be
boringly deterministic.

Every number is rendered as a string. That is not sloppiness -- it is the
single most important decision in this module. `0.42`, `0.420` and `4.2e-1`
are the same number and different bytes, and no two languages or library
versions agree on how to render a float. A hash that silently stops matching
six months after it was anchored is the worst possible failure for an
integrity claim, so numbers are frozen as text at the moment of construction.

See docs/ckb-integrity.md for what the resulting anchor does and does not
prove.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

SCHEMA_VERSION = "1.0"

#: Fixed decimal places per metric, so the same measurement always renders to
#: the same string regardless of how the database hands it back.
METRIC_PRECISION = {
    "ndvi_mean": 6,
}
FRACTION_PRECISION = 6


def num(value: Any, places: int) -> str | None:
    """Render a number as a fixed-precision string, deterministically.

    Decimal is used rather than format() on a float so the rounding is
    specified rather than inherited from the platform's float repr.
    """
    if value is None:
        return None
    return str(Decimal(str(value)).quantize(Decimal(1).scaleb(-places)))


def _utc(value: datetime | str | None) -> str | None:
    """ISO-8601 in UTC with a trailing Z, or None. One format, always."""
    if value is None:
        return None
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def observation_manifest(
    *,
    project_id: str,
    event_id: str,
    observation_id: str,
    metric: str,
    value: float | None,
    unit: str,
    observed_at: datetime | str | None,
    period_key: str,
    source_dataset: str,
    source_scene_id: str | None,
    valid_pixel_fraction: float | None,
    cloud_cover_pct: float | None,
    processing_version: str,
    simulation_status: str,
    previous_event_hash: str | None,
    created_at: datetime | None = None,
) -> dict[str, Any]:
    """A manifest for one recorded observation."""
    places = METRIC_PRECISION.get(metric, 6)
    return {
        "schema_version": SCHEMA_VERSION,
        "project_id": project_id,
        "event_id": event_id,
        "event_type": "observation_recorded",
        "observed_at": _utc(observed_at),
        "period_key": period_key,
        "observation_ids": [observation_id],
        "source_dataset": source_dataset,
        "source_scene_id": source_scene_id,
        "processing_version": processing_version,
        "metric_name": metric,
        "metric_value": num(value, places),
        "unit": unit,
        "quality_summary": {
            "valid_pixel_fraction": num(valid_pixel_fraction, FRACTION_PRECISION),
            "cloud_cover_scene_pct": num(cloud_cover_pct, 2),
        },
        "previous_event_hash": previous_event_hash,
        "created_at": _utc(created_at or datetime.now(timezone.utc)),
        "simulation_status": simulation_status,
    }


def alert_manifest(
    *,
    project_id: str,
    event_id: str,
    alert_id: str,
    metric: str,
    rule_version: str,
    method: str,
    observed_value: float | None,
    expected_value: float | None,
    expected_low: float | None,
    expected_high: float | None,
    consecutive_periods: int,
    evidence_ids: list[str],
    simulation_status: str,
    previous_event_hash: str | None,
    created_at: datetime | None = None,
) -> dict[str, Any]:
    """A manifest for a raised alert.

    The thresholds are part of the commitment: anchoring the band alongside the
    observation is what stops anyone (us included) from re-tuning the
    rule afterwards and claiming the alert always looked like this.
    """
    places = METRIC_PRECISION.get(metric, 6)
    return {
        "schema_version": SCHEMA_VERSION,
        "project_id": project_id,
        "event_id": event_id,
        "event_type": "alert_raised",
        "alert_id": alert_id,
        "metric_name": metric,
        "rule_version": rule_version,
        "method": method,
        "observed_value": num(observed_value, places),
        "expected_value": num(expected_value, places),
        "expected_low": num(expected_low, places),
        "expected_high": num(expected_high, places),
        "consecutive_periods": str(consecutive_periods),
        "evidence_ids": sorted(evidence_ids),
        "previous_event_hash": previous_event_hash,
        "created_at": _utc(created_at or datetime.now(timezone.utc)),
        "simulation_status": simulation_status,
    }
