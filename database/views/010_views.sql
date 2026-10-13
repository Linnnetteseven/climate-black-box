-- Reporting views. APEX reads these directly; the API reads them through the
-- repository layer. One definition, two surfaces -- which is the point.

CREATE OR REPLACE VIEW v_project_observations AS
SELECT o.id,
       o.project_id,
       p.name                AS project_name,
       o.metric,
       o.value,
       o.unit,
       o.period_start,
       o.period_end,
       o.valid_pixel_fraction,
       o.cloud_cover_pct,
       o.processing_version,
       e.source_dataset,
       e.source_id           AS source_scene_id,
       o.simulation_status
FROM observations o
JOIN projects p          ON p.id = o.project_id
LEFT JOIN evidence_assets e ON e.id = o.evidence_asset_id;

CREATE OR REPLACE VIEW v_project_alerts AS
SELECT a.id,
       a.project_id,
       p.name           AS project_name,
       a.metric,
       a.severity,
       a.status,
       a.observed_value,
       a.expected_value,
       a.expected_low,
       a.expected_high,
       a.deviation_abs,
       a.deviation_pct,
       a.consecutive_periods,
       a.rule_version,
       a.created_at,
       a.simulation_status
FROM alerts a
JOIN projects p ON p.id = a.project_id;

-- The audit timeline with its anchor state. This is the view behind the
-- "Verify" beat and behind the APEX audit page.
CREATE OR REPLACE VIEW v_audit_timeline AS
SELECT ae.id            AS event_id,
       ae.project_id,
       ae.event_type,
       ae.subject_table,
       ae.subject_id,
       ae.actor,
       ae.manifest_sha256,
       ae.previous_event_sha256,
       ae.created_at,
       ae.simulation_status,
       ca.network,
       ca.tx_hash,
       ca.output_index,
       ca.status         AS anchor_status,
       ca.explorer_url,
       ca.anchored_at
FROM audit_events ae
LEFT JOIN chain_anchors ca ON ca.event_id = ae.id;
