"""Tests for the divergence rule.

The three cases that matter on stage: it fires when it should, it stays quiet
when it should, and bad data can never trigger it.
"""

import pytest

from services.analytics.alerts import (
    MIN_BASELINE_PERIODS,
    MIN_RESIDUAL_SIGMA,
    MIN_VALID_FRACTION,
    REQUIRED_CONSECUTIVE,
    Period,
    evaluate,
    expected_band,
    fit_baseline,
)


def series(values, start=0, valid=0.9, prefix="p"):
    return [
        Period(period_id=f"{prefix}{start + i}", index=start + i, value=v, valid_fraction=valid)
        for i, v in enumerate(values)
    ]


# A gently improving restoration baseline: NDVI climbing ~0.01 a period.
BASELINE = series([0.40, 0.41, 0.42, 0.43, 0.44, 0.45])


# --- fitting ---------------------------------------------------------------

def test_fit_recovers_a_known_slope():
    slope, intercept, sigma = fit_baseline(BASELINE)
    assert slope == pytest.approx(0.01, abs=1e-6)
    assert intercept == pytest.approx(0.40, abs=1e-6)
    assert sigma == pytest.approx(0.0, abs=1e-9)


def test_fit_refuses_short_history():
    with pytest.raises(ValueError):
        fit_baseline(series([0.40, 0.41]))


def test_fit_ignores_low_coverage_periods():
    noisy = BASELINE + [Period("bad", 6, 0.02, valid_fraction=0.10)]
    slope, _, _ = fit_baseline(noisy)
    assert slope == pytest.approx(0.01, abs=1e-6)


def test_fit_is_robust_to_a_single_outlier():
    """Theil-Sen should shrug off one odd period; OLS would not."""
    with_outlier = series([0.40, 0.41, 0.42, 0.95, 0.44, 0.45])
    slope, _, _ = fit_baseline(with_outlier)
    assert slope == pytest.approx(0.01, abs=2e-3)


def test_band_widens_with_sigma():
    narrow = expected_band(0.01, 0.40, 0.01, 10)
    wide = expected_band(0.01, 0.40, 0.05, 10)
    assert narrow.expected == wide.expected
    assert (wide.high - wide.low) > (narrow.high - narrow.low)


# --- the firing case -------------------------------------------------------

def test_fires_on_two_consecutive_periods_below_the_band():
    baseline = series([0.40, 0.42, 0.41, 0.44, 0.43, 0.46])
    observed = series([0.30, 0.29], start=6)

    decision = evaluate(baseline, observed, evidence_ids=["rain_2026_07"])

    assert decision.fired
    assert decision.consecutive_periods == REQUIRED_CONSECUTIVE
    assert decision.breaching_period_ids == ["p6", "p7"]
    assert decision.observed_value == 0.29
    assert decision.deviation_abs < 0
    assert decision.deviation_pct < 0
    assert "rain_2026_07" in decision.evidence_ids
    assert any("consecutive periods" in r for r in decision.reasons)
    assert any("not a data-coverage artefact" in r for r in decision.reasons)


def test_fired_alert_carries_the_band_it_breached():
    baseline = series([0.40, 0.42, 0.41, 0.44, 0.43, 0.46])
    decision = evaluate(baseline, series([0.30, 0.29], start=6))
    assert decision.expected_low < decision.expected_value < decision.expected_high
    assert decision.observed_value < decision.expected_low


# --- the quiet cases -------------------------------------------------------

def test_does_not_fire_when_on_trajectory():
    baseline = series([0.40, 0.42, 0.41, 0.44, 0.43, 0.46])
    decision = evaluate(baseline, series([0.47, 0.48], start=6))
    assert not decision.fired
    assert decision.consecutive_periods == 0


def test_does_not_fire_on_a_single_bad_period():
    baseline = series([0.40, 0.42, 0.41, 0.44, 0.43, 0.46])
    decision = evaluate(baseline, series([0.29, 0.47], start=6))
    assert not decision.fired
    assert decision.consecutive_periods == 1
    assert any("longest run: 1" in r for r in decision.reasons)


def test_declines_to_fit_without_enough_baseline():
    decision = evaluate(series([0.40, 0.41]), series([0.10, 0.09], start=2))
    assert not decision.fired
    assert any("Baseline not established" in r for r in decision.reasons)


def test_near_zero_variance_baseline_does_not_produce_a_hair_trigger():
    """A perfectly straight baseline fits with sigma ~1e-17, not 0.0.

    Regression: an exact `sigma == 0` check let that through, the band
    collapsed to zero width, and two observations a fraction below the line
    fired an alert whose stated justification was a rounding error.
    """
    decision = evaluate(BASELINE, series([0.4499, 0.4599], start=6))
    assert not decision.fired
    assert any("near-zero residual spread" in r for r in decision.reasons)


def test_degenerate_baseline_is_detected_below_the_sigma_floor():
    _, _, sigma = fit_baseline(BASELINE)
    assert 0 <= sigma < MIN_RESIDUAL_SIGMA


def test_a_real_band_still_fires_normally():
    """The floor must not suppress genuine divergence on a noisy baseline."""
    noisy = series([0.40, 0.42, 0.41, 0.44, 0.43, 0.46])
    _, _, sigma = fit_baseline(noisy)
    assert sigma > MIN_RESIDUAL_SIGMA
    assert evaluate(noisy, series([0.30, 0.29], start=6)).fired


# --- bad data can never raise an alert -------------------------------------

def test_low_coverage_periods_cannot_trigger_an_alert():
    baseline = series([0.40, 0.42, 0.41, 0.44, 0.43, 0.46])
    cloudy = [
        Period("p6", 6, 0.10, valid_fraction=0.20),
        Period("p7", 7, 0.09, valid_fraction=0.15),
    ]
    decision = evaluate(baseline, cloudy)
    assert not decision.fired
    assert any("excluded for valid-pixel fraction" in r for r in decision.reasons)


def test_a_cloudy_period_breaks_the_run_rather_than_extending_it():
    """We cannot claim the project was behind in a month we could not see."""
    baseline = series([0.40, 0.42, 0.41, 0.44, 0.43, 0.46])
    observed = [
        Period("p6", 6, 0.29, valid_fraction=0.90),
        Period("p7", 7, 0.28, valid_fraction=0.10),   # unseen
        Period("p8", 8, 0.27, valid_fraction=0.90),
    ]
    decision = evaluate(baseline, observed)
    assert not decision.fired
    assert decision.consecutive_periods == 1


def test_missing_value_is_treated_as_unusable():
    baseline = series([0.40, 0.42, 0.41, 0.44, 0.43, 0.46])
    observed = [
        Period("p6", 6, None, valid_fraction=0.95),
        Period("p7", 7, 0.29, valid_fraction=0.95),
    ]
    decision = evaluate(baseline, observed)
    assert not decision.fired


def test_coverage_floor_is_inclusive():
    p = Period("edge", 0, 0.4, valid_fraction=MIN_VALID_FRACTION)
    assert p.usable


def test_a_tiny_dip_below_a_tight_band_is_not_divergence():
    """A very stable site narrows its own band; noise must not then fire it.

    This is the Mikoko Pamoja case. Its baseline fits so tightly that the band
    came out 0.022 wide, and a 0.05 dip that recovered within four months
    breached it for three periods. Statistically unusual, ecologically
    meaningless -- without an effect floor the rule punishes consistency.
    """
    baseline = [
        Period(period_id=f"2023-{m:02d}", index=i, value=0.900 + (0.009 if i % 2 else -0.009),
               valid_fraction=1.0)
        for i, m in enumerate(range(1, 13))
    ]
    # Sits below the band, but only by about 0.02: unusual for this site,
    # far too small to be a loss of cover.
    observed = [
        Period(period_id=f"2024-{m:02d}", index=12 + i, value=0.865, valid_fraction=1.0)
        for i, m in enumerate(range(1, 5))
    ]
    decision = evaluate(baseline, observed)
    assert decision.fired is False
    assert any("below the expected band" in r for r in decision.reasons)


def test_a_real_loss_still_fires_through_the_effect_floor():
    """The floor must not deafen the detector: a genuine collapse still fires."""
    baseline = [
        Period(period_id=f"2023-{m:02d}", index=i, value=0.900 + (0.009 if i % 2 else -0.009),
               valid_fraction=1.0)
        for i, m in enumerate(range(1, 13))
    ]
    observed = [
        Period(period_id=f"2024-{m:02d}", index=12 + i, value=0.560, valid_fraction=1.0)
        for i, m in enumerate(range(1, 5))
    ]
    decision = evaluate(baseline, observed)
    assert decision.fired is True
    assert decision.consecutive_periods >= REQUIRED_CONSECUTIVE
