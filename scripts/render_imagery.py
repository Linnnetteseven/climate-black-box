"""Render the cinematic backdrop from our own Landsat scenes.

Everything on this page that looks like a photograph of a forest IS the
project's evidence, rendered from the same public-domain Landsat Collection 2
scenes the numbers come from. That matters for three reasons:

  1. Licensing. USGS Landsat is public domain. There is no stock photograph to
     attribute and nothing to take down.
  2. Honesty. A stock image of "a forest" would be decoration pretending to be
     evidence. These pixels are the evidence.
  3. It is a better story. "This is the actual satellite view of the site, and
     here is the same view three years later" is stronger than any photograph
     we could licence.

Outputs go to apps/web/public/evidence/ as WebP, sized for full-bleed use.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.analytics.ndvi import (  # noqa: E402
    SR_OFFSET, SR_SCALE, ndvi, qa_mask, scale_reflectance,
)
from services.analytics.sources import SceneRef, search_landsat  # noqa: E402

log = logging.getLogger("cbb.imagery")
OUT_DIR = Path("apps/web/public/evidence")


@dataclass
class Frame:
    name: str
    scene_id: str
    period: str
    centre: tuple[float, float]   # lon, lat
    half_deg: float               # half-width of the crop


def _window_read(href: str, centre: tuple[float, float], half: float):
    """Read one band cropped to a lon/lat box around ``centre``."""
    import planetary_computer
    import rasterio
    from rasterio.warp import transform_bounds
    from rasterio.windows import from_bounds

    with rasterio.open(planetary_computer.sign(href)) as src:
        lon, lat = centre
        bounds = transform_bounds(
            "EPSG:4326", src.crs,
            lon - half, lat - half, lon + half, lat + half,
        )
        window = from_bounds(*bounds, transform=src.transform)
        return src.read(1, window=window)


def true_colour(scene: SceneRef, centre, half) -> np.ndarray:
    """An RGB composite that keeps its colour balance.

    The obvious approach -- stretch each band independently to its own
    percentiles -- destroys colour. Over forest the blue band is dark and
    narrow, so an independent stretch amplifies its noise and the whole frame
    comes out magenta. (It did, the first time.)

    So: one shared stretch across all three bands preserves their relative
    values, and saturation and gamma are applied afterwards as deliberate
    choices rather than as an accident of per-band scaling.
    """
    bands = []
    for key in ("red", "green", "blue"):
        href = scene.assets.get(key)
        if href is None:
            raise RuntimeError(f"{scene.scene_id}: no {key} band")
        bands.append(scale_reflectance(_window_read(href, centre, half)))
    rgb = np.dstack(bands)

    finite = rgb[np.isfinite(rgb)]
    if finite.size == 0:
        return np.zeros_like(rgb)
    # Shared across channels: this is the line that keeps the colour honest.
    lo, hi = np.percentile(finite, [2.0, 96.0])
    rgb = np.clip((rgb - lo) / max(hi - lo, 1e-6), 0, 1)

    # Vegetation under a shared stretch is accurate but muted. A modest
    # saturation lift makes it readable on a dark page without inventing hues.
    grey = rgb.mean(axis=2, keepdims=True)
    rgb = np.clip(grey + (rgb - grey) * 1.45, 0, 1)
    return np.clip(rgb ** 0.80, 0, 1)


#: Brown -> amber -> green. Diverging would imply a meaningful midpoint; this
#: is a magnitude, so it is a single progression from bare to vegetated.
NDVI_STOPS = np.array([
    [0.38, 0.27, 0.18],   # bare earth
    [0.60, 0.47, 0.24],
    [0.76, 0.66, 0.30],
    [0.55, 0.65, 0.30],
    [0.22, 0.52, 0.32],
    [0.07, 0.35, 0.24],   # dense canopy
])


def ndvi_image(scene: SceneRef, centre, half) -> tuple[np.ndarray, float]:
    red = _window_read(scene.assets["red"], centre, half)
    nir = _window_read(scene.assets["nir"], centre, half)
    qa = _window_read(scene.assets["qa"], centre, half)

    values = ndvi(scale_reflectance(nir), scale_reflectance(red))
    valid = qa_mask(qa) & np.isfinite(values)

    # Map 0.1..0.85 across the ramp: below 0.1 is bare or water, above 0.85
    # does not occur here, and stretching to the full -1..1 wastes the ramp.
    t = np.clip((values - 0.10) / 0.75, 0, 1)
    idx = t * (len(NDVI_STOPS) - 1)
    lo = np.clip(np.floor(idx).astype(int), 0, len(NDVI_STOPS) - 2)
    frac = (idx - lo)[..., None]
    rgb = NDVI_STOPS[lo] * (1 - frac) + NDVI_STOPS[lo + 1] * frac

    # Masked pixels read as deep slate so cloud is visibly absent data rather
    # than being coloured as if it were a measurement.
    rgb[~valid] = [0.07, 0.09, 0.11]
    mean = float(values[valid].mean()) if valid.any() else float("nan")
    return np.clip(rgb, 0, 1), mean


def save(rgb: np.ndarray, path: Path, width: int = 1800) -> None:
    from PIL import Image

    img = Image.fromarray((rgb * 255).astype(np.uint8))
    if img.width < 8 or img.height < 8:
        raise RuntimeError(f"crop too small: {img.size}")
    scale = width / img.width
    img = img.resize((width, max(1, int(img.height * scale))), Image.LANCZOS)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "WEBP", quality=82, method=6)
    log.info("  wrote %s (%dx%d, %.0f kB)", path, img.width, img.height,
             path.stat().st_size / 1024)


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    for noisy in ("rasterio", "pystac_client", "httpx", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.ERROR)

    ap = argparse.ArgumentParser()
    ap.add_argument("--site", default="mau", choices=["mau", "kiambu"])
    args = ap.parse_args()

    sites = {
        "mau": dict(centre=(35.2400, -0.9300), wide=0.12, close=0.03,
                    before="2023-11", after="2026-09"),
        "kiambu": dict(centre=(36.8385, -1.1125), wide=0.12, close=0.03,
                       before="2023-01", after="2026-09"),
    }
    site = sites[args.site]
    lon, lat = site["centre"]

    scenes = search_landsat(
        (lon - 0.05, lat - 0.05, lon + 0.05, lat + 0.05),
        date(2023, 1, 1), date(2026, 9, 30), max_cloud_pct=25.0,
    )
    by_period: dict[str, SceneRef] = {}
    for s in scenes:
        cur = by_period.get(s.period_key)
        if cur is None or s.cloud_cover_pct < cur.cloud_cover_pct:
            by_period[s.period_key] = s

    def pick(period: str) -> SceneRef | None:
        """The named month, or the clearest scene in the same season nearby.

        Insisting on an exact month throws away the story when that month
        happened to be cloudy, and a neighbouring month in the same season is
        a fair comparison -- the whole analysis is seasonally adjusted anyway.
        """
        if period in by_period:
            return by_period[period]
        year, month = (int(p) for p in period.split("-"))
        nearby = [
            s for key, s in by_period.items()
            if abs(int(key[:4]) - year) <= 1 and abs(int(key[5:7]) - month) <= 1
        ]
        if not nearby:
            return None
        best = min(nearby, key=lambda s: s.cloud_cover_pct)
        log.info("  %s unavailable; using %s instead", period, best.period_key)
        return best

    chosen: dict[str, SceneRef] = {}
    for label in ("before", "after"):
        period = site[label]
        scene = pick(period)
        if scene is None:
            log.warning("no low-cloud scene near %s; skipping", period)
            continue
        chosen[label] = scene
        log.info("%s (%s) %s cloud=%.1f%%", label, period, scene.scene_id, scene.cloud_cover_pct)

        rgb = true_colour(scene, site["centre"], site["close"])
        save(rgb, OUT_DIR / f"{args.site}-{label}-truecolour.webp")

        nd, mean = ndvi_image(scene, site["centre"], site["close"])
        log.info("  mean ndvi in frame: %.4f", mean)
        save(nd, OUT_DIR / f"{args.site}-{label}-ndvi.webp")

        if label == "before":
            wide = true_colour(scene, site["centre"], site["wide"])
            save(wide, OUT_DIR / f"{args.site}-wide.webp", width=2400)

    manifest = OUT_DIR / f"{args.site}-imagery.json"
    manifest.write_text(json.dumps({
        "site": args.site,
        "source": "Landsat Collection 2 Level-2, USGS (public domain)",
        "frames": {
            label: {
                "requested_period": site[label],
                "period": scene.period_key,
                "scene_id": scene.scene_id,
                "cloud_cover_pct": scene.cloud_cover_pct,
                "acquired": scene.datetime_utc,
            }
            for label, scene in chosen.items()
        },
    }, indent=2), encoding="utf-8")
    log.info("wrote %s", manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
