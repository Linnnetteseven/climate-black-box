"""Find a site that has genuinely declined -- not one that merely looks like it.

Kiambu came back healthy once seasonal adjustment was applied, which is the
right answer but leaves the demo with no divergence to investigate. Rather
than fabricate one, we go looking for a real one.

Method, deliberately the same one the product uses:

  1. Pull a sparse NDVI series per candidate site (a few months per year, so a
     scan of several sites costs minutes rather than hours).
  2. Build a calendar-month climatology from the baseline years.
  3. Express the recent years as anomalies against it.
  4. Rank by mean recent anomaly, and report whether the production alert rule
     would actually fire.

A site is only a candidate if the rule fires on it for the real reason. If
nothing qualifies we say so and keep Kiambu as a healthy control, rather than
widening thresholds until something trips.

Candidates are Kenyan forest blocks with documented degradation pressure, plus
Kiambu itself as a control so the scan's own output can be sanity-checked.
"""

from __future__ import annotations

import json
import logging
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.analytics.alerts import Period, evaluate  # noqa: E402
from services.analytics.ingest import read_scene  # noqa: E402
from services.analytics.seasonal import build_climatology, deseasonalise  # noqa: E402
from services.analytics.sources import SourceUnavailable, search_landsat  # noqa: E402

log = logging.getLogger("cbb.scan")

#: Months sampled per year. Spread across wet and dry so the climatology has
#: shape, but sparse enough that six sites scan in minutes.
SAMPLE_MONTHS = {"01", "03", "07", "09", "11"}

BASELINE_BEFORE = "2025"   # period ids below this form the climatology


@dataclass(frozen=True)
class Candidate:
    key: str
    name: str
    note: str
    lon: float
    lat: float
    half: float = 0.009   # ~1 km box half-width in degrees

    def geometry(self) -> dict:
        w, e = self.lon - self.half, self.lon + self.half
        s, n = self.lat - self.half, self.lat + self.half
        return {
            "type": "Polygon",
            "coordinates": [[[w, s], [e, s], [e, n], [w, n], [w, s]]],
        }


CANDIDATES = [
    Candidate("kiambu-control", "Kiambu highlands (control)",
              "the existing project site; expected healthy", 36.8385, -1.1125),
    Candidate("mau-eastern", "Eastern Mau Forest",
              "Kenya's most documented forest-loss complex", 35.9300, -0.4700),
    Candidate("mau-transmara", "Transmara / South-West Mau",
              "excision and charcoal pressure", 35.2400, -0.9300),
    Candidate("cherangany", "Cherangany Hills",
              "water-tower forest under encroachment", 35.4500, 1.0500),
    Candidate("embobut", "Embobut Forest",
              "settlement and clearance pressure", 35.4200, 0.9800),
    Candidate("kakamega", "Kakamega Forest edge",
              "fragmentation at the forest margin", 34.8700, 0.3200),
]


def series_for(candidate: Candidate, start: date, end: date) -> list[Period]:
    geometry = candidate.geometry()
    bbox = (
        candidate.lon - candidate.half, candidate.lat - candidate.half,
        candidate.lon + candidate.half, candidate.lat + candidate.half,
    )
    try:
        scenes = search_landsat(bbox, start, end)
    except SourceUnavailable as exc:
        log.warning("  %s: STAC search failed: %s", candidate.key, exc)
        return []

    best: dict[str, object] = {}
    for scene in scenes:
        if scene.period_key[5:7] not in SAMPLE_MONTHS:
            continue
        current = best.get(scene.period_key)
        if current is None or scene.cloud_cover_pct < current.cloud_cover_pct:  # type: ignore[union-attr]
            best[scene.period_key] = scene

    periods: list[Period] = []
    for index, (period_key, scene) in enumerate(sorted(best.items())):
        try:
            summary = read_scene(scene, geometry)   # type: ignore[arg-type]
            periods.append(Period(period_key, index, summary.mean, summary.valid_fraction))
        except SourceUnavailable:
            periods.append(Period(period_key, index, None, 0.0))
    return periods


def assess(candidate: Candidate, periods: list[Period]) -> dict:
    baseline = [p for p in periods if p.period_id < BASELINE_BEFORE]
    observed = [p for p in periods if p.period_id >= BASELINE_BEFORE]

    result = {
        "key": candidate.key,
        "name": candidate.name,
        "note": candidate.note,
        "lon": candidate.lon,
        "lat": candidate.lat,
        "periods_total": len(periods),
        "baseline_usable": sum(p.usable for p in baseline),
        "observed_usable": sum(p.usable for p in observed),
        "fires": False,
        "mean_anomaly": None,
        "consecutive": 0,
        "reasons": [],
    }
    if result["baseline_usable"] < 4 or result["observed_usable"] < 2:
        result["reasons"] = ["insufficient usable coverage to judge"]
        return result

    clim = build_climatology(baseline)
    anomalies = deseasonalise(observed, clim)
    usable = [p.value for p in anomalies if p.usable]
    result["mean_anomaly"] = round(sum(usable) / len(usable), 4) if usable else None
    result["seasonal_swing"] = round(clim.seasonal_swing, 4)

    decision = evaluate(deseasonalise(baseline, clim), anomalies)
    result["fires"] = decision.fired
    result["consecutive"] = decision.consecutive_periods
    result["reasons"] = decision.reasons
    if decision.fired:
        result["observed_value"] = round(decision.observed_value, 4)
        result["expected_low"] = round(decision.expected_low, 4)
        result["deviation_pct"] = round(decision.deviation_pct, 1)
    return result


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    for noisy in ("httpx", "rasterio", "pystac_client", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.ERROR)

    start, end = date(2023, 1, 1), date(2026, 9, 30)
    results = []
    for candidate in CANDIDATES:
        log.info("\n=== %s (%s)", candidate.name, candidate.note)
        periods = series_for(candidate, start, end)
        usable = [p for p in periods if p.usable]
        log.info("  %d periods, %d usable", len(periods), len(usable))
        result = assess(candidate, periods)
        results.append(result)
        verdict = "FIRES" if result["fires"] else "quiet"
        log.info("  mean anomaly %s | %s | run=%d",
                 result["mean_anomaly"], verdict, result["consecutive"])

    out = Path("data/manifests/site_scan.json")
    out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    log.info("\nwrote %s", out)

    firing = [r for r in results if r["fires"] and r["key"] != "kiambu-control"]
    log.info("\n=== RANKED ===")
    for r in sorted(results, key=lambda r: (r["mean_anomaly"] is None, r["mean_anomaly"] or 0)):
        log.info("  %-16s anomaly=%-8s fires=%-5s  %s",
                 r["key"], r["mean_anomaly"], r["fires"], r["name"])
    log.info("\n%d candidate site(s) fire the production rule.", len(firing))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
