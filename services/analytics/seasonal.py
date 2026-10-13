"""Remove the season before looking for divergence.

Why this module exists, in one example from the real Kiambu series:

    2026-02 NDVI = 0.628   -- flagged as a 22% shortfall by a linear baseline
    2023-02 NDVI = 0.632   -- the same calendar month, two years earlier
    2026-01 NDVI = 0.699   -- *higher* than 2023-01 at 0.671

A straight line fitted to a short, cloud-biased baseline predicted 0.807 for
February 2026. Vegetation there simply does not reach 0.807 in February: the
site swings about 0.15 NDVI across the year, which is most of its entire
observed range of 0.23. The "shortfall" was the dry season.

So we deseasonalise first. Each observation is expressed as an **anomaly**
against the mean for that calendar month during the approved baseline window,
and divergence is judged on anomalies. A February is then compared with
Februaries, which is the only comparison that means anything.

Pooling the anomalies also fixes a sparse-data problem: with one or two usable
observations per calendar month there is no way to estimate a per-month
standard deviation, but the pooled anomaly residuals give a usable one.

Limitations, which belong in the UI and not just here:

* A calendar month absent from the baseline cannot be deseasonalised. Those
  periods are reported as such, never guessed at.
* Two or three years of baseline is a thin climatology. It captures the shape
  of the year, not a long-run normal.
* This removes the *average* season. An unusually early or late rainy season
  still shows up as an anomaly, which is why rainfall context sits beside the
  alert rather than being silently regressed out.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from statistics import mean
from typing import Sequence

from services.analytics.alerts import Period

#: Calendar months needing at least this many usable baseline observations
#: before we trust their climatological mean.
MIN_SAMPLES_PER_MONTH = 1


@dataclass(frozen=True)
class Climatology:
    """Mean metric value per calendar month, over the baseline window."""

    by_month: dict[str, float]
    samples: dict[str, int]
    source_periods: list[str]

    def covers(self, period_id: str) -> bool:
        return _month_of(period_id) in self.by_month

    def expected_for(self, period_id: str) -> float | None:
        return self.by_month.get(_month_of(period_id))

    @property
    def seasonal_swing(self) -> float:
        """Spread between the greenest and brownest months, in metric units."""
        if not self.by_month:
            return 0.0
        return max(self.by_month.values()) - min(self.by_month.values())


def _month_of(period_id: str) -> str:
    """'2026-02' -> '02'. Period ids are monthly buckets."""
    return period_id.split("-")[1] if "-" in period_id else period_id


def build_climatology(baseline: Sequence[Period]) -> Climatology:
    """Mean per calendar month across the usable baseline periods."""
    buckets: dict[str, list[float]] = {}
    used: list[str] = []
    for period in baseline:
        if not period.usable:
            continue
        buckets.setdefault(_month_of(period.period_id), []).append(period.value)  # type: ignore[arg-type]
        used.append(period.period_id)

    by_month = {
        month: mean(values)
        for month, values in buckets.items()
        if len(values) >= MIN_SAMPLES_PER_MONTH
    }
    return Climatology(
        by_month=by_month,
        samples={m: len(v) for m, v in buckets.items()},
        source_periods=sorted(used),
    )


def deseasonalise(periods: Sequence[Period], climatology: Climatology) -> list[Period]:
    """Express each period as an anomaly against its calendar-month mean.

    A period whose calendar month is missing from the climatology comes back
    with ``value=None`` -- it is not comparable, and the alert engine already
    treats a missing value as unusable. We do not invent a seasonal correction
    we cannot support.
    """
    out: list[Period] = []
    for period in periods:
        expected = climatology.expected_for(period.period_id)
        if period.value is None or expected is None:
            out.append(replace(period, value=None))
        else:
            out.append(replace(period, value=period.value - expected))
    return out


def describe(climatology: Climatology) -> str:
    """One sentence for the UI, so the method is visible rather than implied."""
    months = len(climatology.by_month)
    return (
        f"Seasonally adjusted: each month is compared with the same calendar "
        f"month in the approved baseline window ({months} of 12 months have "
        f"baseline coverage; seasonal swing {climatology.seasonal_swing:.3f} "
        f"NDVI). Periods whose calendar month has no baseline coverage are "
        f"excluded rather than estimated."
    )
