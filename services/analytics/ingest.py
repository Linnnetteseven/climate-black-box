"""The pipeline: public satellite data in, defensible observations out.

This is the module that makes the evidence claim true. Everything it produces
carries the scene it came from, the fraction of pixels that survived masking,
and the processing version -- so any number on screen can be traced back to a
public Landsat scene and recomputed by someone who does not trust us.

Run it with ``make ingest``. The committed fixture is regenerated and diffed;
if the numbers move, the command says so loudly rather than quietly rewriting
history.

Design notes:

* **One scene per month, the least cloudy.** Compositing several scenes into a
  monthly median would be defensible too, but it is harder to explain on stage
  and the provenance stops being a single scene ID. Clarity wins.
* **Windowed reads.** We fetch only the pixels covering the polygon, not the
  whole 185 km scene. That turns a multi-gigabyte download into a few hundred
  kilobytes per band.
* **Failure is data.** A scene that cannot be read produces a recorded gap,
  not a silently missing month.
"""

from __future__ import annotations

import argparse
import json
import logging
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterable

import numpy as np

from services.analytics.ndvi import PROCESSING_VERSION, NDVISummary, summarise
from services.analytics.sources import (
    ERA5_RESOLUTION_NOTE,
    SceneRef,
    SourceUnavailable,
    fetch_rainfall,
    search_landsat,
)

log = logging.getLogger("cbb.ingest")

FIXTURE_PATH = Path("data/sample/observations_ndvi-v1.json")
SITE_PATH = Path("data/sample/kiambu_site.geojson")
SCENES_PATH = Path("data/manifests/scene_candidates.json")

PROJECT_ID = "kiambu-restoration-demo"
METRIC = "ndvi_mean"


@dataclass
class MonthlyObservation:
    """One month of evidence, with everything needed to defend it."""

    period_key: str
    period_start: str
    period_end: str
    observed_at: str | None
    metric: str
    value: float | None
    unit: str
    valid_pixel_fraction: float
    valid_pixels: int
    total_pixels: int
    cloud_cover_scene_pct: float | None
    source_dataset: str
    source_scene_id: str | None
    platform: str | None
    processing_version: str
    quality_flags: list[str]
    simulation_status: str
    precipitation_mm: float | None = None
    rainfall_source: str | None = None
    note: str | None = None


def _month_bounds(period_key: str) -> tuple[str, str]:
    year, month = (int(p) for p in period_key.split("-"))
    start = datetime(year, month, 1, tzinfo=timezone.utc)
    end_year, end_month = (year + 1, 1) if month == 12 else (year, month + 1)
    end = datetime(end_year, end_month, 1, tzinfo=timezone.utc)
    return start.isoformat().replace("+00:00", "Z"), end.isoformat().replace("+00:00", "Z")


def read_scene(scene: SceneRef, geometry: dict) -> NDVISummary:
    """Read the three bands we need, clipped to ``geometry``, and summarise.

    Raises ``SourceUnavailable`` when the scene cannot be read, so the caller
    can record an honest gap.
    """
    import planetary_computer
    import rasterio
    from rasterio.features import geometry_mask
    from rasterio.warp import transform_geom
    from rasterio.windows import from_bounds
    from shapely.geometry import shape

    bands: dict[str, np.ndarray] = {}
    polygon_mask: np.ndarray | None = None

    for name in ("red", "nir", "qa"):
        href = planetary_computer.sign(scene.assets[name])
        try:
            with rasterio.open(href) as src:
                # The polygon is WGS84; the scene is UTM. Move the geometry to
                # the raster's CRS rather than warping the raster.
                projected = transform_geom("EPSG:4326", src.crs, geometry)
                bounds = shape(projected).bounds
                window = from_bounds(*bounds, transform=src.transform)
                data = src.read(1, window=window)
                if data.size == 0:
                    raise SourceUnavailable(f"{scene.scene_id}: polygon outside scene extent")
                bands[name] = data

                if polygon_mask is None:
                    polygon_mask = ~geometry_mask(
                        [projected],
                        out_shape=data.shape,
                        transform=src.window_transform(window),
                        invert=False,
                    )
        except SourceUnavailable:
            raise
        except Exception as exc:
            raise SourceUnavailable(f"{scene.scene_id}: cannot read {name}: {exc}") from exc

    return summarise(bands["nir"], bands["red"], bands["qa"], polygon_mask=polygon_mask)


def pick_monthly_scenes(scenes: Iterable[SceneRef]) -> dict[str, SceneRef]:
    """Least-cloudy scene per month."""
    best: dict[str, SceneRef] = {}
    for scene in scenes:
        current = best.get(scene.period_key)
        if current is None or scene.cloud_cover_pct < current.cloud_cover_pct:
            best[scene.period_key] = scene
    return dict(sorted(best.items()))


def build_observations(
    geometry: dict,
    start: date,
    end: date,
    centroid: tuple[float, float],
    limit_months: int | None = None,
) -> list[MonthlyObservation]:
    scenes = search_landsat(_bbox(geometry), start, end)
    SCENES_PATH.parent.mkdir(parents=True, exist_ok=True)
    SCENES_PATH.write_text(
        json.dumps(
            [
                {
                    "scene_id": s.scene_id,
                    "datetime_utc": s.datetime_utc,
                    "cloud_cover_pct": s.cloud_cover_pct,
                    "platform": s.platform,
                }
                for s in scenes
            ],
            indent=2,
        ),
        encoding="utf-8",
    )
    log.info("wrote %s (%d scenes)", SCENES_PATH, len(scenes))

    monthly = pick_monthly_scenes(scenes)
    if limit_months:
        monthly = dict(list(monthly.items())[:limit_months])

    try:
        rainfall = {r.period_key: r.precipitation_mm for r in fetch_rainfall(*centroid, start, end)}
    except SourceUnavailable as exc:
        log.warning("rainfall unavailable, continuing without it: %s", exc)
        rainfall = {}

    observations: list[MonthlyObservation] = []
    for period_key, scene in monthly.items():
        period_start, period_end = _month_bounds(period_key)
        try:
            summary = read_scene(scene, geometry)
            flags = ["cloud_masked", "shadow_masked"]
            if summary.valid_fraction >= 0.75:
                flags.append("coverage_ok")
            else:
                flags.append("coverage_low")
            note = None
        except SourceUnavailable as exc:
            log.warning("gap at %s: %s", period_key, exc)
            summary = NDVISummary(mean=None, valid_pixels=0, total_pixels=0, valid_fraction=0.0)
            flags = ["read_failed"]
            note = str(exc)

        observations.append(
            MonthlyObservation(
                period_key=period_key,
                period_start=period_start,
                period_end=period_end,
                observed_at=scene.datetime_utc,
                metric=METRIC,
                value=round(summary.mean, 6) if summary.mean is not None else None,
                unit="index",
                valid_pixel_fraction=round(summary.valid_fraction, 6),
                valid_pixels=summary.valid_pixels,
                total_pixels=summary.total_pixels,
                cloud_cover_scene_pct=scene.cloud_cover_pct,
                source_dataset="Landsat Collection 2 Level-2 (landsat-c2-l2)",
                source_scene_id=scene.scene_id,
                platform=scene.platform,
                processing_version=PROCESSING_VERSION,
                quality_flags=flags,
                simulation_status="real",
                precipitation_mm=rainfall.get(period_key),
                rainfall_source=ERA5_RESOLUTION_NOTE if period_key in rainfall else None,
                note=note,
            )
        )
        usable = "gap" if summary.mean is None else f"ndvi={summary.mean:.4f}"
        log.info("  %s  %-34s %s  valid=%.0f%%",
                 period_key, scene.scene_id, usable, summary.valid_fraction * 100)

    return observations


def _bbox(geometry: dict) -> tuple[float, float, float, float]:
    coords = geometry["coordinates"][0]
    lons = [c[0] for c in coords]
    lats = [c[1] for c in coords]
    return (min(lons), min(lats), max(lons), max(lats))


def _centroid(geometry: dict) -> tuple[float, float]:
    coords = geometry["coordinates"][0]
    return (
        sum(c[1] for c in coords) / len(coords),   # lat
        sum(c[0] for c in coords) / len(coords),   # lon
    )


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("rasterio").setLevel(logging.ERROR)

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", type=date.fromisoformat, default=date(2023, 1, 1))
    parser.add_argument("--end", type=date.fromisoformat, default=date(2026, 9, 30))
    parser.add_argument("--limit-months", type=int, default=None,
                        help="process only the first N months (for a quick trial run)")
    parser.add_argument("--check", action="store_true",
                        help="regenerate and diff against the committed fixture "
                             "instead of overwriting it")
    args = parser.parse_args()

    geometry = json.loads(SITE_PATH.read_text(encoding="utf-8"))
    if geometry.get("type") == "Feature":
        geometry = geometry["geometry"]

    observations = build_observations(
        geometry, args.start, args.end, _centroid(geometry), args.limit_months
    )
    payload = {
        "project_id": PROJECT_ID,
        "metric": METRIC,
        "processing_version": PROCESSING_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "observations": [asdict(o) for o in observations],
    }

    usable = [o for o in observations if o.value is not None]
    log.info("\n%d months processed, %d usable, %d gaps",
             len(observations), len(usable), len(observations) - len(usable))

    if args.check and FIXTURE_PATH.exists():
        committed = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        same = _compare(committed["observations"], payload["observations"])
        if same:
            log.info("fixture reproduced exactly.")
            return 0
        log.error("FIXTURE DRIFT: regenerated numbers differ from the committed copy.")
        return 1

    FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
    FIXTURE_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    log.info("wrote %s", FIXTURE_PATH)
    return 0


def _compare(old: list[dict], new: list[dict]) -> bool:
    """Compare on the fields that are claims about the world.

    `generated_at` is expected to differ; nothing else is.
    """
    keys = ("period_key", "value", "valid_pixel_fraction", "source_scene_id", "processing_version")
    reduce = lambda rows: [{k: r.get(k) for k in keys} for r in rows]
    return reduce(old) == reduce(new)


if __name__ == "__main__":
    raise SystemExit(main())
