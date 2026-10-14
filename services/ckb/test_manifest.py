"""Tests for manifest construction.

The property under test throughout: the same evidence must always produce the
same bytes, whatever type the database hands us or what platform we are on.
"""

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from services.ckb.canonical import canonical_bytes, manifest_hash
from services.ckb.manifest import alert_manifest, num, observation_manifest

FIXED = datetime(2026, 10, 13, 9, 0, 0, tzinfo=timezone.utc)

BASE = dict(
    project_id="kiambu-restoration-demo",
    event_id="evt_000003",
    observation_id="obs-1b69e290e5cacd04",
    metric="ndvi_mean",
    value=0.5578,
    unit="index",
    observed_at="2026-09-24T07:43:11Z",
    period_key="2026-09",
    source_dataset="Landsat Collection 2 Level-2 (landsat-c2-l2)",
    source_scene_id="LC08_L2SP_168061_20260924_02_T1",
    valid_pixel_fraction=0.946,
    cloud_cover_pct=12.4,
    processing_version="ndvi-v1",
    simulation_status="real",
    previous_event_hash=None,
    created_at=FIXED,
)


def test_numbers_render_as_fixed_precision_strings():
    assert num(0.5578, 6) == "0.557800"
    assert num(0.1, 6) == "0.100000"
    assert num(None, 6) is None


def test_equivalent_float_representations_render_identically():
    """The whole reason numbers are strings."""
    assert num(0.42, 6) == num(0.420, 6) == num(4.2e-1, 6)


def test_decimal_and_float_inputs_agree():
    """Oracle may return a Decimal where the pipeline produced a float."""
    assert num(Decimal("0.5578"), 6) == num(0.5578, 6)


def test_manifest_is_fully_stringified():
    m = observation_manifest(**BASE)
    # canonical_bytes refuses any numeric leaf, so this asserts the invariant
    canonical_bytes(m)


def test_manifest_hash_is_stable():
    assert manifest_hash(observation_manifest(**BASE)) == manifest_hash(
        observation_manifest(**BASE)
    )


def test_timestamps_normalise_to_utc_z():
    shifted = dict(BASE, observed_at="2026-09-24T10:43:11+03:00")
    assert observation_manifest(**shifted)["observed_at"] == "2026-09-24T07:43:11Z"
    # and therefore the same hash as the Z-form
    assert manifest_hash(observation_manifest(**shifted)) == manifest_hash(
        observation_manifest(**BASE)
    )


def test_changing_the_measurement_changes_the_hash():
    tampered = dict(BASE, value=0.5579)
    assert manifest_hash(observation_manifest(**tampered)) != manifest_hash(
        observation_manifest(**BASE)
    )


def test_changing_the_scene_id_changes_the_hash():
    tampered = dict(BASE, source_scene_id="LC08_L2SP_168061_20260101_02_T1")
    assert manifest_hash(observation_manifest(**tampered)) != manifest_hash(
        observation_manifest(**BASE)
    )


def test_changing_quality_changes_the_hash():
    """Coverage is part of the claim, not metadata around it."""
    tampered = dict(BASE, valid_pixel_fraction=0.20)
    assert manifest_hash(observation_manifest(**tampered)) != manifest_hash(
        observation_manifest(**BASE)
    )


def test_chaining_changes_the_hash():
    chained = dict(BASE, previous_event_hash="a" * 64)
    assert manifest_hash(observation_manifest(**chained)) != manifest_hash(
        observation_manifest(**BASE)
    )


def test_alert_manifest_pins_the_thresholds():
    """Re-tuning the rule after the fact must break verification."""
    args = dict(
        project_id="mau-transmara-demo", event_id="evt_000009", alert_id="alert_001",
        metric="ndvi_mean", rule_version="divergence-v1",
        method="robust linear baseline, residual sigma band, 2 consecutive periods",
        observed_value=-0.1183, expected_value=0.0937,
        expected_low=0.0273, expected_high=0.1601,
        consecutive_periods=5, evidence_ids=["obs-a", "obs-b"],
        simulation_status="real", previous_event_hash=None, created_at=FIXED,
    )
    original = manifest_hash(alert_manifest(**args))
    widened = manifest_hash(alert_manifest(**dict(args, expected_low=-0.2)))
    assert original != widened


def test_evidence_id_order_does_not_matter():
    """The set of evidence is the claim; the order we happened to read it is not."""
    args = dict(
        project_id="p", event_id="e", alert_id="a", metric="ndvi_mean",
        rule_version="v1", method="m", observed_value=0.1, expected_value=0.2,
        expected_low=0.1, expected_high=0.3, consecutive_periods=2,
        simulation_status="real", previous_event_hash=None, created_at=FIXED,
    )
    one = manifest_hash(alert_manifest(**args, evidence_ids=["b", "a", "c"]))
    two = manifest_hash(alert_manifest(**args, evidence_ids=["c", "a", "b"]))
    assert one == two


# --- the tamper demonstration ----------------------------------------------

def test_tamper_falls_back_when_the_requested_field_is_absent():
    """Regression: the UI asked to alter 'metric_value' on an intervention
    manifest, which has no such field. Nothing changed, so verification
    passed and the tamper button appeared to prove the opposite of its
    purpose."""
    from services.ckb.verifier import pick_tamper_field

    intervention = {
        "schema_version": "1.0", "event_id": "evt_1", "event_type": "intervention_logged",
        "project_id": "p", "action": "Replanting", "actor": "Team",
        "previous_event_hash": None, "created_at": "2026-10-13T09:00:00Z",
        "simulation_status": "simulated",
    }
    chosen = pick_tamper_field(intervention, "metric_value")
    assert chosen is not None
    assert chosen not in ("schema_version", "event_id", "event_type",
                          "project_id", "previous_event_hash", "created_at")


def test_tamper_prefers_the_requested_field_when_present():
    from services.ckb.verifier import pick_tamper_field

    observation = {"schema_version": "1.0", "metric_value": "0.42", "unit": "index"}
    assert pick_tamper_field(observation, "metric_value") == "metric_value"


def test_tamper_returns_none_when_there_is_nothing_substantive():
    from services.ckb.verifier import pick_tamper_field

    bare = {"schema_version": "1.0", "event_id": "e", "event_type": "t",
            "project_id": "p", "previous_event_hash": None, "created_at": "x"}
    assert pick_tamper_field(bare, "metric_value") is None
