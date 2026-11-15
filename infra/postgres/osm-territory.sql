-- sqlite: skip
-- Territorio OSM in PostGIS: schema dedicato, separato da public e gtfs_eav.
-- Le tabelle pubblicate hanno OID stabili: il refresh aggiorna per osm_key e
-- conserva le righe non più presenti con is_current = FALSE. Non si rinomina
-- lo schema pubblicato, quindi eventuali FK future restano valide.

CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE SCHEMA IF NOT EXISTS osm_territory;

CREATE TABLE IF NOT EXISTS osm_imports (
    import_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    dataset_key TEXT NOT NULL,
    source_url TEXT,
    source_sha256 TEXT NOT NULL,
    dataset_version TEXT NOT NULL,
    staging_schema TEXT NOT NULL,
    target_schema TEXT NOT NULL,
    importer_name TEXT NOT NULL,
    importer_version TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    finished_at TIMESTAMPTZ,
    status TEXT NOT NULL CHECK (status IN ('staging', 'validated', 'published', 'failed')),
    row_counts JSONB,
    detail TEXT
);

CREATE INDEX IF NOT EXISTS idx_osm_imports_dataset_status
    ON osm_imports (dataset_key, status, started_at);

CREATE TABLE IF NOT EXISTS osm_datasets (
    dataset_key TEXT PRIMARY KEY,
    source_url TEXT,
    source_sha256 TEXT NOT NULL,
    dataset_version TEXT NOT NULL,
    osm_snapshot TEXT,
    osm_timestamp TIMESTAMPTZ,
    data_timestamp TIMESTAMPTZ,
    attribution TEXT NOT NULL,
    importer_name TEXT NOT NULL,
    importer_version TEXT NOT NULL,
    imported_at TIMESTAMPTZ NOT NULL,
    published_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    row_counts JSONB NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_osm_datasets_active
    ON osm_datasets (dataset_key, is_active);

CREATE TABLE IF NOT EXISTS osm_territory.osm_ways (
    osm_key TEXT PRIMARY KEY,
    osm_type TEXT NOT NULL CHECK (osm_type = 'way'),
    osm_id BIGINT NOT NULL,
    name TEXT,
    name_it TEXT,
    ref TEXT,
    highway TEXT,
    access TEXT,
    foot TEXT,
    bicycle TEXT,
    motor_vehicle TEXT,
    vehicle TEXT,
    oneway TEXT,
    junction TEXT,
    bridge TEXT,
    tunnel TEXT,
    layer TEXT,
    surface TEXT,
    service TEXT,
    maxspeed TEXT,
    lanes TEXT,
    width TEXT,
    tracktype TEXT,
    smoothness TEXT,
    wheelchair TEXT,
    incline TEXT,
    sidewalk TEXT,
    cycleway TEXT,
    footway TEXT,
    segregated TEXT,
    construction TEXT,
    route TEXT,
    tags JSONB NOT NULL,
    geom geometry(LineString, 4326) NOT NULL,
    source_id TEXT NOT NULL,
    dataset_version TEXT NOT NULL,
    osm_version INTEGER,
    osm_timestamp TIMESTAMPTZ,
    ingested_at TIMESTAMPTZ NOT NULL,
    is_current BOOLEAN NOT NULL DEFAULT TRUE,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_osm_ways_name
    ON osm_territory.osm_ways (lower(name));
CREATE INDEX IF NOT EXISTS idx_osm_ways_name_trgm
    ON osm_territory.osm_ways USING GIN (lower(name) gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_osm_ways_ref
    ON osm_territory.osm_ways (lower(ref));
CREATE INDEX IF NOT EXISTS idx_osm_ways_highway
    ON osm_territory.osm_ways (highway);
CREATE INDEX IF NOT EXISTS idx_osm_ways_geom
    ON osm_territory.osm_ways USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_osm_ways_tags
    ON osm_territory.osm_ways USING GIN (tags jsonb_path_ops);

CREATE TABLE IF NOT EXISTS osm_territory.pois (
    osm_key TEXT PRIMARY KEY,
    osm_type TEXT NOT NULL CHECK (osm_type IN ('node', 'way', 'relation')),
    osm_id BIGINT NOT NULL,
    name TEXT,
    name_it TEXT,
    ref TEXT,
    operator TEXT,
    brand TEXT,
    addr_street TEXT,
    addr_housenumber TEXT,
    addr_city TEXT,
    phone TEXT,
    website TEXT,
    opening_hours TEXT,
    wheelchair TEXT,
    category TEXT,
    category_value TEXT,
    tags JSONB NOT NULL,
    geom geometry(Geometry, 4326) NOT NULL,
    label_point geometry(Point, 4326) NOT NULL,
    source_id TEXT NOT NULL,
    dataset_version TEXT NOT NULL,
    osm_version INTEGER,
    osm_timestamp TIMESTAMPTZ,
    ingested_at TIMESTAMPTZ NOT NULL,
    is_current BOOLEAN NOT NULL DEFAULT TRUE,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_pois_name
    ON osm_territory.pois (lower(name));
CREATE INDEX IF NOT EXISTS idx_pois_name_trgm
    ON osm_territory.pois USING GIN (lower(name) gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_pois_ref
    ON osm_territory.pois (lower(ref));
CREATE INDEX IF NOT EXISTS idx_pois_category
    ON osm_territory.pois (category, category_value);
CREATE INDEX IF NOT EXISTS idx_pois_geom
    ON osm_territory.pois USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_pois_label_point
    ON osm_territory.pois USING GIST (label_point);
CREATE INDEX IF NOT EXISTS idx_pois_tags
    ON osm_territory.pois USING GIN (tags jsonb_path_ops);
