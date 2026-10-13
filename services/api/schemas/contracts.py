"""The wire contracts, frozen at Gate 0.

Every lane codes against these shapes. Field names are final and snake_case:
Python, Oracle and FastAPI are all snake_case-native, and the frontend
generates its TypeScript from this module's OpenAPI output rather than
hand-maintaining a second spelling.

One asymmetry is deliberate and documented in docs/ckb-integrity.md: numbers
here are real numbers, because these are API responses. Inside an evidence
*manifest* every number is a string, because manifests get hashed and float
formatting is not portable. Both rules are right in their own scope.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SimulationStatus(StrEnum):
    """Provenance of a record, shown as a badge on every surface.

    A boolean would not be enough: `fallback` records the case where an AI
    summary came from the deterministic template rather than the model, which
    is exactly the kind of thing we must not round off to "real".
    """

    REAL = "real"
    SIMULATED = "simulated"
    MIXED = "mixed"
    FALLBACK = "fallback"


class VerificationState(StrEnum):
    VERIFIED = "verified"
    MODIFIED = "modified"
    NOT_ANCHORED = "not_anchored"
    PENDING = "pending"
    CHAIN_UNAVAILABLE = "chain_unavailable"


class Base(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Project(Base):
    id: str
    name: str
    country: str
    region: str | None = None
    owner_org: str | None = None
    status: Literal["active", "closed", "suspended"]
    #: GeoJSON geometry. Labelled as approximate in the UI unless surveyed.
    boundary: dict | None = None
    boundary_is_survey: bool = False
    reporting_start: date | None = None
    reporting_end: date | None = None
    simulation_status: SimulationStatus


class Commitment(Base):
    id: str
    project_id: str
    metric: str
    target_value: float | None = None
    unit: str | None = None
    due_date: date | None = None
    baseline_start: date | None = None
    baseline_end: date | None = None
    source_document: str | None = None
    source_text_span: str | None = None
    extraction_status: Literal["proposed", "approved", "rejected"]
    extraction_model: str | None = None
    prompt_version: str | None = None
    reviewer: str | None = None
    reviewed_at: datetime | None = None
    simulation_status: SimulationStatus


class Observation(Base):
    id: str
    project_id: str
    metric: str
    value: float | None
    unit: str
    period_start: datetime
    period_end: datetime
    observed_at: datetime | None = None
    valid_pixel_fraction: float | None = Field(default=None, ge=0.0, le=1.0)
    cloud_cover_scene_pct: float | None = None
    quality_flags: list[str] = Field(default_factory=list)
    source_dataset: str | None = None
    source_scene_id: str | None = None
    processing_version: str
    evidence_asset_id: str | None = None
    simulation_status: SimulationStatus


class RainfallPoint(Base):
    """Rainfall context. ERA5 is a ~25 km grid, so this is district-scale and
    the UI says so -- it cannot resolve conditions at a 200-hectare site."""

    period_start: datetime
    period_end: datetime
    precipitation_mm: float
    anomaly_mm: float | None = None
    source_dataset: str
    resolution_note: str = "ERA5 reanalysis, ~25 km grid -- district-level context, not site rainfall"
    simulation_status: SimulationStatus


class Alert(Base):
    id: str
    project_id: str
    metric: str
    rule_version: str
    method: str
    severity: Literal["info", "review", "urgent"]
    status: Literal["open", "investigating", "resolved", "dismissed"]
    observed_value: float | None = None
    expected_value: float | None = None
    expected_low: float | None = None
    expected_high: float | None = None
    deviation_abs: float | None = None
    deviation_pct: float | None = None
    consecutive_periods: int = 0
    period_start: datetime | None = None
    period_end: datetime | None = None
    quality_flags: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    #: Plain language, shown verbatim in the UI. If we cannot write this
    #: sentence, the alert should not exist.
    explanation: str
    #: Shown next to the alert, never hidden in a tooltip.
    limitations: str
    created_at: datetime
    simulation_status: SimulationStatus


class Hypothesis(Base):
    statement: str
    #: Must reference evidence that was actually supplied to the model.
    evidence_ids: list[str]
    confidence: Literal["low", "medium", "high"]


class Investigation(Base):
    id: str
    alert_id: str
    summary: str
    hypotheses: list[Hypothesis]
    evidence_ids: list[str]
    missing_evidence: str | None = None
    model_id: str | None = None
    prompt_version: str | None = None
    #: `fallback` when the deterministic template produced this, not the model.
    simulation_status: SimulationStatus
    created_at: datetime


class InterventionCreate(Base):
    project_id: str
    alert_id: str | None = None
    action: str = Field(min_length=3, max_length=400)
    actor: str = Field(min_length=2, max_length=200)
    action_date: date
    expected_outcome: str | None = Field(default=None, max_length=1000)
    followup_date: date | None = None


class Intervention(Base):
    id: str
    project_id: str
    alert_id: str | None = None
    action: str
    actor: str
    action_date: date
    expected_outcome: str | None = None
    followup_date: date | None = None
    status: Literal["planned", "in_progress", "done", "abandoned"]
    #: Always 'simulated'. The database refuses anything else -- we have no
    #: field team, so no intervention here may claim to be a real one.
    simulation_status: Literal[SimulationStatus.SIMULATED]
    created_at: datetime


class TrendComparison(Base):
    """Pre/post intervention. Deliberately not called an 'effect'."""

    project_id: str
    metric: str
    intervention_id: str | None = None
    pre_mean: float | None = None
    post_mean: float | None = None
    pre_periods: int = 0
    post_periods: int = 0
    change_abs: float | None = None
    causal_note: str = (
        "A change after an intervention is correlation, not proof of cause. "
        "Weather, season and measurement coverage all moved too."
    )


class AuditEvent(Base):
    id: str
    project_id: str
    event_type: str
    subject_table: str | None = None
    subject_id: str | None = None
    actor: str | None = None
    manifest_sha256: str | None = None
    previous_event_sha256: str | None = None
    anchor: "AnchorRef | None" = None
    created_at: datetime
    simulation_status: SimulationStatus


class AnchorRef(Base):
    network: str
    tx_hash: str | None = None
    output_index: int | None = None
    status: Literal["pending", "confirmed", "failed"]
    explorer_url: str | None = None
    anchored_at: datetime | None = None


class VerificationResult(Base):
    evidence_id: str
    verified: bool
    state: VerificationState
    manifest_hash_recomputed: str | None = None
    manifest_hash_onchain: str | None = None
    network: str | None = None
    tx_hash: str | None = None
    output_index: int | None = None
    anchored_at: datetime | None = None
    explorer_url: str | None = None
    #: Human-readable reason, especially for the four unhappy states.
    detail: str | None = None


class ErrorResponse(Base):
    """One shape for every non-2xx. Never a stack trace."""

    code: str
    message: str
    request_id: str
    details: list[dict] = Field(default_factory=list)


AuditEvent.model_rebuild()
