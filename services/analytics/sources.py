"""Where the real numbers come from.

Two external sources, both chosen because they can be re-run by anyone
reviewing this project:

* **Landsat Collection 2 Level-2** via the Microsoft Planetary Computer STAC
  API. Search is open; reading the COG assets needs a short-lived SAS token
  which `planetary_computer.sign` obtains anonymously.
* **ERA5 reanalysis rainfall** via Open-Meteo's archive API. No key at all.

Both are wrapped here so the rest of the pipeline never touches HTTP
directly, and so a network failure surfaces as one recognisable exception
rather than six different ones.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date

import httpx

log = logging.getLogger("cbb.sources")

STAC_URL = "https://planetarycomputer.microsoft.com/api/stac/v1"
LANDSAT_COLLECTION = "landsat-c2-l2"
OPEN_METEO_ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"

#: ERA5's grid spacing. Stated everywhere this data is displayed, because a
#: ~25 km cell cannot resolve a 210 ha site and we must not imply it can.
ERA5_RESOLUTION_NOTE = (
    "ERA5 reanalysis, ~25 km grid -- district-level context, not site rainfall"
)


class SourceUnavailable(RuntimeError):
    """An upstream data source could not be reached or refused the request."""


@dataclass(frozen=True)
class SceneRef:
    """One Landsat scene that overlaps the project area."""

    scene_id: str
    datetime_utc: str
    cloud_cover_pct: float
    platform: str
    assets: dict[str, str]          # band name -> signed href

    @property
    def period_key(self) -> str:
        """Monthly aggregation bucket, e.g. '2026-08'."""
        return self.datetime_utc[:7]


def search_landsat(
    bbox: tuple[float, float, float, float],
    start: date,
    end: date,
    max_cloud_pct: float = 60.0,
    limit: int = 400,
) -> list[SceneRef]:
    """Find Landsat 8/9 L2 scenes overlapping ``bbox``.

    ``max_cloud_pct`` is a scene-level filter and is deliberately generous:
    scene cloud cover says little about our 210 ha polygon, and the real
    decision is made per-pixel by the QA mask. Filtering hard here would
    throw away months that are perfectly clear over the site.
    """
    try:
        import planetary_computer
        import pystac_client
    except ImportError as exc:  # pragma: no cover - dependency guard
        raise SourceUnavailable(f"STAC client libraries missing: {exc}") from exc

    try:
        catalog = pystac_client.Client.open(STAC_URL, modifier=planetary_computer.sign_inplace)
        search = catalog.search(
            collections=[LANDSAT_COLLECTION],
            bbox=bbox,
            datetime=f"{start.isoformat()}/{end.isoformat()}",
            query={
                "eo:cloud_cover": {"lt": max_cloud_pct},
                "platform": {"in": ["landsat-8", "landsat-9"]},
            },
            max_items=limit,
        )
        items = list(search.items())
    except Exception as exc:
        raise SourceUnavailable(f"Landsat STAC search failed: {exc}") from exc

    scenes: list[SceneRef] = []
    for item in items:
        assets = item.assets
        # Band names differ between collections; these are the C2 L2 names.
        if not {"red", "nir08", "qa_pixel"} <= set(assets):
            log.debug("skipping %s: missing required bands", item.id)
            continue
        scenes.append(
            SceneRef(
                scene_id=item.id,
                datetime_utc=item.datetime.strftime("%Y-%m-%dT%H:%M:%SZ"),
                cloud_cover_pct=float(item.properties.get("eo:cloud_cover", 0.0)),
                platform=item.properties.get("platform", "unknown"),
                assets={
                    "red": assets["red"].href,
                    "nir": assets["nir08"].href,
                    "qa": assets["qa_pixel"].href,
                },
            )
        )

    scenes.sort(key=lambda s: s.datetime_utc)
    log.info("found %d usable Landsat scenes", len(scenes))
    return scenes


@dataclass(frozen=True)
class RainfallMonth:
    period_key: str
    precipitation_mm: float


def fetch_rainfall(lat: float, lon: float, start: date, end: date) -> list[RainfallMonth]:
    """Monthly precipitation totals for the site centroid, from ERA5.

    Daily values are fetched and summed locally rather than asking the API for
    monthly aggregates, so the aggregation rule is visible in our own code.
    """
    params = {
        "latitude": round(lat, 4),
        "longitude": round(lon, 4),
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "daily": "precipitation_sum",
        "timezone": "UTC",
    }
    try:
        response = httpx.get(OPEN_METEO_ARCHIVE, params=params, timeout=60.0)
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        raise SourceUnavailable(f"Open-Meteo request failed: {exc}") from exc

    daily = payload.get("daily") or {}
    days = daily.get("time") or []
    values = daily.get("precipitation_sum") or []

    monthly: dict[str, float] = {}
    for day, value in zip(days, values):
        if value is None:
            continue
        monthly[day[:7]] = monthly.get(day[:7], 0.0) + float(value)

    return [RainfallMonth(k, round(v, 2)) for k, v in sorted(monthly.items())]
