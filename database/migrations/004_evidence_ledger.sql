-- ---------------------------------------------------------------------------
-- Evidence Ledger: one append-only, unforkable history per project on CKB.
--
-- Until now each manifest hash was anchored as a loose cell, and the pipeline
-- rebuilt the whole audit chain on every run. The ledger's type script
-- (evidence-ledger, ckbuilders repo) recomputes a running commitment on every
-- append, so history can no longer be rewritten, reordered, skipped, forked or
-- deleted, by anyone, including us. Loose-cell anchors remain readable.
-- ---------------------------------------------------------------------------

CREATE TABLE ckb_ledgers (
  project_id          VARCHAR2(64)  NOT NULL,
  network             VARCHAR2(32)  NOT NULL,
  type_id             VARCHAR2(80)  NOT NULL,
  type_hash           VARCHAR2(80)  NOT NULL,
  recorder_lock_hash  VARCHAR2(80)  NOT NULL,
  recorder_address    VARCHAR2(200),
  -- where released donations go: the project's own wallet (the recorder by default)
  payout_address      VARCHAR2(200),
  create_tx_hash      VARCHAR2(80)  NOT NULL,
  created_at          TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL,
  CONSTRAINT pk_ckb_ledgers PRIMARY KEY (project_id),
  CONSTRAINT fk_ledgers_project FOREIGN KEY (project_id) REFERENCES projects (id),
  CONSTRAINT ck_ledgers_network CHECK (network IN ('ckb-testnet','ckb-mainnet'))
);

-- Several events now share one append transaction: identify each by its
-- position (ledger_seq) in the project's history.
ALTER TABLE chain_anchors ADD (
  anchor_kind  VARCHAR2(16) DEFAULT 'cell' NOT NULL,
  ledger_seq   NUMBER(12),
  CONSTRAINT ck_anchors_kind CHECK (anchor_kind IN ('cell','ledger')),
  CONSTRAINT ck_anchors_ledger_seq CHECK (anchor_kind = 'cell' OR ledger_seq IS NOT NULL)
);
DROP INDEX uq_anchors_tx;
CREATE UNIQUE INDEX uq_anchors_tx ON chain_anchors (tx_hash, output_index, ledger_seq);

-- Resolving an alert is evidence too: the Evidence Gate releases held funding
-- only once the ledger's open-alert count is back to zero.
ALTER TABLE audit_events DROP CONSTRAINT ck_audit_type;
ALTER TABLE audit_events ADD CONSTRAINT ck_audit_type CHECK (event_type IN (
  'observation_recorded','commitment_approved','alert_raised','alert_resolved',
  'investigation_recorded','intervention_logged','remeasurement_recorded'));
