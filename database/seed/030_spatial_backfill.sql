-- ---------------------------------------------------------------------------
-- Derive native SDO_GEOMETRY from the GeoJSON boundary we already store.
--
-- Runs after the seed, and only where Oracle Spatial exists (applied with
-- --tolerant, so it is a no-op on the local Free container which ships no
-- MDSYS). GeoJSON remains the source of truth; this is a derived convenience
-- for spatial predicates and APEX native map regions, so the two can never
-- disagree about where a project is.
-- ---------------------------------------------------------------------------

UPDATE projects
   SET boundary = SDO_UTIL.FROM_GEOJSON(boundary_geojson)
 WHERE boundary_geojson IS NOT NULL;

COMMIT;
