BEGIN;

-- Stable reference catalogue for OSM ways/POIs used by disruptions.
-- Rows are retained with is_current = FALSE when an object disappears from a
-- newer extract; links therefore keep a valid FK target and can be reported
-- as historical instead of silently pointing at a current object.

UPDATE reference_entities
SET is_current = FALSE
WHERE domain = 'osm' AND dataset_key = :'dataset_key' AND is_current;

INSERT INTO reference_entities (
    entity_key, domain, entity_type, dataset_key, entity_id, service_id,
    display_name, mode, dataset_version, is_current
)
SELECT
    'osm:way:' || osm_key, 'osm', 'osm_way', :'dataset_key', osm_key, NULL,
    name, 'road', :'dataset_version', TRUE
FROM :"osm_schema".osm_ways
WHERE is_current
UNION ALL
SELECT
    'osm:poi:' || osm_key, 'osm', 'osm_poi', :'dataset_key', osm_key, NULL,
    name, 'poi', :'dataset_version', TRUE
FROM :"osm_schema".pois
WHERE is_current
ON CONFLICT (entity_key) DO UPDATE SET
    domain = EXCLUDED.domain,
    entity_type = EXCLUDED.entity_type,
    dataset_key = EXCLUDED.dataset_key,
    entity_id = EXCLUDED.entity_id,
    display_name = EXCLUDED.display_name,
    mode = EXCLUDED.mode,
    dataset_version = EXCLUDED.dataset_version,
    is_current = TRUE,
    last_seen_at = NOW();

COMMIT;
