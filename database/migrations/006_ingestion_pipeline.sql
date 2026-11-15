-- sqlite: skip
-- Ingestion documents, cursors, jobs/leases and interpretation audit.
-- This migration is additive: it does not change or replace service_alerts,
-- service_alert_links, reference_entities or any GTFS/OSM table.

CREATE TABLE IF NOT EXISTS ingestion_sources (
    source_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    url TEXT NOT NULL,
    source_kind TEXT NOT NULL,
    source_class TEXT NOT NULL,
    operator_hint TEXT,
    language TEXT NOT NULL DEFAULT 'it',
    timezone TEXT NOT NULL DEFAULT 'Europe/Rome',
    local_relevance TEXT NOT NULL DEFAULT 'required',
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    polling_interval_s INTEGER NOT NULL DEFAULT 900 CHECK (polling_interval_s > 0),
    timeout_s INTEGER NOT NULL DEFAULT 20 CHECK (timeout_s > 0),
    max_retries INTEGER NOT NULL DEFAULT 3 CHECK (max_retries >= 0),
    next_run_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_checked_at TIMESTAMPTZ,
    last_success_at TIMESTAMPTZ,
    last_http_status INTEGER,
    last_error TEXT,
    consecutive_failures INTEGER NOT NULL DEFAULT 0,
    etag TEXT,
    last_modified TEXT,
    cursor_ts TIMESTAMPTZ,
    registry_hash TEXT NOT NULL DEFAULT '',
    provenance JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (url)
);

CREATE INDEX IF NOT EXISTS idx_ingestion_sources_due
    ON ingestion_sources (enabled, next_run_at);
CREATE INDEX IF NOT EXISTS idx_ingestion_sources_class
    ON ingestion_sources (source_class, enabled);

CREATE TABLE IF NOT EXISTS ingestion_fetches (
    fetch_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES ingestion_sources (source_id) ON DELETE CASCADE,
    started_at TIMESTAMPTZ NOT NULL,
    finished_at TIMESTAMPTZ,
    http_status INTEGER,
    not_modified BOOLEAN NOT NULL DEFAULT FALSE,
    bytes_received INTEGER,
    entries_seen INTEGER NOT NULL DEFAULT 0,
    documents_new INTEGER NOT NULL DEFAULT 0,
    documents_updated INTEGER NOT NULL DEFAULT 0,
    documents_filtered INTEGER NOT NULL DEFAULT 0,
    interpretation_jobs INTEGER NOT NULL DEFAULT 0,
    outcome TEXT NOT NULL DEFAULT 'running',
    error TEXT,
    etag TEXT,
    last_modified TEXT,
    duration_ms INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ingestion_fetches_source
    ON ingestion_fetches (source_id, started_at DESC);

CREATE TABLE IF NOT EXISTS ingestion_documents (
    document_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES ingestion_sources (source_id) ON DELETE CASCADE,
    external_id TEXT NOT NULL,
    canonical_url TEXT,
    title TEXT NOT NULL,
    body_text TEXT,
    raw_document TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    language TEXT NOT NULL DEFAULT 'it',
    published_at TIMESTAMPTZ,
    published_precision TEXT NOT NULL DEFAULT 'unknown',
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status TEXT NOT NULL DEFAULT 'new' CHECK (
        status IN (
            'new', 'filtered', 'pending', 'interpreting', 'interpreted',
            'irrelevant', 'needs_review', 'failed'
        )
    ),
    revision INTEGER NOT NULL DEFAULT 1,
    is_relevant BOOLEAN,
    relevance_reason TEXT,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    interpretation_key TEXT,
    catalogued_at TIMESTAMPTZ,
    lease_owner TEXT,
    lease_expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (source_id, external_id)
);

CREATE INDEX IF NOT EXISTS idx_ingestion_documents_status
    ON ingestion_documents (status, updated_at);
CREATE INDEX IF NOT EXISTS idx_ingestion_documents_source
    ON ingestion_documents (source_id, published_at DESC);
CREATE INDEX IF NOT EXISTS idx_ingestion_documents_hash
    ON ingestion_documents (content_hash);
CREATE INDEX IF NOT EXISTS idx_ingestion_documents_lease
    ON ingestion_documents (status, lease_expires_at)
    WHERE status = 'interpreting';

CREATE TABLE IF NOT EXISTS ingestion_interpretations (
    interpretation_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    document_id BIGINT NOT NULL REFERENCES ingestion_documents (document_id) ON DELETE CASCADE,
    content_hash TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    model TEXT NOT NULL,
    language TEXT NOT NULL DEFAULT 'it',
    status TEXT NOT NULL CHECK (status IN ('ok', 'irrelevant', 'invalid', 'error')),
    output JSONB,
    error TEXT,
    latency_ms INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (document_id, content_hash, prompt_version, schema_version, model, language)
);

CREATE INDEX IF NOT EXISTS idx_ingestion_interpretations_document
    ON ingestion_interpretations (document_id, created_at DESC);

CREATE TABLE IF NOT EXISTS ingestion_jobs (
    job_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    job_type TEXT NOT NULL CHECK (job_type IN ('fetch_source', 'interpret_document', 'maintenance')),
    source_id TEXT REFERENCES ingestion_sources (source_id) ON DELETE CASCADE,
    document_id BIGINT REFERENCES ingestion_documents (document_id) ON DELETE CASCADE,
    dedupe_key TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (
        status IN ('pending', 'leased', 'done', 'failed', 'cancelled')
    ),
    priority INTEGER NOT NULL DEFAULT 100,
    attempts INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 4,
    run_after TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    lease_owner TEXT,
    lease_expires_at TIMESTAMPTZ,
    last_error TEXT,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_ingestion_jobs_active_dedupe
    ON ingestion_jobs (dedupe_key)
    WHERE status IN ('pending', 'leased');
CREATE INDEX IF NOT EXISTS idx_ingestion_jobs_claim
    ON ingestion_jobs (status, run_after, priority, job_id);

-- Reading the real profile must not depend on fixture rows. This index does
-- not change data; it only makes the read-time simulation filter cheap.
CREATE INDEX IF NOT EXISTS idx_service_alerts_real_active
    ON service_alerts (is_simulated, lifecycle_status, valid_from, valid_to);
