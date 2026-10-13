"""Divergence detection: when has a project fallen behind its commitment?

The rule is deliberately simple and completely explainable. A funder has to
be able to read why an alert fired and disagree with it on the merits. That
rules out anything that produces a score nobody can defend in a sentence.

The rule, in one sentence: fit a robust straight line to the approved
baseline period, project it forward with a band of +/- 1.5 residual sigma,
and raise a review alert when the observed mean sits below the band for two
consecutive periods that both have trustworthy pixel coverage.

Three guards keep it honest:

* **Coverage.** A period whose valid-pixel fraction is below the floor is not
  evidence of anything. It is excluded from the fit and can never trigger an
  alert -- otherwise a cloudy month reads as a vegetation collapse.
* **Persistence.** One bad period is noise. Two consecutive is a signal worth
  a human's time. This is the single biggest false-positive killer.
* **Minimum history.** Below a handful of baseline periods the band is
  meaningless, so we decline to fit rather than invent confidence.

An alert means "this deserves investigation". It never means the project
failed, and it never asserts a cause.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Sequence

import numpy as np

RULE_VERSION = "divergence-v1"
METHOD = "robust linear baseline, residual sigma band, 2 consecutive periods"

#: Below this valid-pixel fraction a period is not usable as evidence.
MIN_VALID_FRACTION = 0.75
#: Fewer baseline periods than this and we decline to fit a trajectory.
MIN_BASELINE_PERIODS = 4
#: Half-width of the expected band, in residual standard deviations.
BAND_SIGMA = 1.5
#: Consecutive breaching periods required before an alert is raised.
REQUIRED_CONSECUTIVE = 2
#: Below this residual sigma the baseline is treated as degenerate.
#:
#: Exact float arithmetic almost never yields a sigma of exactly zero: a
#: perfectly straight baseline fits with a residual sigma around 1e-17, which
#: is not zero but produces a band of zero practical width. Everything then
#: "breaches" it, and the engine fires on a rounding error -- an alert whose
#: whole justification is that an observation sat 0.0001 below a line.
#:
#: This floor is in metric units and is tuned for NDVI, where period-to-period
#: measurement noise alone is comfortably above 0.005. A different metric needs
#: a different floor; it is not dimensionless.
MIN_RESIDUAL_SIGMA = 0.005


@dataclass(frozen=True)
class Period:
    """One observation period, as the alert engine sees it."""

    period_id: str
    index: int               # ordinal position in the series, 0-based
    value: float | None      # the metric mean, None when unusable
    valid_fraction: float

    @property
    def usable(self) -> bool:
        return self.value is not None and self.valid_fraction >= MIN_VALID_FRACTION


@dataclass(frozen=True)
class Band:
    expected: float
    low: float
    high: float


@dataclass(frozen=True)
class AlertDecision:
    """The outcome, whether or not it fired, with the reasoning attached."""

    fired: bool
    rule_version: str = RULE_VERSION
    method: str = METHOD
    reasons: list[str] = field(default_factory=list)
    breaching_period_ids: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    observed_value: float | None = None
    expected_value: float | None = None
    expected_low: float | None = None
    expected_high: float | None = None
    consecutive_periods: int = 0
    suppressed_by_coverage: bool = False

    @property
    def deviation_abs(self) -> float | None:
        if self.observed_value is None or self.expected_value is None:
            return None
        return self.observed_value - self.expected_value

    @property
    def deviation_pct(self) -> float | None:
        if self.deviation_abs is None or not self.expected_value:
            return None
        return 100.0 * self.deviation_abs / abs(self.expected_value)


def _theil_sen(x: np.ndarray, y: np.ndarray) -> tuple[float, float]:
    """Theil-Sen slope and intercept.

    Robust to a couple of odd periods in a short series, which ordinary least
    squares is not. With ten-ish points one bad month should not be able to
    swing the baseline, and with OLS it can.
    """
    slopes = []
    for i in range(len(x)):
        for j in range(i + 1, len(x)):
            if x[j] != x[i]:
                slopes.append((y[j] - y[i]) / (x[j] - x[i]))
    slope = float(np.median(slopes)) if slopes else 0.0
    intercept = float(np.median(y - slope * x))
    return slope, intercept


def fit_baseline(baseline: Sequence[Period]) -> tuple[float, float, float]:
    """Return (slope, intercept, residual_sigma) over the usable periods.

    Raises ``ValueError`` when there is not enough usable history, rather
    than returning a confident-looking line nobody should trust.
    """
    usable = [p for p in baseline if p.usable]
    if len(usable) < MIN_BASELINE_PERIODS:
        raise ValueError(
            f"need at least {MIN_BASELINE_PERIODS} usable baseline periods, got {len(usable)}"
        )
    x = np.array([p.index for p in usable], dtype=float)
    y = np.array([p.value for p in usable], dtype=float)
    slope, intercept = _theil_sen(x, y)
    residuals = y - (slope * x + intercept)
    # ddof=1: we are estimating sigma from a sample, and the series is short.
    sigma = float(np.std(residuals, ddof=1)) if len(residuals) > 1 else 0.0
    return slope, intercept, sigma


def expected_band(slope: float, intercept: float, sigma: float, index: int) -> Band:
    expected = slope * index + intercept
    half = BAND_SIGMA * sigma
    return Band(expected=expected, low=expected - half, high=expected + half)


def evaluate(
    baseline: Sequence[Period],
    observed: Sequence[Period],
    evidence_ids: Iterable[str] = (),
) -> AlertDecision:
    """Decide whether the observed periods diverge from the baseline."""
    evidence = list(evidence_ids)

    try:
        slope, intercept, sigma = fit_baseline(baseline)
    except ValueError as exc:
        return AlertDecision(
            fired=False,
            reasons=[f"Baseline not established: {exc}."],
            evidence_ids=evidence,
        )

    if sigma < MIN_RESIDUAL_SIGMA:
        return AlertDecision(
            fired=False,
            reasons=[
                f"Baseline has near-zero residual spread (sigma={sigma:.2e}, floor="
                f"{MIN_RESIDUAL_SIGMA}), so no meaningful band can be drawn and any "
                "deviation would breach it. Treat the trajectory as unvalidated "
                "rather than firing on rounding error."
            ],
            evidence_ids=evidence,
        )

    unusable = [p for p in observed if not p.usable]
    run: list[tuple[Period, Band]] = []
    best: list[tuple[Period, Band]] = []

    for period in observed:
        if not period.usable:
            # A low-coverage period breaks the run rather than extending it:
            # we cannot say the project was behind in a month we could not see.
            run = []
            continue
        band = expected_band(slope, intercept, sigma, period.index)
        if period.value < band.low:
            run.append((period, band))
            if len(run) > len(best):
                best = list(run)
        else:
            run = []

    reasons: list[str] = []
    if unusable:
        reasons.append(
            f"{len(unusable)} period(s) excluded for valid-pixel fraction below "
            f"{MIN_VALID_FRACTION:.0%}: {', '.join(p.period_id for p in unusable)}."
        )

    if len(best) < REQUIRED_CONSECUTIVE:
        reasons.insert(
            0,
            f"No run of {REQUIRED_CONSECUTIVE} consecutive usable periods below the "
            f"expected band (longest run: {len(best)}).",
        )
        return AlertDecision(
            fired=False,
            reasons=reasons,
            consecutive_periods=len(best),
            suppressed_by_coverage=bool(unusable) and len(best) > 0,
            evidence_ids=evidence,
        )

    last_period, last_band = best[-1]
    reasons.insert(
        0,
        f"Observed {last_period.period_id} at {last_period.value:.3f}, below the "
        f"expected band [{last_band.low:.3f}, {last_band.high:.3f}] around "
        f"{last_band.expected:.3f}, for {len(best)} consecutive periods.",
    )
    reasons.insert(
        1,
        f"All {len(best)} breaching periods had valid-pixel fraction at or above "
        f"{MIN_VALID_FRACTION:.0%}, so this is not a data-coverage artefact.",
    )

    return AlertDecision(
        fired=True,
        reasons=reasons,
        breaching_period_ids=[p.period_id for p, _ in best],
        evidence_ids=evidence + [p.period_id for p, _ in best],
        observed_value=last_period.value,
        expected_value=last_band.expected,
        expected_low=last_band.low,
        expected_high=last_band.high,
        consecutive_periods=len(best),
    )
