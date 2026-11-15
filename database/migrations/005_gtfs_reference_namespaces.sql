-- sqlite: skip
-- Dataset-scoped identities prevent ANM/EAV ID collisions. The migration
-- runs in the migration runner's transaction. Audit payloads remain unchanged.
LOCK TABLE reference_entities, service_alert_links IN ACCESS EXCLUSIVE MODE;

CREATE TEMP TABLE gtfs_reference_key_migration ON COMMIT DROP AS
SELECT entity_key AS old_key,
       'gtfs:' || dataset_key || ':' || entity_type || ':' || entity_id AS new_key,
       dataset_key
FROM reference_entities
WHERE domain = 'gtfs';

-- A pre-existing mismatched link cannot safely be reassigned to the dataset
-- of an overwritten legacy reference. Preserve the stated dataset and raw
-- evidence, and require explicit re-resolution instead.
UPDATE service_alert_links l
SET entity_key = NULL, resolution_status = 'unresolved',
    resolution_note = concat_ws('; ', l.resolution_note, 'legacy_dataset_mismatch'),
    updated_at = NOW()
FROM gtfs_reference_key_migration m
WHERE l.entity_key = m.old_key
  AND l.dataset_key IS NOT NULL AND l.dataset_key <> m.dataset_key;

ALTER TABLE service_alert_links
    DROP CONSTRAINT service_alert_links_entity_key_fkey;
ALTER TABLE service_alert_links
    ADD CONSTRAINT service_alert_links_entity_key_fkey
    FOREIGN KEY (entity_key) REFERENCES reference_entities (entity_key)
    ON UPDATE CASCADE;

UPDATE reference_entities r
SET entity_key = m.new_key
FROM gtfs_reference_key_migration m
WHERE r.entity_key = m.old_key AND m.old_key <> m.new_key;

UPDATE service_alert_links l
SET link_ref = m.new_key || substring(l.link_ref FROM length(m.old_key) + 1),
    dataset_key = m.dataset_key
FROM gtfs_reference_key_migration m
WHERE l.entity_key = m.new_key
  AND left(l.link_ref, length(m.old_key) + 1) = m.old_key || '|'
  AND m.old_key <> m.new_key;

ALTER TABLE reference_entities
    ADD CONSTRAINT reference_entities_gtfs_namespace_check CHECK (
        domain <> 'gtfs' OR (
            dataset_key ~ '^[a-z0-9_]+$'
            AND entity_type IN ('route', 'trip', 'stop')
            AND entity_key = 'gtfs:' || dataset_key || ':' || entity_type || ':' || entity_id
        )
    );
