-- ---------------------------------------------------------------------------
-- Climate Black Box -- core schema
-- Target: Oracle Database 23ai (local Free container and Autonomous DB alike).
-- Forward-only. Re-runnable via 000_drop.sql, never edited in place.
--
-- Two rules are enforced here rather than in application code, because
-- application code is what we will be editing at 2am:
--   1. Every evidence-bearing row carries a simulation_status.
--   2. An intervention can never be labelled 'real' in this demo.
-- ---------------------------------------------------------------------------

-- Projects ------------------------------------------------------------------
CREATE TABLE projects (
  id                 VARCHAR2(64)   NOT NULL,
  name               VARCHAR2(200)  NOT NULL,
  country            VARCHAR2(80)   NOT NULL,
  region             VARCHAR2(120),
  owner_org          VARCHAR2(200),
  status             VARCHAR2(24)   DEFAULT 'active' NOT NULL,
  -- Approximate demo polygon unless a surveyed boundary is supplied; the UI
  -- labels it as such. Stored as GeoJSON (WGS84 / EPSG:4326) because that is
  -- what the map consumes and because it works on every Oracle edition.
  -- 002_spatial.sql adds a native SDO_GEOMETRY alongside this, where Oracle
  -- Spatial is installed. GeoJSON stays the source of truth either way.
  boundary_geojson   CLOB,
  boundary_is_survey NUMBER(1)      DEFAULT 0 NOT NULL,
  reporting_start    DATE,
  reporting_end      DATE,
  simulation_status  VARCHAR2(16)   NOT NULL,
  created_at         TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL,
  CONSTRAINT pk_projects PRIMARY KEY (id),
  CONSTRAINT ck_projects_status CHECK (status IN ('active','closed','suspended')),
  CONSTRAINT ck_projects_sim CHECK (simulation_status IN ('real','simulated','mixed','fallback')),
  CONSTRAINT ck_projects_survey CHECK (boundary_is_survey IN (0,1)),
  CONSTRAINT ck_projects_boundary_json CHECK (boundary_geojson IS JSON)
);

-- Commitments ---------------------------------------------------------------
-- What the project promised. Extracted values start as 'proposed' and only a
-- named human can move them to 'approved' -- that transition is the baseline.
CREATE TABLE commitments (
  id                 VARCHAR2(64)   NOT NULL,
  project_id         VARCHAR2(64)   NOT NULL,
  metric             VARCHAR2(64)   NOT NULL,
  target_value       NUMBER,
  unit               VARCHAR2(32),
  due_date           DATE,
  baseline_start     DATE,
  baseline_end       DATE,
  source_document    VARCHAR2(400),
  source_text_span   CLOB,
  extraction_status  VARCHAR2(16)   DEFAULT 'proposed' NOT NULL,
  extraction_model   VARCHAR2(200),
  prompt_version     VARCHAR2(64),
  reviewer           VARCHAR2(200),
  reviewed_at        TIMESTAMP WITH TIME ZONE,
  simulation_status  VARCHAR2(16)   NOT NULL,
  created_at         TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL,
  CONSTRAINT pk_commitments PRIMARY KEY (id),
  CONSTRAINT fk_commitments_project FOREIGN KEY (project_id) REFERENCES projects (id),
  CONSTRAINT ck_commitments_status CHECK (extraction_status IN ('proposed','approved','rejected')),
  CONSTRAINT ck_commitments_sim CHECK (simulation_status IN ('real','simulated','mixed','fallback')),
  -- An approved commitment must name who approved it and when. No anonymous
  -- baselines: the reviewer is part of the evidence.
  CONSTRAINT ck_commitments_reviewed CHECK (
    extraction_status <> 'approved' OR (reviewer IS NOT NULL AND reviewed_at IS NOT NULL))
);

CREATE INDEX ix_commitments_project ON commitments (project_id, metric);

-- Evidence assets -----------------------------------------------------------
-- Provenance for anything we derived a number from. Large binaries stay out
-- of the database; we keep the reference and the content hash.
CREATE TABLE evidence_assets (
  id                 VARCHAR2(64)   NOT NULL,
  project_id         VARCHAR2(64)   NOT NULL,
  source_type        VARCHAR2(32)   NOT NULL,
  source_dataset     VARCHAR2(200)  NOT NULL,
  source_id          VARCHAR2(200),
  source_uri         VARCHAR2(1000),
  observed_at        TIMESTAMP WITH TIME ZONE,
  content_sha256     VARCHAR2(64),
  quality_json       CLOB,
  simulation_status  VARCHAR2(16)   NOT NULL,
  created_at         TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL,
  CONSTRAINT pk_evidence_assets PRIMARY KEY (id),
  CONSTRAINT fk_evidence_project FOREIGN KEY (project_id) REFERENCES projects (id),
  CONSTRAINT ck_evidence_type CHECK (source_type IN ('satellite','rainfall','document','field_report','derived')),
  CONSTRAINT ck_evidence_sim CHECK (simulation_status IN ('real','simulated','mixed','fallback')),
  CONSTRAINT ck_evidence_quality_json CHECK (quality_json IS JSON)
);

CREATE INDEX ix_evidence_project_time ON evidence_assets (project_id, observed_at);
CREATE INDEX ix_evidence_source ON evidence_assets (source_dataset, source_id);

-- Observations --------------------------------------------------------------
CREATE TABLE observations (
  id                   VARCHAR2(64)  NOT NULL,
  project_id           VARCHAR2(64)  NOT NULL,
  metric               VARCHAR2(64)  NOT NULL,
  value                NUMBER,
  unit                 VARCHAR2(32)  NOT NULL,
  -- Aggregation bucket, e.g. '2026-08'. Oracle will not accept a TIMESTAMP
  -- WITH TIME ZONE in a unique key (ORA-02329), and an explicit bucket key is
  -- clearer anyway: it is what the idempotent MERGE keys on, and it says out
  -- loud that observations are monthly rather than instantaneous.
  period_key           VARCHAR2(16)  NOT NULL,
  period_start         TIMESTAMP WITH TIME ZONE NOT NULL,
  period_end           TIMESTAMP WITH TIME ZONE NOT NULL,
  observed_at          TIMESTAMP WITH TIME ZONE,
  valid_pixel_fraction NUMBER,
  cloud_cover_pct      NUMBER,
  quality_flags        VARCHAR2(400),
  processing_version   VARCHAR2(64)  NOT NULL,
  evidence_asset_id    VARCHAR2(64),
  simulation_status    VARCHAR2(16)  NOT NULL,
  created_at           TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL,
  CONSTRAINT pk_observations PRIMARY KEY (id),
  CONSTRAINT fk_obs_project FOREIGN KEY (project_id) REFERENCES projects (id),
  CONSTRAINT fk_obs_evidence FOREIGN KEY (evidence_asset_id) REFERENCES evidence_assets (id),
  CONSTRAINT ck_obs_sim CHECK (simulation_status IN ('real','simulated','mixed','fallback')),
  CONSTRAINT ck_obs_period CHECK (period_end >= period_start),
  CONSTRAINT ck_obs_fraction CHECK (valid_pixel_fraction IS NULL
                                    OR (valid_pixel_fraction >= 0 AND valid_pixel_fraction <= 1)),
  -- One row per project/metric/period. Re-running the loader must not
  -- duplicate history.
  CONSTRAINT uq_obs_period UNIQUE (project_id, metric, period_key, processing_version)
);

CREATE INDEX ix_obs_project_metric_time ON observations (project_id, metric, period_key);

-- Alerts --------------------------------------------------------------------
CREATE TABLE alerts (
  id                  VARCHAR2(64)  NOT NULL,
  project_id          VARCHAR2(64)  NOT NULL,
  metric              VARCHAR2(64)  NOT NULL,
  rule_version        VARCHAR2(64)  NOT NULL,
  method              VARCHAR2(400) NOT NULL,
  severity            VARCHAR2(16)  DEFAULT 'review' NOT NULL,
  status              VARCHAR2(24)  DEFAULT 'open' NOT NULL,
  observed_value      NUMBER,
  expected_value      NUMBER,
  expected_low        NUMBER,
  expected_high       NUMBER,
  deviation_abs       NUMBER,
  deviation_pct       NUMBER,
  consecutive_periods NUMBER(4),
  period_start        TIMESTAMP WITH TIME ZONE,
  period_end          TIMESTAMP WITH TIME ZONE,
  quality_flags       VARCHAR2(400),
  evidence_ids        CLOB,
  explanation         CLOB          NOT NULL,
  limitations         CLOB          NOT NULL,
  simulation_status   VARCHAR2(16)  NOT NULL,
  created_at          TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL,
  CONSTRAINT pk_alerts PRIMARY KEY (id),
  CONSTRAINT fk_alerts_project FOREIGN KEY (project_id) REFERENCES projects (id),
  CONSTRAINT ck_alerts_severity CHECK (severity IN ('info','review','urgent')),
  CONSTRAINT ck_alerts_status CHECK (status IN ('open','investigating','resolved','dismissed')),
  CONSTRAINT ck_alerts_sim CHECK (simulation_status IN ('real','simulated','mixed','fallback')),
  CONSTRAINT ck_alerts_evidence_json CHECK (evidence_ids IS JSON)
);

CREATE INDEX ix_alerts_project_status ON alerts (project_id, status, created_at);

-- Investigations ------------------------------------------------------------
-- AI (or fallback) output. Never authoritative, always attributable.
CREATE TABLE investigations (
  id                VARCHAR2(64)  NOT NULL,
  alert_id          VARCHAR2(64)  NOT NULL,
  summary           CLOB          NOT NULL,
  hypotheses_json   CLOB          NOT NULL,
  evidence_ids_json CLOB          NOT NULL,
  missing_evidence  CLOB,
  model_id          VARCHAR2(200),
  prompt_version    VARCHAR2(64),
  latency_ms        NUMBER,
  simulation_status VARCHAR2(16)  NOT NULL,
  created_at        TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL,
  CONSTRAINT pk_investigations PRIMARY KEY (id),
  CONSTRAINT fk_investigations_alert FOREIGN KEY (alert_id) REFERENCES alerts (id),
  CONSTRAINT ck_investigations_sim CHECK (simulation_status IN ('real','simulated','mixed','fallback')),
  CONSTRAINT ck_investigations_hyp_json CHECK (hypotheses_json IS JSON),
  CONSTRAINT ck_investigations_ev_json CHECK (evidence_ids_json IS JSON)
);

CREATE INDEX ix_investigations_alert ON investigations (alert_id);

-- Interventions -------------------------------------------------------------
CREATE TABLE interventions (
  id                VARCHAR2(64)  NOT NULL,
  project_id        VARCHAR2(64)  NOT NULL,
  alert_id          VARCHAR2(64),
  action            VARCHAR2(400) NOT NULL,
  actor             VARCHAR2(200) NOT NULL,
  action_date       DATE          NOT NULL,
  expected_outcome  VARCHAR2(1000),
  followup_date     DATE,
  status            VARCHAR2(24)  DEFAULT 'planned' NOT NULL,
  simulation_status VARCHAR2(16)  NOT NULL,
  created_at        TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL,
  CONSTRAINT pk_interventions PRIMARY KEY (id),
  CONSTRAINT fk_interventions_project FOREIGN KEY (project_id) REFERENCES projects (id),
  CONSTRAINT fk_interventions_alert FOREIGN KEY (alert_id) REFERENCES alerts (id),
  CONSTRAINT ck_interventions_status CHECK (status IN ('planned','in_progress','done','abandoned')),
  -- Enforced here on purpose. We have no real field team, so no intervention
  -- in this system may ever claim to be a real one.
  CONSTRAINT ck_interventions_simulated CHECK (simulation_status = 'simulated')
);

CREATE INDEX ix_interventions_project ON interventions (project_id, action_date);

-- Audit events --------------------------------------------------------------
-- Append-only history. Nothing updates these rows; corrections are new rows.
CREATE TABLE audit_events (
  id                     VARCHAR2(64)  NOT NULL,
  project_id             VARCHAR2(64)  NOT NULL,
  event_type             VARCHAR2(48)  NOT NULL,
  subject_table          VARCHAR2(48),
  subject_id             VARCHAR2(64),
  actor                  VARCHAR2(200),
  canonical_manifest     CLOB,
  manifest_sha256        VARCHAR2(64),
  previous_event_sha256  VARCHAR2(64),
  simulation_status      VARCHAR2(16)  NOT NULL,
  created_at             TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL,
  CONSTRAINT pk_audit_events PRIMARY KEY (id),
  CONSTRAINT fk_audit_project FOREIGN KEY (project_id) REFERENCES projects (id),
  CONSTRAINT ck_audit_sim CHECK (simulation_status IN ('real','simulated','mixed','fallback')),
  CONSTRAINT ck_audit_manifest_json CHECK (canonical_manifest IS JSON),
  CONSTRAINT ck_audit_type CHECK (event_type IN (
    'observation_recorded','commitment_approved','alert_raised',
    'investigation_recorded','intervention_logged','remeasurement_recorded'))
);

CREATE INDEX ix_audit_project_time ON audit_events (project_id, created_at);
CREATE UNIQUE INDEX uq_audit_manifest ON audit_events (manifest_sha256);

-- Chain anchors -------------------------------------------------------------
CREATE TABLE chain_anchors (
  id               VARCHAR2(64)  NOT NULL,
  event_id         VARCHAR2(64)  NOT NULL,
  network          VARCHAR2(32)  NOT NULL,
  tx_hash          VARCHAR2(80),
  output_index     NUMBER(6),
  manifest_sha256  VARCHAR2(64)  NOT NULL,
  status           VARCHAR2(24)  DEFAULT 'pending' NOT NULL,
  explorer_url     VARCHAR2(400),
  anchored_at      TIMESTAMP WITH TIME ZONE,
  created_at       TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL,
  CONSTRAINT pk_chain_anchors PRIMARY KEY (id),
  CONSTRAINT fk_anchors_event FOREIGN KEY (event_id) REFERENCES audit_events (id),
  CONSTRAINT ck_anchors_network CHECK (network IN ('ckb-testnet','ckb-mainnet')),
  CONSTRAINT ck_anchors_status CHECK (status IN ('pending','confirmed','failed')),
  -- A confirmed anchor without a transaction hash would be a lie on stage.
  CONSTRAINT ck_anchors_confirmed CHECK (status <> 'confirmed' OR tx_hash IS NOT NULL)
);

CREATE INDEX ix_anchors_event ON chain_anchors (event_id);
CREATE UNIQUE INDEX uq_anchors_tx ON chain_anchors (tx_hash, output_index);
