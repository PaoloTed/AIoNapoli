-- sqlite: skip
-- Evoluzione della tabella service_alerts esistente: nessun secondo archivio.
-- Le colonne sono aggiunte con default compatibili con il connettore RSS
-- legacy; i nuovi campi e i collegamenti sono gestiti dal repository 2C.

ALTER TABLE service_alerts ADD COLUMN IF NOT EXISTS alert_type TEXT NOT NULL DEFAULT 'info';
ALTER TABLE service_alerts ADD COLUMN IF NOT EXISTS effect TEXT NOT NULL DEFAULT 'info';
ALTER TABLE service_alerts ADD COLUMN IF NOT EXISTS source_url TEXT;
ALTER TABLE service_alerts ADD COLUMN IF NOT EXISTS content_hash TEXT;
ALTER TABLE service_alerts ADD COLUMN IF NOT EXISTS published_at TIMESTAMPTZ;
UPDATE service_alerts SET published_at = valid_from WHERE published_at IS NULL;
ALTER TABLE service_alerts ALTER COLUMN published_at SET DEFAULT NOW();
ALTER TABLE service_alerts ALTER COLUMN published_at SET NOT NULL;
ALTER TABLE service_alerts ADD COLUMN IF NOT EXISTS observed_at TIMESTAMPTZ;
ALTER TABLE service_alerts ADD COLUMN IF NOT EXISTS timezone TEXT NOT NULL DEFAULT 'Europe/Rome';
ALTER TABLE service_alerts ADD COLUMN IF NOT EXISTS lifecycle_status TEXT NOT NULL DEFAULT 'active';
ALTER TABLE service_alerts ADD COLUMN IF NOT EXISTS verification_status TEXT NOT NULL DEFAULT 'unverified';
ALTER TABLE service_alerts ADD COLUMN IF NOT EXISTS uncertainty TEXT NOT NULL DEFAULT 'medium';
ALTER TABLE service_alerts ADD COLUMN IF NOT EXISTS next_review_at TIMESTAMPTZ;
ALTER TABLE service_alerts ADD COLUMN IF NOT EXISTS recurrence JSONB;
ALTER TABLE service_alerts ADD COLUMN IF NOT EXISTS revision INTEGER NOT NULL DEFAULT 1;
ALTER TABLE service_alerts ADD COLUMN IF NOT EXISTS resolved_at TIMESTAMPTZ;
ALTER TABLE service_alerts ADD COLUMN IF NOT EXISTS cancelled_at TIMESTAMPTZ;
ALTER TABLE service_alerts ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();

ALTER TABLE service_alerts ADD CONSTRAINT service_alerts_effect_check
    CHECK (effect IN ('block', 'penalize', 'info'));
ALTER TABLE service_alerts ADD CONSTRAINT service_alerts_lifecycle_check
    CHECK (lifecycle_status IN ('draft', 'active', 'resolved', 'cancelled', 'expired'));
ALTER TABLE service_alerts ADD CONSTRAINT service_alerts_verification_check
    CHECK (verification_status IN ('verified', 'unverified', 'needs_review', 'stale'));
ALTER TABLE service_alerts ADD CONSTRAINT service_alerts_uncertainty_check
    CHECK (uncertainty IN ('low', 'medium', 'high'));

CREATE INDEX IF NOT EXISTS idx_service_alerts_lifecycle
    ON service_alerts (lifecycle_status, valid_from, valid_to);
CREATE INDEX IF NOT EXISTS idx_service_alerts_published
    ON service_alerts (published_at);

CREATE TABLE IF NOT EXISTS reference_entities (
    entity_key TEXT PRIMARY KEY,
    domain TEXT NOT NULL CHECK (domain IN ('gtfs', 'osm')),
    entity_type TEXT NOT NULL CHECK (entity_type IN ('route', 'trip', 'stop', 'osm_way', 'osm_poi')),
    dataset_key TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    service_id TEXT,
    display_name TEXT,
    mode TEXT,
    dataset_version TEXT NOT NULL,
    is_current BOOLEAN NOT NULL DEFAULT TRUE,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (domain, dataset_key, entity_type, entity_id)
);

CREATE INDEX IF NOT EXISTS idx_reference_entities_current
    ON reference_entities (domain, dataset_key, entity_type, is_current);
CREATE INDEX IF NOT EXISTS idx_reference_entities_name
    ON reference_entities (lower(display_name));

CREATE TABLE IF NOT EXISTS service_alert_links (
    link_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_id TEXT NOT NULL,
    alert_id TEXT NOT NULL,
    link_ref TEXT NOT NULL,
    entity_type TEXT NOT NULL CHECK (
        entity_type IN ('route', 'trip', 'stop', 'osm_way', 'osm_poi')
    ),
    entity_key TEXT REFERENCES reference_entities (entity_key),
    raw_reference TEXT NOT NULL,
    resolution_status TEXT NOT NULL CHECK (
        resolution_status IN ('resolved', 'historical', 'unresolved')
    ),
    resolution_note TEXT,
    dataset_key TEXT,
    dataset_version TEXT,
    direction TEXT CHECK (direction IN ('both', 'forward', 'backward')),
    mode TEXT,
    from_stop_id TEXT,
    to_stop_id TEXT,
    from_stop_sequence INTEGER,
    to_stop_sequence INTEGER,
    service_date DATE,
    service_active BOOLEAN,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    is_current BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (source_id, alert_id, link_ref),
    FOREIGN KEY (source_id, alert_id)
        REFERENCES service_alerts (source_id, alert_id) ON DELETE CASCADE,
    CHECK (
        (resolution_status IN ('resolved', 'historical') AND entity_key IS NOT NULL)
        OR (resolution_status = 'unresolved' AND entity_key IS NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_service_alert_links_alert
    ON service_alert_links (source_id, alert_id, is_current);
CREATE INDEX IF NOT EXISTS idx_service_alert_links_entity
    ON service_alert_links (entity_key, is_current);

CREATE TABLE IF NOT EXISTS service_alert_revisions (
    revision_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_id TEXT NOT NULL,
    alert_id TEXT NOT NULL,
    revision INTEGER NOT NULL,
    content_hash TEXT NOT NULL,
    payload JSONB NOT NULL,
    recorded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (source_id, alert_id, revision),
    FOREIGN KEY (source_id, alert_id)
        REFERENCES service_alerts (source_id, alert_id) ON DELETE CASCADE
);

ALTER TABLE osm_datasets ADD COLUMN IF NOT EXISTS data_timestamp TIMESTAMPTZ;

CREATE OR REPLACE VIEW v_service_alerts_active AS
SELECT *
FROM service_alerts
WHERE lifecycle_status = 'active'
  AND published_at <= NOW()
  AND valid_from <= NOW()
  AND (valid_to IS NULL OR valid_to >= NOW());
