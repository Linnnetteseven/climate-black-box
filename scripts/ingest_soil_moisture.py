#!/usr/bin/env python3
"""Monthly surface soil moisture for each project, from ERA5-Land.

Soil moisture is context, not evidence of a promise kept. It earns its place
beside NDVI because it is the first thing anyone asks when greenness falls:
was the site cleared, or was it dry? The investigation step can only weigh
that alternative if the number is on the record.

Written as its own script rather than folded into the Landsat pipeline because
it shares nothing with it: no scenes, no pixels, no cloud masking. It needs no
migration either -- `metric` and `unit` are free text, so a new metric is new
rows, not a new column.

Usage:
    .venv/bin/python scripts/ingest_soil_moisture.py            # every project
    .venv/bin/python scripts/ingest_soil_moisture.py --project mau-transmara-demo
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.analytics.sources import fetch_soil_moisture  # noqa: E402
from services.api.db.coerce import as_json  # noqa: E402
from services.api.db.connection import cursor  # noqa: E402

METRIC = "soil_moisture_pct"
UNIT = "%"
PROCESSING_VERSION = "soil-moisture-v1"

#: ERA5-Land is ~9 km. At that scale a 400 ha site is a fraction of one cell,
#: so this describes the district, not the project. Carried as a quality flag
#: so the limitation travels with the row rather than living in a README.
QUALITY_FLAGS = ["reanalysis", "regional_scale_9km"]


def _observation_id(project_id: str, period_key: str) -> str:
    raw = f"{project_id}|{METRIC}|{period_key}|{PROCESSING_VERSION}"
    return "obs-" + hashlib.sha256(raw.encode()).hexdigest()[:16]


def centroid(boundary_geojson) -> tuple[float, float]:
    # Oracle hands this back as a LOB, a string or an already-parsed dict
    # depending on the driver path, which is exactly what as_json exists for.
    ring = as_json(boundary_geojson)["coordinates"][0]
    lons = [p[0] for p in ring]
    lats = [p[1] for p in ring]
    return sum(lats) / len(lats), sum(lons) / len(lons)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", help="one project id; default is all of them")
    args = ap.parse_args()

    with cursor() as cur:
        if args.project:
            cur.execute(
                "SELECT id, boundary_geojson, reporting_start, reporting_end "
                "FROM projects WHERE id = :p",
                {"p": args.project},
            )
        else:
            cur.execute(
                "SELECT id, boundary_geojson, reporting_start, reporting_end FROM projects"
            )
        projects = [(r[0], r[1], r[2], r[3]) for r in cur]

    if not projects:
        print("no matching project")
        return 1

    total = 0
    for project_id, boundary, start, end in projects:
        lat, lon = centroid(boundary)
        # Never ask for the future: the archive simply has no rows for it.
        last = min(date.fromisoformat(str(end)[:10]), date.today())
        months = fetch_soil_moisture(lat, lon, date.fromisoformat(str(start)[:10]), last)
        print(f"{project_id}: {len(months)} months at {lat:.4f},{lon:.4f}")

        now = datetime.now(timezone.utc)
        with cursor() as cur:
            for m in months:
                y, mo = int(m.period_key[:4]), int(m.period_key[5:7])
                nxt = (y + 1, 1) if mo == 12 else (y, mo + 1)
                cur.execute(
                    """MERGE INTO observations o
                       USING (SELECT :id AS id FROM dual) s ON (o.id = s.id)
                       WHEN MATCHED THEN UPDATE SET value = :val, observed_at = :obs
                       WHEN NOT MATCHED THEN INSERT
                         (id, project_id, metric, value, unit, period_key,
                          period_start, period_end, observed_at, quality_flags,
                          processing_version, simulation_status, created_at)
                       VALUES (:id, :pid, :metric, :val, :unit, :pk,
                               :ps, :pe, :obs, :flags, :pv, 'real', :now)""",
                    {
                        "id": _observation_id(project_id, m.period_key),
                        "pid": project_id,
                        "metric": METRIC,
                        "val": m.soil_moisture_pct,
                        "unit": UNIT,
                        "pk": m.period_key,
                        "ps": datetime(y, mo, 1, tzinfo=timezone.utc),
                        "pe": datetime(nxt[0], nxt[1], 1, tzinfo=timezone.utc),
                        "obs": now,
                        "flags": json.dumps(QUALITY_FLAGS),
                        "pv": PROCESSING_VERSION,
                        "now": now,
                    },
                )
                total += 1
    print(f"\n{total} soil moisture observations written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
