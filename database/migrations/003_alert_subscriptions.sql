-- ---------------------------------------------------------------------------
-- Alert subscriptions -- a waitlist, not a delivery system.
--
-- No SMS is sent from this table. There is no provider wired up, and the UI
-- says so where someone types their number. It exists so that interest is
-- recorded somewhere real rather than discarded by a form that pretends.
--
-- Deliberately minimal: a phone number is personal data, and this endpoint is
-- public and unauthenticated. We keep the number, the project it is about and
-- when it arrived. Nothing else -- no name, no email, no IP.
-- ---------------------------------------------------------------------------

CREATE TABLE alert_subscriptions (
  id            VARCHAR2(64)  NOT NULL,
  project_id    VARCHAR2(64)  NOT NULL,
  phone         VARCHAR2(32)  NOT NULL,
  created_at    TIMESTAMP WITH TIME ZONE DEFAULT SYSTIMESTAMP NOT NULL,
  -- Every row is a waitlist entry until a provider exists. The column is here
  -- so that the day one does, nobody has to guess which rows were notified.
  notified_at   TIMESTAMP WITH TIME ZONE,
  CONSTRAINT pk_alert_subs       PRIMARY KEY (id),
  CONSTRAINT fk_alert_subs_proj  FOREIGN KEY (project_id) REFERENCES projects (id),
  -- One entry per number per project; re-submitting is not a new subscriber.
  CONSTRAINT uq_alert_subs       UNIQUE (project_id, phone),
  CONSTRAINT ck_alert_subs_phone CHECK (REGEXP_LIKE(phone, '^\+[1-9][0-9]{7,14}$'))
);

CREATE INDEX ix_alert_subs_project ON alert_subscriptions (project_id);
