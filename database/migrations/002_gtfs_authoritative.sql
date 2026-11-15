-- GTFS autorevole e metadati dell'importazione.
--
-- La rete GTFS vive in uno schema dedicato (es. gtfs_eav), non in public:
-- evita collisioni con le tabelle applicative e rende esplicita la fonte.
-- Le tabelle seguenti registrano l'import e il dataset pubblicato; non sono
-- una copia della rete e non vengono alimentate dal seed demo.

ALTER TABLE stops ALTER COLUMN zone_id DROP NOT NULL;

CREATE TABLE IF NOT EXISTS gtfs_imports (
    import_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    dataset_key TEXT NOT NULL,
    operator_id TEXT NOT NULL,
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

CREATE INDEX IF NOT EXISTS idx_gtfs_imports_dataset_status
    ON gtfs_imports (dataset_key, status, started_at);

CREATE TABLE IF NOT EXISTS gtfs_datasets (
    dataset_key TEXT PRIMARY KEY,
    operator_id TEXT NOT NULL,
    operator_name TEXT NOT NULL,
    agency_ids TEXT NOT NULL,
    source_url TEXT,
    source_sha256 TEXT NOT NULL,
    dataset_version TEXT NOT NULL,
    gtfs_schema TEXT NOT NULL,
    service_start DATE,
    service_end DATE,
    importer_name TEXT NOT NULL,
    importer_version TEXT NOT NULL,
    imported_at TIMESTAMPTZ NOT NULL,
    published_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    row_counts JSONB NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE INDEX IF NOT EXISTS idx_gtfs_datasets_active
    ON gtfs_datasets (dataset_key, is_active);
