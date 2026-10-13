"""Tests for the pre/post comparison and the decision it feeds.

The thing being guarded here is restraint. It is trivially easy to make this
module claim an intervention worked; these tests exist to keep it from doing
so on evidence that cannot support the claim.
"""

import pytest

from services.analytics.alerts import Period
from services.analytics.trend import (
    MIN_PERIODS_PER_SIDE,
    compare,
    recommendation,
)


def series(values, start_index=0, prefix="2026-", valid=0.9):
    return [
        Period(f"{prefix}{start_index + i:02d}", start_index + i, v, valid)
        for i, v in enumerate(values)
    ]


def test_declines_to_compare_without_enough_post_evidence():
    anomalies = series([-0.10, -0.11, -0.12], 1) + series([-0.05], 7)
    result = compare(anomalies, intervention_period="2026-06")
    assert not result.sufficient
    assert result.direction == "unknown"
    assert "pending rather than negative" in result.note


def test_declines_to_compare_without_enough_pre_evidence():
    anomalies = series([-0.10], 1) + series([-0.05, -0.04, -0.03], 7)
    result = compare(anomalies, intervention_period="2026-06")
    assert not result.sufficient


def test_low_coverage_periods_do_not_count_toward_the_minimum():
    anomalies = (
        series([-0.10, -0.11], 1)
        + [Period("2026-07", 7, 0.05, 0.10), Period("2026-08", 8, 0.06, 0.12)]
    )
    result = compare(anomalies, intervention_period="2026-06")
    assert not result.sufficient
    assert result.post_periods == 0


def test_reports_improvement_when_it_exceeds_the_noise():
    anomalies = series([-0.12, -0.11, -0.12], 1) + series([0.04, 0.05, 0.04], 7)
    result = compare(anomalies, intervention_period="2026-06")
    assert result.sufficient
    assert result.direction == "improving"
    assert result.change_abs > 0


def test_reports_decline_when_it_continues():
    anomalies = series([-0.05, -0.04, -0.05], 1) + series([-0.20, -0.21, -0.22], 7)
    result = compare(anomalies, intervention_period="2026-06")
    assert result.direction == "declining"


def test_a_move_smaller_than_the_noise_is_reported_as_unchanged():
    """The restraint test: scattered data must not read as a result."""
    anomalies = series([-0.10, 0.05, -0.08, 0.06], 1) + series([-0.06, 0.04, -0.05, 0.05], 7)
    result = compare(anomalies, intervention_period="2026-06")
    assert result.sufficient
    assert result.direction == "unchanged"
    assert "within the spread" in result.note


def test_the_causal_note_is_always_present():
    anomalies = series([-0.12, -0.11, -0.12], 1) + series([0.04, 0.05, 0.04], 7)
    result = compare(anomalies, intervention_period="2026-06")
    assert "correlation, not proof of cause" in result.causal_note
    assert "untreated area" in result.causal_note


def test_minimum_is_enforced_at_exactly_the_boundary():
    anomalies = series([-0.10, -0.11], 1) + series([0.05, 0.06], 7)
    result = compare(anomalies, intervention_period="2026-06")
    assert result.sufficient
    assert result.pre_periods == MIN_PERIODS_PER_SIDE


# --- the decision beat -----------------------------------------------------

def test_insufficient_evidence_recommends_measuring_not_concluding():
    anomalies = series([-0.10, -0.11], 1) + series([0.05], 7)
    action, why = recommendation(compare(anomalies, "2026-06"), alert_open=True)
    assert "do not draw a conclusion" in action.lower()


def test_decline_recommends_escalation_and_field_verification():
    anomalies = series([-0.05, -0.04, -0.05], 1) + series([-0.20, -0.21, -0.22], 7)
    action, why = recommendation(compare(anomalies, "2026-06"), alert_open=True)
    assert "escalate" in action.lower()
    assert "field verification" in action.lower()


def test_improvement_is_never_described_as_proof():
    anomalies = series([-0.12, -0.11, -0.12], 1) + series([0.04, 0.05, 0.04], 7)
    action, why = recommendation(compare(anomalies, "2026-06"), alert_open=False)
    body = (action + " " + why).lower()
    assert "not yet conclusive" in body
    for forbidden in ("proves", "proven", "caused by", "because of the intervention"):
        assert forbidden not in body


def test_no_change_is_not_reported_as_failure():
    anomalies = series([-0.10, 0.05, -0.08, 0.06], 1) + series([-0.06, 0.04, -0.05, 0.05], 7)
    action, why = recommendation(compare(anomalies, "2026-06"), alert_open=True)
    assert "not evidence" in why and "failed" in why
