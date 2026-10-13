-- Tear-down for `make db-reset`. Reverse dependency order.
-- Errors are expected on a clean database; the Makefile tolerates them.
DROP TABLE chain_anchors CASCADE CONSTRAINTS;
DROP TABLE audit_events CASCADE CONSTRAINTS;
DROP TABLE interventions CASCADE CONSTRAINTS;
DROP TABLE investigations CASCADE CONSTRAINTS;
DROP TABLE alerts CASCADE CONSTRAINTS;
DROP TABLE observations CASCADE CONSTRAINTS;
DROP TABLE evidence_assets CASCADE CONSTRAINTS;
DROP TABLE commitments CASCADE CONSTRAINTS;
DROP TABLE projects CASCADE CONSTRAINTS;
-- only present where Oracle Spatial is installed; tolerated when absent
DELETE FROM user_sdo_geom_metadata WHERE table_name = 'PROJECTS';
COMMIT;
