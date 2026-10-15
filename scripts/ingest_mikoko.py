#!/usr/bin/env python3
"""
ingest_mikoko.py — Landsat C2 L2 Surface Reflectance Ingestion for Mikoko Pamoja

Fetches Landsat 8/9 Collection 2 Level-2 surface reflectance scenes over Gazi Bay,
Kenya from Microsoft Planetary Computer. Clips bands to the Mikoko Pamoja project
polygon, filters out clouds and shadows using the QA_PIXEL bitmask, computes
masked monthly mean NDVI, and writes out a frozen fixture: observations_mikoko_ndvi-v1.json.

Why Gazi Bay works as a control:
Unlike the highland evergreen forest at South-West Mau which suffered clearance
pressure, Mikoko Pamoja has had continuous community-enforced protection and active
Rhizophora/Avicennia replanting since 2013 under Plan Vivo accreditation. Because
mangroves benefit from regular semidiurnal tidal flushing, they maintain a stable
vegetation greenness baseline (~0.60–0.75 NDVI) throughout the year, even during
dry coastal seasons.

Written procedurally without heavy OOP abstraction so every step is transparent
and debuggable during a review.
"""

import calendar
import json
import os
import sys
import uuid
from datetime import datetime, timezone

import numpy as np
import planetary_computer
import pystac_client
import rasterio
from rasterio.features import geometry_mask
from rasterio.warp import transform_geom
from rasterio.windows import from_bounds
from shapely.geometry import shape

# ---------------------------------------------------------------------------
# Configuration & Spatial Extent
# ---------------------------------------------------------------------------

PROJECT_ID = "mikoko-pamoja-demo"
COLLECTION = "landsat-c2-l2"
STAC_API_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"

# Target output: save to data/sample/ if that directory exists, else local directory
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "sample")
if not os.path.exists(OUTPUT_DIR):
    OUTPUT_DIR = "."
OUTPUT_PATH = os.path.normpath(os.path.join(OUTPUT_DIR, "observations_mikoko_ndvi-v1.json"))

# Mikoko Pamoja ~135 ha polygon in Gazi Bay, Kwale County, Kenya (EPSG:4326)
POLYGON_GEOM = {
    "type": "Polygon",
    "coordinates": [[
        [39.5144, -4.4205], [39.5225, -4.4205], [39.5225, -4.4123],
        [39.5144, -4.4123], [39.5144, -4.4205]
    ]]
}

# (min_lon, min_lat, max_lon, max_lat)
BBOX = (39.5080, -4.4360, 39.5190, -4.4260)
START_DATE = "2023-01-01"
END_DATE = "2026-09-30"

# USGS Landsat Collection 2 Level-2 Surface Reflectance constants
# Reflectance = DN * 0.0000275 - 0.2
SR_SCALE = 0.0000275
SR_OFFSET = -0.2
SR_MIN_DN = 7273
SR_MAX_DN = 43636

# QA_PIXEL bit positions (Landsat 8/9 OLI-TIRS Collection 2 L2):
# Bit 0: Fill, 1: Dilated Cloud, 2: Cirrus, 3: Cloud, 4: Cloud Shadow, 5: Snow
# If any of these bits are set, the pixel must not be used for canopy estimation.
QA_WATER = 7

REJECT_BITS = (0, 1, 2, 3, 4, 5, QA_WATER)


# ---------------------------------------------------------------------------
# Helper Functions (Purely Procedural)
# ---------------------------------------------------------------------------

def build_qa_mask(qa_array):
    """
    Returns a boolean mask: True for valid/usable pixels, False for bad ones.
    We drop fill, clouds, cloud shadows, cirrus, dilated cloud edges -- and
    water. Water matters here and nowhere else in the project: this is a tidal
    bay, so a pixel that is sea at high tide and mud at low tide produces a
    number that describes the tide, not the canopy.
    We don't strictly require the CLEAR bit (bit 6) because healthy mangrove
    fringes next to tidal water channels can be slightly hazy without degrading
    the surface reflectance signal.
    """
    rejected = np.zeros(qa_array.shape, dtype=bool)
    for bit in REJECT_BITS:
        rejected |= ((qa_array.astype(np.uint16) >> bit) & 1) == 1
    return ~rejected


def get_monthly_date_windows(start_year=2023, end_year=2026, end_month=9):
    """
    Builds a list of (period_key, period_start_iso, period_end_iso) tuples
    spanning each calendar month from Jan 2023 through Sep 2026.
    """
    periods = []
    for year in range(start_year, end_year + 1):
        last_m = end_month if year == end_year else 12
        for month in range(1, last_m + 1):
            key = f"{year:04d}-{month:02d}"
            num_days = calendar.monthrange(year, month)[1]
            p_start = f"{year:04d}-{month:02d}-01T00:00:00Z"
            p_end = f"{year:04d}-{month:02d}-{num_days:02d}T23:59:59Z"
            periods.append((key, p_start, p_end))
    return periods


# ---------------------------------------------------------------------------
# Main Execution Pipeline
# ---------------------------------------------------------------------------

def main():
    print("=" * 70)
    print("Climate Black Box — Ingestion: Mikoko Pamoja Control Site")
    print(f"Target Bounding Box : {BBOX}")
    print(f"Date Range          : {START_DATE} to {END_DATE}")
    print(f"Output Fixture File : {OUTPUT_PATH}")
    print("=" * 70)

    # 1. Search Planetary Computer STAC for Landsat 8 and 9 scenes
    try:
        print("\n[1/4] Querying Microsoft Planetary Computer STAC catalog...")
        catalog = pystac_client.Client.open(
            STAC_API_URL,
            modifier=planetary_computer.sign_inplace
        )
        search = catalog.search(
            collections=[COLLECTION],
            bbox=BBOX,
            datetime=f"{START_DATE}/{END_DATE}",
            query={
                "eo:cloud_cover": {"lt": 60.0},
                "platform": {"in": ["landsat-8", "landsat-9"]}
            },
            max_items=400
        )
        items = list(search.items())
        print(f"  Found {len(items)} matching Landsat scenes over Gazi Bay.")
    except Exception as exc:
        print(f"ERROR: Failed to connect or search Planetary Computer: {exc}", file=sys.stderr)
        sys.exit(1)

    # 2. Index the best scene for each calendar month (lowest scene-level cloud cover)
    print("\n[2/4] Indexing least-cloudy scene candidate per monthly bucket...")
    monthly_best_scenes = {}
    for item in items:
        # Require Red (B4), NIR (B5), and QA_PIXEL
        if not {"red", "nir08", "qa_pixel"} <= set(item.assets):
            continue

        month_bucket = item.datetime.strftime("%Y-%m")
        cloud_pct = float(item.properties.get("eo:cloud_cover", 100.0))

        if (month_bucket not in monthly_best_scenes or 
                cloud_pct < monthly_best_scenes[month_bucket]["cloud_cover"]):
            monthly_best_scenes[month_bucket] = {
                "scene_id": item.id,
                "datetime": item.datetime.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "cloud_cover": cloud_pct,
                "assets": {
                    "red": item.assets["red"].href,
                    "nir": item.assets["nir08"].href,
                    "qa": item.assets["qa_pixel"].href,
                }
            }

    print(f"  Mapped {len(monthly_best_scenes)} months with candidate scenes.")

    # 3. Process each monthly window across 2023-01 to 2026-09
    print("\n[3/4] Processing windowed raster bands and calculating masked NDVI...")
    windows = get_monthly_date_windows(start_year=2023, end_year=2026, end_month=9)
    observations = []

    for month_key, p_start, p_end in windows:
        # Generate a unique hex ID per observation row (compatible with Oracle SYS_GUID)
        row_id = uuid.uuid4().hex

        if month_key not in monthly_best_scenes:
            # Honest data recording: if no usable satellite pass exists, record null
            observations.append({
                "id": row_id,
                "project_id": PROJECT_ID,
                "metric": "ndvi_mean",
                "obs_value": None,
                "period_key": month_key,
                "period_start": p_start,
                "period_end": p_end,
                "valid_pixel_fraction": 0.0,
                "valid_pixels": 0,
                "total_pixels": 0,
                "source_scene_id": None,
                "cloud_cover_pct": None,
                "source_uri": None,
                "simulation_status": "real"
            })
            print(f"  [{month_key}] No usable scene -> null observation recorded.")
            continue

        candidate = monthly_best_scenes[month_key]
        scene_assets = candidate["assets"]

        try:
            bands_data = {}
            polygon_mask = None

            # Read each band clipped to the project polygon window
            for band_name in ("red", "nir", "qa"):
                href = planetary_computer.sign(scene_assets[band_name])
                with rasterio.open(href) as src:
                    # Project WGS84 coordinates to the scene's native UTM projection
                    # This avoids resampling or distorting reflectance pixels
                    projected_polygon = transform_geom("EPSG:4326", src.crs, POLYGON_GEOM)
                    poly_bounds = shape(projected_polygon).bounds
                    window = from_bounds(*poly_bounds, transform=src.transform)

                    raster_chunk = src.read(1, window=window)
                    if raster_chunk.size == 0:
                        raise ValueError(f"Empty window read for scene {candidate['scene_id']}")

                    bands_data[band_name] = raster_chunk

                    if polygon_mask is None:
                        # True inside polygon, False outside
                        polygon_mask = ~geometry_mask(
                            [projected_polygon],
                            out_shape=raster_chunk.shape,
                            transform=src.window_transform(window),
                            invert=False
                        )

            red_raw = bands_data["red"]
            nir_raw = bands_data["nir"]
            qa_raw = bands_data["qa"]

            # Compute pixel validity inside the polygon
            total_pixels_in_site = int(polygon_mask.sum())
            qa_ok = build_qa_mask(qa_raw)
            dn_ok = (
                (red_raw >= SR_MIN_DN) & (red_raw <= SR_MAX_DN) &
                (nir_raw >= SR_MIN_DN) & (nir_raw <= SR_MAX_DN)
            )

            surviving_pixels = polygon_mask & qa_ok & dn_ok
            valid_pixel_count = int(surviving_pixels.sum())

            if total_pixels_in_site > 0:
                fraction = float(valid_pixel_count / total_pixels_in_site)
            else:
                fraction = 0.0

            # Under 10% valid coverage across the site is too noisy to trust
            if fraction >= 0.10 and valid_pixel_count > 0:
                # Convert raw Digital Numbers to surface reflectance
                red_refl = red_raw[surviving_pixels].astype(np.float64) * SR_SCALE + SR_OFFSET
                nir_refl = nir_raw[surviving_pixels].astype(np.float64) * SR_SCALE + SR_OFFSET

                denominator = nir_refl + red_refl
                valid_denom = denominator > 0.0001
                ndvi_pixels = (nir_refl[valid_denom] - red_refl[valid_denom]) / denominator[valid_denom]

                if ndvi_pixels.size > 0:
                    mean_val = round(float(np.mean(ndvi_pixels)), 4)
                else:
                    mean_val = None
            else:
                mean_val = None

            observations.append({
                "id": row_id,
                "project_id": PROJECT_ID,
                "metric": "ndvi_mean",
                "obs_value": mean_val,
                "period_key": month_key,
                "period_start": p_start,
                "period_end": p_end,
                "valid_pixel_fraction": round(fraction, 4),
                "valid_pixels": int(surviving_pixels.sum()),
                "total_pixels": int(surviving_pixels.size),
                # The scene id is what makes this re-derivable by a stranger:
                # without it the loader cannot build an evidence id and the row
                # is dropped, so it travels with the measurement.
                "source_scene_id": candidate["scene_id"],
                "cloud_cover_pct": round(candidate["cloud_cover"], 2),
                "source_uri": f"{STAC_API_URL}/collections/{COLLECTION}/items/{candidate['scene_id']}",
                "simulation_status": "real"
            })

            val_str = f"{mean_val:.4f}" if mean_val is not None else "   None"
            print(f"  [{month_key}] NDVI: {val_str} | Valid Pixels: {fraction:6.2%} | Scene: {candidate['scene_id']}")

        except Exception as err:
            print(f"  [{month_key}] Error processing scene ({err}) -> recording gap.")
            observations.append({
                "id": row_id,
                "project_id": PROJECT_ID,
                "metric": "ndvi_mean",
                "obs_value": None,
                "period_key": month_key,
                "period_start": p_start,
                "period_end": p_end,
                "valid_pixel_fraction": 0.0,
                "valid_pixels": 0,
                "total_pixels": 0,
                "source_scene_id": None,
                "cloud_cover_pct": None,
                "source_uri": None,
                "simulation_status": "real"
            })

    # 4. Save formatted JSON fixture
    print("\n[4/4] Writing fixture to disk...")
    try:
        with open(OUTPUT_PATH, "w", encoding="utf-8") as out_f:
            json.dump({
                "project_id": PROJECT_ID,
                "metric": "ndvi_mean",
                "processing_version": "ndvi-v1",
                "observations": observations,
            }, out_f, indent=2)
        print(f"  Successfully wrote {len(observations)} observation records to {OUTPUT_PATH}")
    except Exception as exc:
        print(f"ERROR writing output file: {exc}", file=sys.stderr)
        sys.exit(1)

    print("\nDone. Mikoko Pamoja control observations ready for database loading.")


if __name__ == "__main__":
    main()
