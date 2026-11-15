"""PostgreSQL persistence for ingestion sources, documents, jobs and audit."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from app.config.sources import SourceRegistry


@dataclass(frozen=True)
class DocumentUpsert:
    document_id: int
    status: str
    is_new: bool
    changed: bool
    revision: int
    content_hash: str


@dataclass(frozen=True)
class ClaimedJob:
    job_id: int
    job_type: str
    source_id: str | None
    document_id: int | None
    attempts: int
    max_attempts: int
    payload: dict[str, Any]


class IngestionRepository:
    """Serialized database access for the single ingestion worker process."""

    def __init__(self, conn: Any) -> None:
        self._conn = conn

    def _row(self, cur: Any, row: Any) -> dict[str, Any]:
        if isinstance(row, dict):
            return dict(row)
        if hasattr(row, "keys"):
            return {key: row[key] for key in row.keys()}
        cols = [desc[0] for desc in cur.description]
        return dict(zip(cols, row))

    def _fetchall(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        cur = self._conn.cursor()
        cur.execute(sql, params)
        return [self._row(cur, row) for row in cur.fetchall()]

    def _fetchone(self, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any] | None:
        rows = self._fetchall(sql, params)
        return rows[0] if rows else None

    def _execute(self, sql: str, params: tuple[Any, ...] = ()) -> None:
        cur = self._conn.cursor()
        cur.execute(sql, params)

    def sync_sources(self, registry: SourceRegistry) -> int:
        """Upsert configuration only; runtime cursors/errors are preserved."""
        cur = self._conn.cursor()
        for source in registry.sources:
            cur.execute(
                """
                INSERT INTO ingestion_sources (
                    source_id, name, url, source_kind, source_class, operator_hint,
                    language, timezone, local_relevance, enabled,
                    polling_interval_s, timeout_s, max_retries, registry_hash,
                    provenance, next_run_at, updated_at
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s::jsonb, NOW(), NOW()
                )
                ON CONFLICT (source_id) DO UPDATE SET
                    name = EXCLUDED.name,
                    url = EXCLUDED.url,
                    source_kind = EXCLUDED.source_kind,
                    source_class = EXCLUDED.source_class,
                    operator_hint = EXCLUDED.operator_hint,
                    language = EXCLUDED.language,
                    timezone = EXCLUDED.timezone,
                    local_relevance = EXCLUDED.local_relevance,
                    enabled = EXCLUDED.enabled,
                    polling_interval_s = EXCLUDED.polling_interval_s,
                    timeout_s = EXCLUDED.timeout_s,
                    max_retries = EXCLUDED.max_retries,
                    registry_hash = EXCLUDED.registry_hash,
                    provenance = EXCLUDED.provenance,
                    updated_at = NOW()
                """,
                (
                    source.source_id,
                    source.name,
                    source.url,
                    source.kind,
                    source.source_class,
                    source.operator,
                    source.language,
                    source.timezone,
                    source.local_relevance,
                    source.enabled,
                    source.polling_interval_s,
                    source.timeout_s,
                    source.max_retries,
                    source.registry_hash(),
                    json.dumps(source.provenance, ensure_ascii=False),
                ),
            )
        self._conn.commit()
        return len(registry.sources)

    def list_sources(self, *, enabled_only: bool = False) -> list[dict[str, Any]]:
        where = "WHERE enabled" if enabled_only else ""
        return self._fetchall(
            f"""
            SELECT s.*,
                   (SELECT count(*) FROM ingestion_documents d
                     WHERE d.source_id = s.source_id) AS documents_total,
                   (SELECT count(*) FROM ingestion_documents d
                     WHERE d.source_id = s.source_id AND d.status = 'interpreted')
                     AS documents_interpreted,
                   (SELECT count(*) FROM ingestion_documents d
                     WHERE d.source_id = s.source_id
                       AND d.status IN ('pending','new','needs_review','failed'))
                     AS documents_pending
            FROM ingestion_sources s
            {where}
            ORDER BY s.source_class, s.source_id
            """
        )

    def source(self, source_id: str) -> dict[str, Any] | None:
        return self._fetchone("SELECT * FROM ingestion_sources WHERE source_id = %s", (source_id,))

    def set_source_due(self, source_id: str | None = None) -> int:
        cur = self._conn.cursor()
        if source_id:
            cur.execute(
                "UPDATE ingestion_sources SET next_run_at = NOW(), updated_at = NOW() "
                "WHERE source_id = %s AND enabled",
                (source_id,),
            )
        else:
            cur.execute(
                "UPDATE ingestion_sources SET next_run_at = NOW(), updated_at = NOW() WHERE enabled"
            )
        count = cur.rowcount
        self._conn.commit()
        return int(count)

    def enqueue_fetch(self, source_id: str, *, run_after: datetime | None = None) -> bool:
        now = datetime.now(timezone.utc)
        try:
            self._execute(
                """
                INSERT INTO ingestion_jobs (
                    job_type, source_id, document_id, dedupe_key, priority,
                    run_after, payload, updated_at
                )
                VALUES ('fetch_source', %s, NULL, %s, 10, %s, '{}'::jsonb, NOW())
                ON CONFLICT DO NOTHING
                """,
                (source_id, f"fetch_source:{source_id}", run_after or now),
            )
            self._conn.commit()
            return True
        except Exception:
            self._conn.rollback()
            raise

    def enqueue_interpret(self, document_id: int, *, run_after: datetime | None = None) -> bool:
        now = datetime.now(timezone.utc)
        try:
            self._execute(
                """
                INSERT INTO ingestion_jobs (
                    job_type, document_id, dedupe_key, priority, run_after,
                    payload, updated_at
                )
                VALUES ('interpret_document', %s, %s, 20, %s, '{}'::jsonb, NOW())
                ON CONFLICT DO NOTHING
                """,
                (document_id, f"interpret_document:{document_id}", run_after or now),
            )
            self._conn.commit()
            return True
        except Exception:
            self._conn.rollback()
            raise

    def enqueue_maintenance(self) -> bool:
        try:
            self._execute(
                """
                INSERT INTO ingestion_jobs (
                    job_type, dedupe_key, priority, run_after, payload, updated_at
                )
                VALUES ('maintenance', 'maintenance:global', 5, NOW(), '{}'::jsonb, NOW())
                ON CONFLICT DO NOTHING
                """
            )
            self._conn.commit()
            return True
        except Exception:
            self._conn.rollback()
            raise

    def recover_expired_leases(self, now: datetime | None = None) -> int:
        ref = now or datetime.now(timezone.utc)
        cur = self._conn.cursor()
        cur.execute(
            """
            UPDATE ingestion_jobs
            SET status = CASE WHEN attempts >= max_attempts THEN 'failed' ELSE 'pending' END,
                lease_owner = NULL,
                lease_expires_at = NULL,
                last_error = COALESCE(last_error, 'lease scaduto'),
                updated_at = NOW()
            WHERE status = 'leased' AND lease_expires_at IS NOT NULL
              AND lease_expires_at < %s
            """,
            (ref,),
        )
        jobs = cur.rowcount
        cur.execute(
            """
            UPDATE ingestion_documents
            SET status = 'pending', lease_owner = NULL, lease_expires_at = NULL,
                updated_at = NOW()
            WHERE status = 'interpreting' AND lease_expires_at IS NOT NULL
              AND lease_expires_at < %s
            """,
            (ref,),
        )
        docs = cur.rowcount
        self._conn.commit()
        return int(jobs + docs)

    def claim_job(
        self,
        worker_id: str,
        *,
        lease_s: int,
        now: datetime | None = None,
        source_id: str | None = None,
    ) -> ClaimedJob | None:
        ref = now or datetime.now(timezone.utc)
        expires = ref + timedelta(seconds=lease_s)
        row = self._fetchone(
            """
            WITH candidate AS (
                SELECT job_id
                FROM ingestion_jobs
                WHERE status = 'pending' AND run_after <= %s
                  AND (%s::text IS NULL OR source_id = %s)
                ORDER BY priority, run_after, job_id
                FOR UPDATE SKIP LOCKED
                LIMIT 1
            )
            UPDATE ingestion_jobs j
            SET status = 'leased',
                lease_owner = %s,
                lease_expires_at = %s,
                attempts = j.attempts + 1,
                updated_at = NOW()
            FROM candidate c
            WHERE j.job_id = c.job_id
            RETURNING j.job_id, j.job_type, j.source_id, j.document_id,
                      j.attempts, j.max_attempts, j.payload
            """,
            (ref, source_id, source_id, worker_id, expires),
        )
        self._conn.commit()
        if row is None:
            return None
        payload = row.get("payload")
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except ValueError:
                payload = {}
        return ClaimedJob(
            job_id=int(row["job_id"]),
            job_type=str(row["job_type"]),
            source_id=row.get("source_id"),
            document_id=row.get("document_id"),
            attempts=int(row["attempts"]),
            max_attempts=int(row["max_attempts"]),
            payload=payload if isinstance(payload, dict) else {},
        )

    def complete_job(self, job_id: int) -> None:
        self._execute(
            """
            UPDATE ingestion_jobs
            SET status = 'done', lease_owner = NULL, lease_expires_at = NULL,
                updated_at = NOW()
            WHERE job_id = %s
            """,
            (job_id,),
        )
        self._conn.commit()

    def fail_job(self, job_id: int, error: str, *, retry_after_s: float | None = None) -> None:
        row = self._fetchone(
            "SELECT attempts, max_attempts FROM ingestion_jobs WHERE job_id = %s", (job_id,)
        )
        if row is None:
            return
        final = int(row["attempts"]) >= int(row["max_attempts"])
        run_after = datetime.now(timezone.utc) + timedelta(
            seconds=max(0.0, float(retry_after_s or 0.0))
        )
        self._execute(
            """
            UPDATE ingestion_jobs
            SET status = %s, lease_owner = NULL, lease_expires_at = NULL,
                last_error = %s, run_after = %s, updated_at = NOW()
            WHERE job_id = %s
            """,
            (
                "failed" if final else "pending",
                error[:2000],
                run_after,
                job_id,
            ),
        )
        self._conn.commit()

    def update_source_after_fetch(
        self,
        source_id: str,
        *,
        checked_at: datetime,
        http_status: int | None,
        success: bool,
        error: str | None,
        etag: str | None,
        last_modified: str | None,
        next_run_at: datetime,
    ) -> None:
        self._execute(
            """
            UPDATE ingestion_sources
            SET last_checked_at = %s,
                last_success_at = CASE WHEN %s THEN %s ELSE last_success_at END,
                last_http_status = %s,
                last_error = %s,
                consecutive_failures = CASE WHEN %s THEN 0 ELSE consecutive_failures + 1 END,
                etag = COALESCE(%s, etag),
                last_modified = COALESCE(%s, last_modified),
                next_run_at = %s,
                updated_at = NOW()
            WHERE source_id = %s
            """,
            (
                checked_at,
                success,
                checked_at,
                http_status,
                error,
                success,
                etag,
                last_modified,
                next_run_at,
                source_id,
            ),
        )
        self._conn.commit()

    def record_fetch(self, row: dict[str, Any]) -> None:
        self._execute(
            """
            INSERT INTO ingestion_fetches (
                source_id, started_at, finished_at, http_status, not_modified,
                bytes_received, entries_seen, documents_new, documents_updated,
                documents_filtered, interpretation_jobs, outcome, error, etag,
                last_modified, duration_ms
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                row["source_id"],
                row["started_at"],
                row.get("finished_at"),
                row.get("http_status"),
                bool(row.get("not_modified", False)),
                row.get("bytes_received"),
                int(row.get("entries_seen", 0)),
                int(row.get("documents_new", 0)),
                int(row.get("documents_updated", 0)),
                int(row.get("documents_filtered", 0)),
                int(row.get("interpretation_jobs", 0)),
                row.get("outcome", "ok"),
                row.get("error"),
                row.get("etag"),
                row.get("last_modified"),
                row.get("duration_ms"),
            ),
        )
        self._conn.commit()

    def upsert_document(
        self,
        *,
        source_id: str,
        external_id: str,
        canonical_url: str | None,
        title: str,
        body_text: str | None,
        raw_document: str,
        content_hash: str,
        language: str,
        published_at: datetime | None,
        published_precision: str,
    ) -> DocumentUpsert:
        cur = self._conn.cursor()
        try:
            cur.execute(
                """
                SELECT document_id, content_hash, status, revision
                FROM ingestion_documents
                WHERE source_id = %s AND external_id = %s
                FOR UPDATE
                """,
                (source_id, external_id),
            )
            existing = cur.fetchone()
            now = datetime.now(timezone.utc)
            if existing is None:
                cur.execute(
                    """
                    INSERT INTO ingestion_documents (
                        source_id, external_id, canonical_url, title, body_text,
                        raw_document, content_hash, language, published_at,
                        published_precision, first_seen_at, last_seen_at,
                        status, revision, updated_at
                    )
                    VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        'new', 1, NOW()
                    )
                    RETURNING document_id, revision
                    """,
                    (
                        source_id,
                        external_id,
                        canonical_url,
                        title,
                        body_text,
                        raw_document,
                        content_hash,
                        language,
                        published_at,
                        published_precision,
                        now,
                        now,
                    ),
                )
                inserted = cur.fetchone()
                self._conn.commit()
                doc_id = (
                    int(inserted[0])
                    if not isinstance(inserted, dict)
                    else int(inserted["document_id"])
                )
                revision = (
                    int(inserted[1])
                    if not isinstance(inserted, dict)
                    else int(inserted["revision"])
                )
                return DocumentUpsert(doc_id, "new", True, True, revision, content_hash)

            doc_id = int(existing[0])
            old_hash = str(existing[1])
            old_status = str(existing[2])
            old_revision = int(existing[3])
            changed = old_hash != content_hash
            if not changed:
                cur.execute(
                    """
                    UPDATE ingestion_documents
                    SET last_seen_at = NOW(), canonical_url = %s, updated_at = NOW()
                    WHERE document_id = %s
                    """,
                    (canonical_url, doc_id),
                )
                self._conn.commit()
                return DocumentUpsert(doc_id, old_status, False, False, old_revision, content_hash)

            cur.execute(
                """
                UPDATE ingestion_documents
                SET canonical_url = %s, title = %s, body_text = %s,
                    raw_document = %s, content_hash = %s, language = %s,
                    published_at = %s, published_precision = %s,
                    last_seen_at = NOW(), status = 'new',
                    revision = revision + 1, is_relevant = NULL,
                    relevance_reason = NULL, attempt_count = 0,
                    last_error = NULL, interpretation_key = NULL,
                    catalogued_at = NULL, lease_owner = NULL,
                    lease_expires_at = NULL, updated_at = NOW()
                WHERE document_id = %s
                """,
                (
                    canonical_url,
                    title,
                    body_text,
                    raw_document,
                    content_hash,
                    language,
                    published_at,
                    published_precision,
                    doc_id,
                ),
            )
            self._conn.commit()
            return DocumentUpsert(doc_id, "new", False, True, old_revision + 1, content_hash)
        except Exception:
            self._conn.rollback()
            raise

    def document(self, document_id: int) -> dict[str, Any] | None:
        return self._fetchone(
            """
            SELECT d.*, s.name AS source_name, s.url AS source_url,
                   s.source_class, s.source_kind, s.operator_hint,
                   s.language AS source_language, s.timezone AS source_timezone,
                   s.local_relevance
            FROM ingestion_documents d
            JOIN ingestion_sources s ON s.source_id = d.source_id
            WHERE d.document_id = %s
            """,
            (document_id,),
        )

    def list_documents(
        self,
        *,
        status: str | None = None,
        source_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        clauses = []
        params: list[Any] = []
        if status:
            clauses.append("d.status = %s")
            params.append(status)
        if source_id:
            clauses.append("d.source_id = %s")
            params.append(source_id)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(max(1, min(limit, 500)))
        return self._fetchall(
            f"""
            SELECT d.document_id, d.source_id, d.external_id, d.canonical_url,
                   d.title, d.published_at, d.first_seen_at, d.last_seen_at,
                   d.status, d.revision, d.is_relevant, d.relevance_reason,
                   d.attempt_count, d.last_error, d.interpretation_key,
                   d.catalogued_at, s.name AS source_name
            FROM ingestion_documents d
            JOIN ingestion_sources s ON s.source_id = d.source_id
            {where}
            ORDER BY d.published_at DESC NULLS LAST, d.document_id DESC
            LIMIT %s
            """,
            tuple(params),
        )

    def mark_document(
        self,
        document_id: int,
        *,
        status: str,
        is_relevant: bool | None = None,
        relevance_reason: str | None = None,
        error: str | None = None,
        catalogued: bool = False,
    ) -> None:
        self._execute(
            """
            UPDATE ingestion_documents
            SET status = %s,
                is_relevant = COALESCE(%s, is_relevant),
                relevance_reason = COALESCE(%s, relevance_reason),
                last_error = %s,
                catalogued_at = CASE WHEN %s THEN NOW() ELSE catalogued_at END,
                lease_owner = NULL,
                lease_expires_at = NULL,
                updated_at = NOW()
            WHERE document_id = %s
            """,
            (
                status,
                is_relevant,
                relevance_reason,
                error,
                catalogued,
                document_id,
            ),
        )
        self._conn.commit()

    def lease_document(self, document_id: int, worker_id: str, lease_s: int) -> bool:
        expires = datetime.now(timezone.utc) + timedelta(seconds=lease_s)
        cur = self._conn.cursor()
        cur.execute(
            """
            UPDATE ingestion_documents
            SET status = 'interpreting', lease_owner = %s, lease_expires_at = %s,
                updated_at = NOW()
            WHERE document_id = %s
              AND status IN ('new', 'pending', 'needs_review', 'failed')
            """,
            (worker_id, expires, document_id),
        )
        changed = cur.rowcount
        self._conn.commit()
        return bool(changed)

    def increment_attempt(self, document_id: int, error: str | None = None) -> int:
        cur = self._conn.cursor()
        cur.execute(
            """
            UPDATE ingestion_documents
            SET attempt_count = attempt_count + 1, last_error = %s, updated_at = NOW()
            WHERE document_id = %s
            RETURNING attempt_count
            """,
            (error, document_id),
        )
        row = cur.fetchone()
        self._conn.commit()
        return int(row[0]) if row else 0

    def cached_interpretation(
        self,
        document_id: int,
        *,
        content_hash: str,
        prompt_version: str,
        schema_version: str,
        model: str,
        language: str,
    ) -> dict[str, Any] | None:
        return self._fetchone(
            """
            SELECT status, output, error, latency_ms, created_at
            FROM ingestion_interpretations
            WHERE document_id = %s AND content_hash = %s
              AND prompt_version = %s AND schema_version = %s
              AND model = %s AND language = %s
            """,
            (
                document_id,
                content_hash,
                prompt_version,
                schema_version,
                model,
                language,
            ),
        )

    def save_interpretation(
        self,
        document_id: int,
        *,
        content_hash: str,
        prompt_version: str,
        schema_version: str,
        model: str,
        language: str,
        status: str,
        output: dict[str, Any] | None,
        error: str | None,
        latency_ms: int | None,
    ) -> None:
        self._execute(
            """
            INSERT INTO ingestion_interpretations (
                document_id, content_hash, prompt_version, schema_version,
                model, language, status, output, error, latency_ms
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s)
            ON CONFLICT (
                document_id, content_hash, prompt_version, schema_version,
                model, language
            ) DO UPDATE SET
                status = EXCLUDED.status,
                output = EXCLUDED.output,
                error = EXCLUDED.error,
                latency_ms = EXCLUDED.latency_ms,
                created_at = NOW()
            """,
            (
                document_id,
                content_hash,
                prompt_version,
                schema_version,
                model,
                language,
                status,
                json.dumps(output, ensure_ascii=False) if output is not None else None,
                error,
                latency_ms,
            ),
        )
        self._conn.commit()

    def status_summary(self) -> dict[str, Any]:
        sources = self._fetchall(
            """
            SELECT count(*) AS total,
                   count(*) FILTER (WHERE enabled) AS enabled,
                   count(*) FILTER (WHERE last_error IS NOT NULL) AS with_error,
                   count(*) FILTER (WHERE last_checked_at IS NOT NULL) AS checked
            FROM ingestion_sources
            """
        )[0]
        docs = self._fetchall(
            "SELECT status, count(*) AS n FROM ingestion_documents GROUP BY status"
        )
        fetches = self._fetchall(
            """
            SELECT count(*) AS total,
                   count(*) FILTER (WHERE outcome = 'ok') AS ok,
                   count(*) FILTER (WHERE outcome = 'not_modified') AS not_modified,
                   count(*) FILTER (WHERE outcome NOT IN ('ok','not_modified')) AS failed
            FROM ingestion_fetches
            """
        )[0]
        jobs = self._fetchall("SELECT status, count(*) AS n FROM ingestion_jobs GROUP BY status")
        return {
            "sources": sources,
            "documents_by_status": {row["status"]: int(row["n"]) for row in docs},
            "fetches": fetches,
            "jobs_by_status": {row["status"]: int(row["n"]) for row in jobs},
        }

    def fetches(self, *, source_id: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
        params: list[Any] = []
        where = ""
        if source_id:
            where = "WHERE source_id = %s"
            params.append(source_id)
        params.append(max(1, min(limit, 500)))
        return self._fetchall(
            f"""
            SELECT * FROM ingestion_fetches {where}
            ORDER BY started_at DESC LIMIT %s
            """,
            tuple(params),
        )


__all__ = ["ClaimedJob", "DocumentUpsert", "IngestionRepository"]
