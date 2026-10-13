# Data sources, licences and provenance

Every number this project puts on screen comes from one of the sources below.
If a figure cannot be traced to a row here, it should not be on screen.

## Real data

### Landsat Collection 2 Level-2 surface reflectance
- **Source:** Microsoft Planetary Computer STAC, collection `landsat-c2-l2`
  (`https://planetarycomputer.microsoft.com/api/stac/v1`).
- **Underlying producer:** USGS / NASA Landsat 8 and 9 OLI.
- **Access:** STAC search is open. Reading the assets needs a short-lived SAS
  token, obtainable anonymously (rate-limited) from the Planetary Computer
  Data Authentication API.
- **Licence:** Landsat data are in the public domain (USGS).
- **Resolution:** 30 m.
- **What we compute:** `ndvi_mean`, the mean NDVI of valid pixels inside the
  project polygon, per calendar month. See `services/analytics/ndvi.py`.
- **Limitations we state out loud:**
  - NDVI is a vegetation **greenness** indicator. It is not tree survival, not
    canopy cover, not biomass, and not carbon.
  - Cloud, cloud shadow, snow, dilated cloud and fill pixels are masked out
    before the mean. Months where too few pixels survive are reported as gaps,
    never interpolated.
  - A 30 m pixel mixes canopy, understorey and bare ground.

### Rainfall — ERA5 via Open-Meteo
- **Source:** Open-Meteo Historical Weather API
  (`https://archive-api.open-meteo.com/v1/archive`), variable
  `precipitation_sum`.
- **Underlying producer:** ECMWF ERA5 reanalysis.
- **Access:** free, no API key. Non-commercial use.
- **Resolution:** **~25 km grid.**
- **Limitations we state out loud:** at ~25 km a single grid cell covers far
  more than our ~210 ha site. This is **district-level context**, useful for
  answering "was the whole area dry that season", and it **cannot** resolve
  conditions at the project site. We never present it as site rainfall.

## Simulated data

Everything below is invented. It is flagged `simulation_status = 'simulated'`
in the database, badged in the UI, and labelled on stage.

- The project, its name, its owner organisation and its boundary polygon.
- The commitment, its target, and the named reviewer who approved it.
- Any field report.
- Every intervention. The database physically refuses to store an
  intervention marked `real` (`CK_INTERVENTIONS_SIMULATED`).

There is no real funded project behind this demonstration. We invented a
plausible one so that the evidence loop has something to hang on, and we built
it around **real** satellite and rainfall measurements so the loop is testing
something true.

## Reproducibility

`make ingest` regenerates the observation fixture from source and diffs it
against the committed copy. If the numbers move, the command says so. That
property is what makes the evidence claim defensible: anyone can re-derive
our figures from public data.
