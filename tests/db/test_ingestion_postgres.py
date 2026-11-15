"""Opt-in PostgreSQL checks for document idempotency, jobs and leases."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from uuid import uuid4

import pytest

from app.db.migrations import apply_migrations
from app.services.ingestion.repository import IngestionRepository

DATABASE_URL = os.environ.get("INGESTION_TEST_DATABASE_URL", "")
pytestmark = [
    pytest.mark.db,
    pytest.mark.skipif(not DATABASE_URL, reason="INGESTION_TEST_DATABASE_URL non impostata"),
]


@pytest.fixture()
def repo() -> object:
    psycopg = pytest.importorskip("psycopg")
    conn = psycopg.connect(DATABASE_URL)
    apply_migrations(conn)
    source_id = "test_ingestion_" + uuid4().hex
    conn.execute(
        """
        INSERT INTO ingestion_sources (
            source_id, name, url, source_kind, source_class, polling_interval_s,
            timeout_s, max_retries, registry_hash, provenance
        ) VALUES (%s, %s, %s, 'rss', 'local_news', 60, 5, 0, 'test', '[]'::jsonb)
        """,
        (source_id, "Test ingestion", f"https://example.test/{source_id}"),
    )
    conn.commit()
    repository = IngestionRepository(conn)
    try:
        yield repository, source_id
    finally:
        conn.execute("DELETE FROM ingestion_sources WHERE source_id = %s", (source_id,))
        conn.commit()
        conn.close()


def test_document_upsert_is_idempotent_and_revisioned(repo: object) -> None:
    repository, source_id = repo  # type: ignore[misc]
    first = repository.upsert_document(
        source_id=source_id,
        external_id="doc-1",
        canonical_url="https://example.test/doc-1",
        title="Titolo",
        body_text="Corpo",
        raw_document='{"raw": true}',
        content_hash="hash-1",
        language="it",
        published_at=datetime(2026, 11, 15, tzinfo=timezone.utc),
        published_precision="second",
    )
    assert first.is_new and first.changed and first.revision == 1

    second = repository.upsert_document(
        source_id=source_id,
        external_id="doc-1",
        canonical_url="https://example.test/doc-1",
        title="Titolo",
        body_text="Corpo",
        raw_document='{"raw": true}',
        content_hash="hash-1",
        language="it",
        published_at=datetime(2026, 11, 15, tzinfo=timezone.utc),
        published_precision="second",
    )
    assert second.document_id == first.document_id
    assert second.is_new is False
    assert second.changed is False
    assert second.revision == 1

    changed = repository.upsert_document(
        source_id=source_id,
        external_id="doc-1",
        canonical_url="https://example.test/doc-1",
        title="Titolo aggiornato",
        body_text="Corpo aggiornato",
        raw_document='{"raw": false}',
        content_hash="hash-2",
        language="it",
        published_at=datetime(2026, 11, 15, tzinfo=timezone.utc),
        published_precision="second",
    )
    assert changed.changed is True
    assert changed.revision == 2
    document = repository.document(first.document_id)
    assert document is not None
    assert document["status"] == "new"


def test_interpretation_cache_key_stops_a_second_model_call(repo: object) -> None:
    repository, source_id = repo  # type: ignore[misc]
    document = repository.upsert_document(
        source_id=source_id,
        external_id="doc-cache",
        canonical_url=None,
        title="Titolo",
        body_text="Corpo",
        raw_document="{}",
        content_hash="hash-cache",
        language="it",
        published_at=None,
        published_precision="unknown",
    )
    repository.save_interpretation(
        document.document_id,
        content_hash="hash-cache",
        prompt_version="v1",
        schema_version="1",
        model="small",
        language="it",
        status="ok",
        output={"relevant": False},
        error=None,
        latency_ms=10,
    )
    cached = repository.cached_interpretation(
        document.document_id,
        content_hash="hash-cache",
        prompt_version="v1",
        schema_version="1",
        model="small",
        language="it",
    )
    assert cached is not None
    assert cached["status"] == "ok"


def test_job_lease_and_dedupe(repo: object) -> None:
    repository, source_id = repo  # type: ignore[misc]
    assert repository.enqueue_fetch(source_id) is True
    assert repository.enqueue_fetch(source_id) is True  # ON CONFLICT, not a duplicate
    rows = repository._fetchall(
        """
        SELECT count(*) AS n FROM ingestion_jobs
        WHERE job_type = 'fetch_source' AND source_id = %s
          AND status IN ('pending', 'leased')
        """,
        (source_id,),
    )
    assert rows[0]["n"] == 1
    job = repository.claim_job("worker-test", lease_s=60, source_id=source_id)
    assert job is not None
    assert job.job_type == "fetch_source"
    assert job.source_id == source_id
    assert repository.claim_job("worker-test-2", lease_s=60, source_id=source_id) is None
    repository.complete_job(job.job_id)
    assert repository.claim_job("worker-test-3", lease_s=60, source_id=source_id) is None
