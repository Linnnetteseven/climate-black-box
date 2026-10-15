"""Load the observation fixture into Oracle, idempotently.

Uses MERGE so re-running changes nothing: the unique key is
(project_id, metric, period_key, processing_version), and the loader is
expected to be run repeatedly as the pipeline is re-run.

Each observation gets an evidence_assets row first -- that is where the scene
id, the source dataset and the quality summary live, and it is what the
evidence drawer in the UI reads.
"""

from __future__ import annotations

import hashlib
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.api.db.connection import cursor  # noqa: E402

load_dotenv()
log = logging.getLogger("cbb.load")

FIXTURES = {
    "kiambu-restoration-demo": Path("data/sample/observations_ndvi-v1.json"),
    "mau-transmara-demo": Path("data/sample/observations_mau_ndvi-v1.json"),
    "mikoko-pamoja-demo": Path("data/sample/observations_mikoko_ndvi-v1.json"),
}


def _evidence_id(project_id: str, scene_id: str, period_key: str) -> str:
    """Stable id derived from identity, so re-running produces the same row."""
    digest = hashlib.sha256(f"{project_id}|{scene_id}|{period_key}".encode()).hexdigest()
    return f"ev-{digest[:16]}"


def _observation_id(project_id: str, metric: str, period_key: str, version: str) -> str:
    digest = hashlib.sha256(f"{project_id}|{metric}|{period_key}|{version}".encode()).hexdigest()
    return f"obs-{digest[:16]}"


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", default="kiambu-restoration-demo", choices=sorted(FIXTURES))
    args = ap.parse_args()
    payload = json.loads(FIXTURES[args.project].read_text(encoding="utf-8"))
    project_id = payload["project_id"]
    metric = payload["metric"]
    rows = payload["observations"]

    inserted = updated = skipped = 0

    with cursor() as cur:
        for row in rows:
            if row["source_scene_id"] is None:
                skipped += 1
                continue

            ev_id = _evidence_id(project_id, row["source_scene_id"], row["period_key"])
            quality = json.dumps({
                "valid_pixel_fraction": row["valid_pixel_fraction"],
                "valid_pixels": row["valid_pixels"],
                "total_pixels": row["total_pixels"],
                "cloud_cover_scene_pct": row["cloud_cover_scene_pct"],
                "platform": row["platform"],
                "quality_flags": row["quality_flags"],
            })

            cur.execute(
                """MERGE INTO evidence_assets t
                   USING (SELECT :id AS id FROM dual) s ON (t.id = s.id)
                   WHEN MATCHED THEN UPDATE SET
                     quality_json = :quality, observed_at = :observed_at
                   WHEN NOT MATCHED THEN INSERT
                     (id, project_id, source_type, source_dataset, source_id,
                      source_uri, observed_at, content_sha256, quality_json,
                      simulation_status)
                   VALUES (:id, :pid, 'satellite', :dataset, :scene,
                           :uri, :observed_at, :sha, :quality, 'real')""",
                id=ev_id, pid=project_id, dataset=row["source_dataset"],
                scene=row["source_scene_id"],
                uri=f"https://planetarycomputer.microsoft.com/api/stac/v1/collections/"
                    f"landsat-c2-l2/items/{row['source_scene_id']}",
                observed_at=_ts(row["observed_at"]),
                sha=hashlib.sha256(quality.encode()).hexdigest(),
                quality=quality,
            )

            obs_id = _observation_id(project_id, metric, row["period_key"],
                                     row["processing_version"])
            cur.execute("SELECT COUNT(*) FROM observations WHERE id = :id", id=obs_id)
            existed = cur.fetchone()[0] > 0

            cur.execute(
                """MERGE INTO observations t
                   USING (SELECT :id AS id FROM dual) s ON (t.id = s.id)
                   WHEN MATCHED THEN UPDATE SET
                     value = :value,
                     valid_pixel_fraction = :vpf,
                     cloud_cover_pct = :cloud,
                     quality_flags = :flags,
                     evidence_asset_id = :ev
                   WHEN NOT MATCHED THEN INSERT
                     (id, project_id, metric, value, unit, period_key,
                      period_start, period_end, observed_at,
                      valid_pixel_fraction, cloud_cover_pct, quality_flags,
                      processing_version, evidence_asset_id, simulation_status)
                   VALUES (:id, :pid, :metric, :value, :unit, :pkey,
                           :pstart, :pend, :observed_at,
                           :vpf, :cloud, :flags, :version, :ev, 'real')""",
                id=obs_id, pid=project_id, metric=metric,
                value=row["value"], unit=row["unit"], pkey=row["period_key"],
                pstart=_ts(row["period_start"]), pend=_ts(row["period_end"]),
                observed_at=_ts(row["observed_at"]),
                vpf=row["valid_pixel_fraction"], cloud=row["cloud_cover_scene_pct"],
                flags=",".join(row["quality_flags"]),
                version=row["processing_version"], ev=ev_id,
            )
            if existed:
                updated += 1
            else:
                inserted += 1

            # Rainfall is evidence too. The alert's reasoning cites it, so it
            # has to exist as a row with its own id and provenance -- otherwise
            # we are asserting context we cannot show.
            if row.get("precipitation_mm") is not None:
                rain_id = _observation_id(project_id, "precipitation_mm",
                                          row["period_key"], "era5-v1")
                cur.execute(
                    """MERGE INTO observations t
                       USING (SELECT :id AS id FROM dual) s ON (t.id = s.id)
                       WHEN MATCHED THEN UPDATE SET value = :value
                       WHEN NOT MATCHED THEN INSERT
                         (id, project_id, metric, value, unit, period_key,
                          period_start, period_end, processing_version,
                          quality_flags, simulation_status)
                       VALUES (:id, :pid, 'precipitation_mm', :value, 'mm', :pkey,
                               :pstart, :pend, 'era5-v1',
                               'era5_reanalysis,grid_25km', 'real')""",
                    id=rain_id, pid=project_id, value=row["precipitation_mm"],
                    pkey=row["period_key"], pstart=_ts(row["period_start"]),
                    pend=_ts(row["period_end"]),
                )

    log.info("inserted %d, updated %d, skipped %d (of %d rows)",
             inserted, updated, skipped, len(rows))
    return 0


def _ts(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


if __name__ == "__main__":
    raise SystemExit(main())
