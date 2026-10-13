"""Pre/post comparison around an intervention.

This is the beat where it is easiest to say something indefensible, so the
module is built to make the indefensible thing hard to say.

What it computes: the mean seasonally-adjusted anomaly before an intervention
and after it, over usable periods only, with the count behind each so a reader
can see how thin the evidence is.

What it refuses to compute: anything resembling an effect size or an
attribution. A change after an intervention is not evidence the intervention
caused it -- weather moved, the season moved, and at these sample sizes almost
anything could. The `causal_note` is part of the return value rather than a
caption someone might drop, and `sufficient` is False whenever there is too
little post-intervention data to say anything at all.
"""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean, pstdev
from typing import Sequence

from services.analytics.alerts import Period

#: Below this many usable periods on either side, we decline to compare.
#: Two points either side of a line is not a trend, and presenting it as one
#: would be the single most misleading thing this system could do.
MIN_PERIODS_PER_SIDE = 2


@dataclass(frozen=True)
class TrendComparison:
    pre_mean: float | None
    post_mean: float | None
    pre_periods: int
    post_periods: int
    change_abs: float | None
    pre_spread: float | None
    post_spread: float | None
    sufficient: bool
    direction: str          # improving | declining | unchanged | unknown
    note: str

    @property
    def causal_note(self) -> str:
        return (
            "A change after an intervention is correlation, not proof of cause. "
            "Rainfall, season and measurement coverage all moved over the same "
            "period. Establishing attribution would need a comparable untreated "
            "area observed over the same window."
        )


def compare(
    anomalies: Sequence[Period],
    intervention_period: str,
) -> TrendComparison:
    """Compare usable anomalies before and after ``intervention_period``.

    ``anomalies`` must already be seasonally adjusted -- comparing raw NDVI
    across an intervention date would mostly measure the calendar.
    """
    usable = [p for p in anomalies if p.usable]
    before = [p.value for p in usable if p.period_id < intervention_period]
    after = [p.value for p in usable if p.period_id > intervention_period]

    if len(before) < MIN_PERIODS_PER_SIDE or len(after) < MIN_PERIODS_PER_SIDE:
        return TrendComparison(
            pre_mean=mean(before) if before else None,
            post_mean=mean(after) if after else None,
            pre_periods=len(before), post_periods=len(after),
            change_abs=None, pre_spread=None, post_spread=None,
            sufficient=False, direction="unknown",
            note=(
                f"Not enough usable evidence to compare: {len(before)} period(s) before "
                f"and {len(after)} after, against a minimum of {MIN_PERIODS_PER_SIDE} "
                "each. Re-measurement is pending rather than negative."
            ),
        )

    pre, post = mean(before), mean(after)
    change = post - pre
    pre_spread = pstdev(before) if len(before) > 1 else 0.0
    post_spread = pstdev(after) if len(after) > 1 else 0.0

    # "Moved less than the noise either side of it" is not a change worth
    # reporting as one.
    noise = max(pre_spread, post_spread)
    if abs(change) <= noise:
        direction = "unchanged"
        note = (
            f"The mean anomaly moved by {change:+.4f}, which is within the spread of the "
            f"observations themselves ({noise:.4f}). On this evidence the trajectory has "
            "not measurably changed."
        )
    else:
        direction = "improving" if change > 0 else "declining"
        note = (
            f"The mean anomaly moved from {pre:+.4f} over {len(before)} period(s) to "
            f"{post:+.4f} over {len(after)}, a change of {change:+.4f}. That is larger "
            f"than the spread within either group ({noise:.4f})."
        )

    return TrendComparison(
        pre_mean=pre, post_mean=post,
        pre_periods=len(before), post_periods=len(after),
        change_abs=change, pre_spread=pre_spread, post_spread=post_spread,
        sufficient=True, direction=direction, note=note,
    )


def recommendation(trend: TrendComparison, alert_open: bool) -> tuple[str, str]:
    """The decision beat: what a funder should do next, and how sure we are.

    Deliberately conservative. The honest recommendation after one intervention
    and a handful of observations is almost always "keep measuring", and saying
    so is more useful than manufacturing a verdict.
    """
    if not trend.sufficient:
        return (
            "Continue monitoring. Do not draw a conclusion yet.",
            "There is not enough post-intervention evidence to judge. The next two "
            "usable observations will be the first that can support any finding.",
        )
    if trend.direction == "improving":
        return (
            "Keep the intervention in place and re-assess after two more observations.",
            "The indicator has moved in the intended direction by more than the "
            "measurement spread. That is encouraging and not yet conclusive: it does "
            "not establish that the intervention caused it.",
        )
    if trend.direction == "declining":
        return (
            "Escalate. Commission field verification before further spending.",
            "The indicator has continued to move away from the commitment despite the "
            "recorded intervention. Remote sensing cannot say why; someone needs to "
            "visit the site.",
        )
    return (
        "Hold, and extend the observation window.",
        "No measurable change either way. With this many periods, a real effect of "
        "modest size would not yet be visible, so absence of change is not evidence "
        "the intervention failed.",
    )
