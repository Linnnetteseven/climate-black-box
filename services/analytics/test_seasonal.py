"""Tests for seasonal adjustment.

The regression these guard against is real and was caught on live Landsat
data: a linear baseline fitted to a short, cloud-biased window predicted an
NDVI of 0.807 for February 2026 at a site whose Februaries run about 0.63,
and raised a 22% "shortfall" that was simply the dry season.
"""

import pytest

from services.analytics.alerts import Period, evaluate
from services.analytics.seasonal import (
    build_climatology,
    deseasonalise,
    describe,
)


def p(period_id, index, value, valid=0.9):
    return Period(period_id, index, value, valid)


# A site with a strong season: greener mid-year, browner in Feb, and no
# underlying trend at all.
SEASON = {"01": 0.70, "02": 0.63, "03": 0.60, "06": 0.75, "09": 0.62, "12": 0.72}


#: Small year-to-year wobble, so the deseasonalised baseline has a real
#: residual spread. A noiseless fixture would sit under the degenerate-baseline
#: floor and the engine would (correctly) decline to judge anything.
NOISE = {"01": +0.012, "02": -0.009, "03": +0.015, "06": -0.011, "09": +0.008, "12": -0.014}


def _year(year, index_base, offset=0.0, valid=0.9, noisy=False):
    return [
        p(f"{year}-{m}", index_base + i, v + offset + (NOISE[m] if noisy else 0.0), valid)
        for i, (m, v) in enumerate(sorted(SEASON.items()))
    ]


BASELINE = _year(2023, 0) + _year(2024, 10, noisy=True)


def test_climatology_recovers_the_seasonal_shape():
    clim = build_climatology(BASELINE)
    for month, expected in SEASON.items():
        # mean of the clean year and the wobbled one
        assert clim.by_month[month] == pytest.approx(expected + NOISE[month] / 2, abs=1e-9)


def test_climatology_reports_its_own_coverage():
    clim = build_climatology(BASELINE)
    assert set(clim.by_month) == set(SEASON)
    assert all(count == 2 for count in clim.samples.values())
    # swing is between the greenest and brownest month means, noise included
    means = [SEASON[m] + NOISE[m] / 2 for m in SEASON]
    assert clim.seasonal_swing == pytest.approx(max(means) - min(means))


def test_low_coverage_periods_do_not_pollute_the_climatology():
    clean = build_climatology(BASELINE).by_month["02"]
    polluted = build_climatology(BASELINE + [p("2024-02", 99, 0.10, valid=0.05)])
    assert polluted.by_month["02"] == pytest.approx(clean, abs=1e-9)


def test_deseasonalising_a_normal_year_gives_near_zero_anomalies():
    clim = build_climatology(BASELINE)
    anomalies = deseasonalise(_year(2026, 20), clim)
    for period in anomalies:
        # within half the year-to-year wobble, i.e. indistinguishable from normal
        assert abs(period.value) < 0.01


def test_a_month_absent_from_the_baseline_is_excluded_not_guessed():
    clim = build_climatology(BASELINE)
    # July never appears in the baseline.
    out = deseasonalise([p("2026-07", 30, 0.71)], clim)
    assert out[0].value is None
    assert not out[0].usable


def test_the_seasonal_false_positive_is_removed():
    """The regression, in miniature.

    Cloud decides which months survive QA, so a baseline can end up sampling
    brown months early and green months late. A straight line through that
    reads as a rising trend and extrapolates to a value the site never reaches
    in its brown season -- which is exactly how the real Kiambu series produced
    a 22% "shortfall" in a February that matched its own baseline Februaries.
    """
    # Brown months in the first year, green months in the second.
    cloud_biased = [
        p("2023-02", 0, SEASON["02"]), p("2023-03", 1, SEASON["03"]),
        p("2023-09", 2, SEASON["09"]), p("2024-01", 3, SEASON["01"]),
        p("2024-06", 4, SEASON["06"]), p("2024-12", 5, SEASON["12"]),
    ]
    # An utterly normal February, on its own seasonal norm.
    observed = [p("2026-02", 10, SEASON["02"]), p("2026-03", 11, SEASON["03"])]

    naive = evaluate(cloud_biased, observed)
    assert naive.fired, "the unadjusted rule should be fooled -- that is the bug"

    clim = build_climatology(cloud_biased + BASELINE)
    adjusted = evaluate(
        deseasonalise(cloud_biased + BASELINE, clim), deseasonalise(observed, clim)
    )
    assert not adjusted.fired, "seasonal adjustment must remove the false positive"


def test_a_real_decline_still_fires_after_adjustment():
    """Adjustment must not blind the detector to genuine divergence."""
    clim = build_climatology(BASELINE)
    collapsed = [
        p("2026-02", 20, SEASON["02"] - 0.25),
        p("2026-03", 21, SEASON["03"] - 0.25),
    ]
    decision = evaluate(deseasonalise(BASELINE, clim), deseasonalise(collapsed, clim))
    assert decision.fired
    assert decision.consecutive_periods == 2
    assert decision.observed_value < decision.expected_low


def test_describe_states_the_method_and_its_coverage():
    text = describe(build_climatology(BASELINE))
    assert "same calendar month" in text
    assert "6 of 12" in text
