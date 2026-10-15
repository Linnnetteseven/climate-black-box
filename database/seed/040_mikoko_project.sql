-- ---------------------------------------------------------------------------
-- Mikoko Pamoja Mangrove Conservation (Gazi Bay, Kwale County, Kenya)
-- Control Site: Positive Trajectory / No Divergence Baseline
-- Target: Oracle Database 23ai / Autonomous Database
-- File: database/seed/040_mikoko_project.sql
--
-- WHY THIS SITE IS THE CONTROL:
--
-- Our alert engine is designed to fire when a project's vegetation greenness
-- drops below a 1.5-sigma band for two consecutive periods. A detector that
-- fires everywhere detects nothing; we need a real-world counterweight that
-- faces coastal weather, high humidity, and monsoon transitions, but held its
-- canopy intact under genuine community governance.
--
-- Mikoko Pamoja in Gazi Bay has been protecting and replanting Rhizophora
-- mucronata and Avicennia marina stands since 2013, supported by the Kenya
-- Marine and Fisheries Research Institute (KMFRI). Because tidal inundation
-- supplies continuous moisture, the mangrove canopy maintains a solid,
-- resilient NDVI baseline (typically 0.60 to 0.74). The alert detector
-- evaluates this entire 45-month series and correctly stays quiet.
--
-- REAL VS SIMULATED SPLIT:
--   simulated : the administrative project wrapper, the named reviewer, and
--               the excerpted commitment document.
--   real      : all Landsat 8/9 surface reflectance observations, the QA_PIXEL
--               pixel-masking masks, and the polygon boundary coordinates.
-- ---------------------------------------------------------------------------

DELETE FROM commitments WHERE project_id = 'mikoko-pamoja-demo';
DELETE FROM projects    WHERE id         = 'mikoko-pamoja-demo';

-- 1. Project Registration ---------------------------------------------------
INSERT INTO projects (
  id,
  name,
  country,
  region,
  owner_org,
  status,
  boundary_geojson,
  boundary_is_survey,
  reporting_start,
  reporting_end,
  simulation_status
) VALUES (
  'mikoko-pamoja-demo',
  'Mikoko Pamoja Mangrove Restoration & Protection (control)',
  'Kenya',
  'Kwale County, Gazi Bay',
  'Mikoko Pamoja Community Organization / KMFRI',
  'active',
  
  -- ~82 ha of dense canopy on the Gazi Bay tideline. The first boundary ran
  -- over the tidal channel: a third of its readings were open water and two
  -- were negative, so the series described the tide rather than the canopy.
  -- This one was chosen from a twelve-scene median composite -- median NDVI
  -- 0.881, tenth percentile 0.844, within 120 m of persistent water.
  '{"type":"Polygon","coordinates":[[
      [39.5144,-4.4205],[39.5225,-4.4205],[39.5225,-4.4123],
      [39.5144,-4.4123],[39.5144,-4.4205]]]}',
  0,  -- Drawn from imagery, not surveyed
  DATE '2023-01-01',
  DATE '2026-12-31',
  'simulated'
);

-- 2. Approved Commitment Baseline ------------------------------------------
-- Approved commitments require a named reviewer and timestamp to satisfy the
-- CK_COMMITMENTS_REVIEWED constraint. Anonymous baselines are rejected.
INSERT INTO commitments (
  id,
  project_id,
  metric,
  target_value,
  unit,
  due_date,
  baseline_start,
  baseline_end,
  source_document,
  source_text_span,
  extraction_status,
  extraction_model,
  prompt_version,
  reviewer,
  reviewed_at,
  simulation_status
) VALUES (
  'cmt-mikoko-ndvi-2026',
  'mikoko-pamoja-demo',
  'ndvi_mean',
  0.6800,
  'index',
  DATE '2026-12-31',
  DATE '2023-01-01',
  DATE '2024-12-31',
  'mikoko-pamoja-project-design.pdf (demonstration document)',
  'Community patrols, hydrological channel maintenance, and active Rhizophora '
  || 'enrichment planting across the 135-hectare Gazi Bay tract will sustain mean '
  || 'canopy greenness at or above the 2023-2024 baseline of 0.6800 through December 2026.',
  'approved',
  'meta.llama-3.3-70b-instruct',
  'extract-v1',
  'Dr. J. Kairo (demonstration reviewer)',
  TIMESTAMP '2026-01-12 10:00:00 +00:00',
  'simulated'
);

-- 3. Oracle Spatial Geometry Backfill ---------------------------------------
-- Applied via run_sql.py --tolerant when Oracle Spatial (MDSYS) is installed.
UPDATE projects
   SET boundary = SDO_UTIL.FROM_GEOJSON(boundary_geojson)
 WHERE id = 'mikoko-pamoja-demo'
   AND boundary_geojson IS NOT NULL;

COMMIT;
