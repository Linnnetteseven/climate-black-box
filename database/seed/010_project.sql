-- ---------------------------------------------------------------------------
-- The one demo project: a forest restoration site in Kiambu County, Kenya.
--
-- WHAT IS REAL AND WHAT IS NOT, stated here because it is stated on stage:
--
--   simulated : the project itself, its owner, its commitment, the named
--               reviewer, and every intervention. There is no real funded
--               project behind this. We invented a plausible one so the
--               evidence loop has something to hang on.
--   real      : every satellite observation and every rainfall figure. Those
--               come from Landsat Collection 2 Level-2 and ERA5 and are
--               loaded by the pipeline, not by this file.
--
-- That split is the whole integrity story. This file therefore seeds ONLY
-- simulated rows. If you ever find yourself adding an observation here, stop:
-- observations come from `make ingest`.
-- ---------------------------------------------------------------------------

DELETE FROM commitments WHERE project_id = 'kiambu-restoration-demo';
DELETE FROM projects    WHERE id         = 'kiambu-restoration-demo';

INSERT INTO projects (
  id, name, country, region, owner_org, status,
  boundary_geojson, boundary_is_survey,
  reporting_start, reporting_end, simulation_status
) VALUES (
  'kiambu-restoration-demo',
  'Kiambu Highlands Forest Restoration (demonstration)',
  'Kenya',
  'Kiambu County',
  'Demonstration implementer -- not a real organisation',
  'active',
  -- Approximate demonstration polygon, WGS84. ~210 ha on the Kiambu
  -- highlands. boundary_is_survey = 0, and the UI labels it "approximate
  -- demo polygon" wherever it is drawn. We do not imply survey accuracy.
  '{"type":"Polygon","coordinates":[[
      [36.8300,-1.1200],[36.8470,-1.1200],[36.8470,-1.1050],
      [36.8300,-1.1050],[36.8300,-1.1200]]]}',
  0,
  DATE '2023-01-01',
  DATE '2026-12-31',
  'simulated'
);

-- The commitment. Approved, so it carries a named reviewer and a timestamp --
-- the CK_COMMITMENTS_REVIEWED constraint refuses an anonymous baseline.
INSERT INTO commitments (
  id, project_id, metric, target_value, unit, due_date,
  baseline_start, baseline_end,
  source_document, source_text_span,
  extraction_status, extraction_model, prompt_version,
  reviewer, reviewed_at, simulation_status
) VALUES (
  'cmt-kiambu-ndvi-2026',
  'kiambu-restoration-demo',
  'ndvi_mean',
  0.55,
  'index',
  DATE '2026-12-31',
  DATE '2023-01-01',
  DATE '2024-12-31',
  'kiambu-restoration-proposal.pdf (demonstration document)',
  'The programme will restore degraded highland forest across the project '
  || 'area, targeting a sustained improvement in vegetation cover through '
  || '2026, measured against the 2023-2024 baseline period.',
  'approved',
  NULL,              -- extracted deterministically in the seed, not by a model
  NULL,
  'L. Mugwanja (demonstration reviewer)',
  TIMESTAMP '2026-01-15 09:00:00 +00:00',
  'simulated'
);

COMMIT;
