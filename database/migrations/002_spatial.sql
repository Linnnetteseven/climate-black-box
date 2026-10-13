-- ---------------------------------------------------------------------------
-- Optional: native Oracle Spatial geometry.
--
-- Applied with --tolerant, because Oracle Spatial is not present on every
-- edition. The container image used for local development (gvenzl/oracle-free
-- :23-slim) ships without MDSYS entirely, while Autonomous Database has
-- Spatial installed as standard. So this migration is additive and skippable:
--
--   * boundary_geojson in 001_core.sql is the source of truth, everywhere.
--   * boundary (SDO_GEOMETRY) is a derived convenience for spatial predicates
--     and APEX native map regions, populated only where Spatial exists.
--
-- Nothing in the API or the demo depends on this file succeeding. If it is
-- skipped, the map still renders -- it reads the GeoJSON.
-- ---------------------------------------------------------------------------

ALTER TABLE projects ADD (boundary SDO_GEOMETRY);

INSERT INTO user_sdo_geom_metadata (table_name, column_name, diminfo, srid)
VALUES ('PROJECTS', 'BOUNDARY',
        SDO_DIM_ARRAY(
          SDO_DIM_ELEMENT('LONG', -180, 180, 0.0000005),
          SDO_DIM_ELEMENT('LAT',   -90,  90, 0.0000005)),
        4326);

CREATE INDEX ix_projects_boundary ON projects (boundary) INDEXTYPE IS MDSYS.SPATIAL_INDEX_V2;

-- NOTE: the geometry itself is derived in database/seed/030_spatial_backfill.sql,
-- which runs AFTER the seed. Doing it here would be a no-op on an empty table
-- and would leave boundary NULL with no error to notice.

COMMIT;
