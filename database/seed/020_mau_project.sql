-- ---------------------------------------------------------------------------
-- Second demonstration site: Transmara / South-West Mau.
--
-- Chosen by `scripts/scan_sites.py`, which ran the PRODUCTION alert rule --
-- same seasonal adjustment, same coverage floor, no threshold tuning -- across
-- six Kenyan forest blocks. Kiambu came back quiet (+0.0017 mean anomaly) and
-- this site fired with a six-period run (-0.0458).
--
-- The site selection is itself disclosed: we went looking for a place where
-- something had happened, because that is what a monitoring system is for. We
-- did not widen a threshold until something tripped.
--
-- Real: every observation. Simulated: the project wrapper, as with Kiambu.
-- ---------------------------------------------------------------------------

DELETE FROM commitments WHERE project_id = 'mau-transmara-demo';
DELETE FROM projects    WHERE id         = 'mau-transmara-demo';

INSERT INTO projects (
  id, name, country, region, owner_org, status,
  boundary_geojson, boundary_is_survey,
  reporting_start, reporting_end, simulation_status
) VALUES (
  'mau-transmara-demo',
  'Transmara Forest Block, South-West Mau (demonstration)',
  'Kenya',
  'Narok County',
  'Demonstration implementer -- not a real organisation',
  'active',
  '{"type":"Polygon","coordinates":[[
      [35.2310,-0.9390],[35.2490,-0.9390],[35.2490,-0.9210],
      [35.2310,-0.9210],[35.2310,-0.9390]]]}',
  0,
  DATE '2023-01-01',
  DATE '2026-12-31',
  'simulated'
);

INSERT INTO commitments (
  id, project_id, metric, target_value, unit, due_date,
  baseline_start, baseline_end,
  source_document, source_text_span,
  extraction_status, reviewer, reviewed_at, simulation_status
) VALUES (
  'cmt-mau-ndvi-2026',
  'mau-transmara-demo',
  'ndvi_mean',
  0.62,
  'index',
  DATE '2026-12-31',
  DATE '2023-01-01',
  DATE '2024-12-31',
  'mau-conservation-proposal.pdf (demonstration document)',
  'The programme will hold vegetation cover across the Transmara block at or '
  || 'above its 2023-2024 baseline through 2026, with quarterly verification.',
  'approved',
  'L. Mugwanja (demonstration reviewer)',
  TIMESTAMP '2026-01-15 09:00:00 +00:00',
  'simulated'
);

COMMIT;
