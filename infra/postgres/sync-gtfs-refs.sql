BEGIN;

-- Stable reference catalogue for GTFS entities used by disruptions.
-- Existing rows are never deleted: entities absent from the new feed remain
-- with is_current = FALSE, so old links keep a valid FK target.

UPDATE reference_entities
SET is_current = FALSE
WHERE domain = 'gtfs' AND dataset_key = :'dataset_key' AND is_current;

INSERT INTO reference_entities (
    entity_key, domain, entity_type, dataset_key, entity_id, service_id,
    display_name, mode, dataset_version, is_current
)
SELECT
    'gtfs:' || :'dataset_key' || ':route:' || route_id,
    'gtfs', 'route', :'dataset_key', route_id, NULL,
    COALESCE(NULLIF(route_short_name, ''), route_long_name, route_id),
    CASE route_type::text
        WHEN '0' THEN 'tram'
        WHEN '1' THEN 'subway'
        WHEN '2' THEN 'rail'
        WHEN '3' THEN 'bus'
        WHEN '4' THEN 'ferry'
        WHEN '5' THEN 'cable'
        WHEN '6' THEN 'aerial'
        WHEN '7' THEN 'funicular'
        ELSE 'other'
    END,
    :'dataset_version', TRUE
FROM :"gtfs_schema".routes
UNION ALL
SELECT
    'gtfs:' || :'dataset_key' || ':trip:' || t.trip_id,
    'gtfs', 'trip', :'dataset_key', t.trip_id,
    t.service_id, COALESCE(NULLIF(t.trip_headsign, ''), t.trip_id),
    CASE r.route_type::text
        WHEN '0' THEN 'tram'
        WHEN '1' THEN 'subway'
        WHEN '2' THEN 'rail'
        WHEN '3' THEN 'bus'
        WHEN '4' THEN 'ferry'
        WHEN '5' THEN 'cable'
        WHEN '6' THEN 'aerial'
        WHEN '7' THEN 'funicular'
        ELSE 'other'
    END,
    :'dataset_version', TRUE
FROM :"gtfs_schema".trips t
LEFT JOIN :"gtfs_schema".routes r ON r.route_id = t.route_id
UNION ALL
SELECT
    'gtfs:' || :'dataset_key' || ':stop:' || stop_id,
    'gtfs', 'stop', :'dataset_key', stop_id, NULL,
    stop_name, NULL, :'dataset_version', TRUE
FROM :"gtfs_schema".stops
ON CONFLICT (entity_key) DO UPDATE SET
    domain = EXCLUDED.domain,
    entity_type = EXCLUDED.entity_type,
    dataset_key = EXCLUDED.dataset_key,
    entity_id = EXCLUDED.entity_id,
    service_id = EXCLUDED.service_id,
    display_name = EXCLUDED.display_name,
    mode = EXCLUDED.mode,
    dataset_version = EXCLUDED.dataset_version,
    is_current = TRUE,
    last_seen_at = NOW();

COMMIT;
