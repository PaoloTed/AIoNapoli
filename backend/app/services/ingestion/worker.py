"""Separate ingestion worker: fetch, normalize, interpret and catalogue."""

from __future__ import annotations

import hashlib
import json
import os
import signal
import socket
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from app.config.sources import SourceDefinition, SourceRegistry, load_source_registry
from app.db.migrations import apply_migrations
from app.db.session import get_connection
from app.domain.models.config import AppConfig
from app.domain.models.disruption import DisruptionRecord
from app.repositories.disruptions import DisruptionRepository
from app.services.ingestion.catalogue import DisruptionCataloguer
from app.services.ingestion.extraction import ExtractionError, ExtractionOutcome, NewsExtractor
from app.services.ingestion.parsing import (
    FeedParseError,
    ParsedEntry,
    parse_anm_document,
    parse_feed_bytes,
    raw_document_json,
)
from app.services.ingestion.relevance import assess_relevance
from app.services.ingestion.repository import ClaimedJob, IngestionRepository
from app.services.ingestion.resolver import EntityResolver, ResolutionResult
from app.services.llm.client import (
    LlmClient,
    LlmError,
    LlmUnavailableError,
    build_llm_client,
)
from app.services.orchestrator.config import load_config
from app.utils.logging import log_event

WORKER_ADVISORY_LOCK = 0x4E414349  # "NACI"


@dataclass
class FetchResult:
    http_status: int | None
    not_modified: bool
    content: bytes | None
    etag: str | None
    last_modified: str | None
    error: str | None = None
    outcome: str = "ok"


@dataclass
class WorkerStats:
    sources_checked: int = 0
    fetches_ok: int = 0
    fetches_not_modified: int = 0
    fetches_failed: int = 0
    documents_new: int = 0
    documents_updated: int = 0
    documents_filtered: int = 0
    interpretations_ok: int = 0
    interpretations_irrelevant: int = 0
    interpretations_failed: int = 0
    alerts_written: int = 0
    jobs_processed: int = 0
    expirations: int = 0
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "sources_checked": self.sources_checked,
            "fetches_ok": self.fetches_ok,
            "fetches_not_modified": self.fetches_not_modified,
            "fetches_failed": self.fetches_failed,
            "documents_new": self.documents_new,
            "documents_updated": self.documents_updated,
            "documents_filtered": self.documents_filtered,
            "interpretations_ok": self.interpretations_ok,
            "interpretations_irrelevant": self.interpretations_irrelevant,
            "interpretations_failed": self.interpretations_failed,
            "alerts_written": self.alerts_written,
            "jobs_processed": self.jobs_processed,
            "expirations": self.expirations,
            "errors": self.errors[-50:],
        }


class HttpFeedFetcher:
    """Conditional GET with bounded retries and Retry-After support."""

    def __init__(self, user_agent: str) -> None:
        self.user_agent = user_agent

    def fetch(
        self,
        source: SourceDefinition,
        *,
        etag: str | None,
        last_modified: str | None,
    ) -> FetchResult:
        headers = {
            "User-Agent": self.user_agent,
            "Accept": (
                "application/rss+xml, application/atom+xml, application/xml, text/xml, */*;q=0.5"
            ),
        }
        if etag:
            headers["If-None-Match"] = etag
        if last_modified:
            headers["If-Modified-Since"] = last_modified
        last_error: str | None = None
        for attempt in range(source.max_retries + 1):
            try:
                with httpx.Client(
                    follow_redirects=True,
                    timeout=float(source.timeout_s),
                    headers=headers,
                ) as client:
                    response = client.get(source.url)
            except httpx.TimeoutException as exc:
                last_error = f"timeout: {type(exc).__name__}"
                if attempt < source.max_retries:
                    time.sleep(min(30.0, 2.0 * (2**attempt)))
                    continue
                return FetchResult(None, False, None, None, None, last_error, "error")
            except httpx.RequestError as exc:
                last_error = f"rete: {type(exc).__name__}"
                if attempt < source.max_retries:
                    time.sleep(min(30.0, 2.0 * (2**attempt)))
                    continue
                return FetchResult(None, False, None, None, None, last_error, "error")

            if response.status_code == 304:
                return FetchResult(
                    304,
                    True,
                    None,
                    response.headers.get("ETag") or etag,
                    response.headers.get("Last-Modified") or last_modified,
                    None,
                    "not_modified",
                )
            if response.status_code == 429:
                retry_after = _retry_after(response.headers.get("Retry-After"))
                last_error = "HTTP 429 rate limit"
                if attempt < source.max_retries:
                    time.sleep(min(60.0, retry_after or 5.0 * (2**attempt)))
                    continue
                return FetchResult(429, False, None, etag, last_modified, last_error, "error")
            if response.status_code in {500, 502, 503, 504} and attempt < source.max_retries:
                retry_after = _retry_after(response.headers.get("Retry-After"))
                time.sleep(min(60.0, retry_after or 2.0 * (2**attempt)))
                last_error = f"HTTP {response.status_code}"
                continue
            if response.status_code >= 400:
                snippet = response.text[:200].replace("\n", " ")
                return FetchResult(
                    response.status_code,
                    False,
                    None,
                    response.headers.get("ETag") or etag,
                    response.headers.get("Last-Modified") or last_modified,
                    f"HTTP {response.status_code}: {snippet}",
                    "error",
                )
            content_type = response.headers.get("Content-Type", "")
            if "html" in content_type.lower() and not response.content.lstrip().startswith(
                (b"<?xml", b"<rss", b"<feed")
            ):
                return FetchResult(
                    response.status_code,
                    False,
                    response.content,
                    response.headers.get("ETag") or etag,
                    response.headers.get("Last-Modified") or last_modified,
                    f"Content-Type non feed: {content_type}",
                    "error",
                )
            return FetchResult(
                response.status_code,
                False,
                response.content,
                response.headers.get("ETag") or etag,
                response.headers.get("Last-Modified") or last_modified,
                None,
                "ok",
            )
        return FetchResult(None, False, None, etag, last_modified, last_error, "error")


def _retry_after(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return max(0.0, float(value.strip()))
    except ValueError:
        return None


def _content_hash(entry: ParsedEntry) -> str:
    published = entry.published_at.isoformat() if entry.published_at else ""
    raw = (f"{entry.title}\x00{entry.body}\x00{published}\x00{entry.link or ''}").encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


class IngestionWorker:
    """One worker process; PostgreSQL jobs and advisory lock prevent duplicates."""

    def __init__(
        self,
        config: AppConfig,
        *,
        registry: SourceRegistry | None = None,
        conn: Any | None = None,
        llm_client: LlmClient | None = None,
        worker_id: str | None = None,
    ) -> None:
        if config.app_profile != "postgres" or not config.database_url:
            raise RuntimeError(
                "il worker di ingestion richiede APP_PROFILE=postgres e DATABASE_URL"
            )
        self.config = config
        self.registry = registry or load_source_registry(config.ingestion_registry_path or None)
        self.conn = conn or get_connection(config.app_profile, database_url=config.database_url)
        if conn is None:
            apply_migrations(self.conn)
        self.repo = IngestionRepository(self.conn)
        self.disruption_repo = DisruptionRepository(
            self.conn,
            gtfs_schema=config.gtfs_schema,
            gtfs_dataset_key=config.gtfs_dataset_key,
            osm_dataset_key=config.osm_dataset_key,
        )
        self.resolver = EntityResolver(
            self.conn,
            gtfs_schemas=config.gtfs_datasets,
            osm_schema=config.osm_schema,
        )
        self.llm = llm_client or build_llm_client(config)
        self.extractor = NewsExtractor(self.repo, config, client=self.llm)
        self.cataloguer = DisruptionCataloguer(
            self.disruption_repo,
            config,
            is_simulated=config.llm_mode in {"mock", "replay"},
        )
        self.fetcher = HttpFeedFetcher(config.ingestion_user_agent)
        self.worker_id = worker_id or f"{socket.gethostname()}:{os.getpid()}"
        self._stop = False

    def close(self) -> None:
        try:
            self.conn.close()
        except Exception:
            pass

    def stop(self, *_args: Any) -> None:
        self._stop = True

    def sync_registry(self) -> int:
        return self.repo.sync_sources(self.registry)

    def enqueue_due_fetches(self, source_id: str | None = None) -> int:
        rows = self.repo._fetchall(
            """
            SELECT source_id FROM ingestion_sources
            WHERE enabled AND next_run_at <= NOW()
              AND (%s::text IS NULL OR source_id = %s)
            ORDER BY next_run_at, source_id
            """,
            (source_id, source_id),
        )
        queued = 0
        for row in rows:
            if self.repo.enqueue_fetch(str(row["source_id"])):
                queued += 1
        return queued

    def run_once(self, *, force: bool = False, source_id: str | None = None) -> dict[str, Any]:
        self.sync_registry()
        if force:
            self.repo.set_source_due(source_id)
        self.repo.recover_expired_leases()
        self.enqueue_due_fetches(source_id)
        self.repo.enqueue_maintenance()
        stats = WorkerStats()
        while not self._stop:
            job = self.repo.claim_job(
                self.worker_id,
                lease_s=self.config.ingestion_lease_s,
                source_id=source_id,
            )
            if job is None:
                break
            self._process_job(job, stats)
            stats.jobs_processed += 1
        return stats.as_dict()

    def run_forever(self, *, interval_s: float | None = None) -> dict[str, Any]:
        if not self._acquire_lock():
            raise RuntimeError(
                "un altro worker di ingestion possiede il lock advisory; "
                "avvio annullato per evitare polling duplicato"
            )
        signal.signal(signal.SIGTERM, self.stop)
        signal.signal(signal.SIGINT, self.stop)
        total = WorkerStats()
        try:
            while not self._stop:
                result = self.run_once()
                for key in (
                    "sources_checked",
                    "fetches_ok",
                    "fetches_not_modified",
                    "fetches_failed",
                    "documents_new",
                    "documents_updated",
                    "documents_filtered",
                    "interpretations_ok",
                    "interpretations_irrelevant",
                    "interpretations_failed",
                    "alerts_written",
                    "jobs_processed",
                    "expirations",
                ):
                    setattr(total, key, getattr(total, key) + int(result.get(key, 0)))
                total.errors.extend(result.get("errors", []))
                if self._stop:
                    break
                time.sleep(interval_s or self.config.ingestion_poll_interval_s)
        finally:
            self._release_lock()
        return total.as_dict()

    def _acquire_lock(self) -> bool:
        row = self.repo._fetchone(
            "SELECT pg_try_advisory_lock(%s) AS locked", (WORKER_ADVISORY_LOCK,)
        )
        self.conn.commit()
        return bool(row and row.get("locked"))

    def _release_lock(self) -> None:
        try:
            self.repo._execute("SELECT pg_advisory_unlock(%s)", (WORKER_ADVISORY_LOCK,))
            self.conn.commit()
        except Exception:
            pass

    def _process_job(self, job: ClaimedJob, stats: WorkerStats) -> None:
        try:
            if job.job_type == "fetch_source":
                self._process_fetch(job, stats)
            elif job.job_type == "interpret_document":
                self._process_interpret(job, stats)
            elif job.job_type == "maintenance":
                self._process_maintenance(job, stats)
            else:
                self.repo.fail_job(job.job_id, f"tipo job sconosciuto: {job.job_type}")
        except Exception as exc:  # noqa: BLE001 - the worker must survive one source
            message = f"{type(exc).__name__}: {exc}"
            log_event("ingestion.worker", "job_failed", level="error", detail=message)
            stats.errors.append(message)
            self.repo.fail_job(job.job_id, message, retry_after_s=60)

    def _source(self, source_id: str) -> SourceDefinition | None:
        return self.registry.by_id().get(source_id)

    def _process_fetch(self, job: ClaimedJob, stats: WorkerStats) -> None:
        if not job.source_id:
            self.repo.complete_job(job.job_id)
            return
        source = self._source(job.source_id)
        source_row = self.repo.source(job.source_id)
        if source is None or source_row is None:
            self.repo.fail_job(job.job_id, f"fonte non censita: {job.source_id}")
            return
        if source.kind == "non_rss":
            self.repo.record_fetch(
                {
                    "source_id": source.source_id,
                    "started_at": datetime.now(timezone.utc),
                    "finished_at": datetime.now(timezone.utc),
                    "http_status": None,
                    "entries_seen": 0,
                    "outcome": "skipped_non_rss",
                    "error": "fonte dichiarata non RSS; nessuna acquisizione tentata",
                }
            )
            self.repo.update_source_after_fetch(
                source.source_id,
                checked_at=datetime.now(timezone.utc),
                http_status=None,
                success=True,
                error=None,
                etag=None,
                last_modified=None,
                next_run_at=datetime.now(timezone.utc)
                + timedelta(seconds=source.polling_interval_s),
            )
            stats.sources_checked += 1
            self.repo.complete_job(job.job_id)
            return

        started = datetime.now(timezone.utc)
        stats.sources_checked += 1
        if source.kind == "anm_scraper":
            result = self._fetch_anm(source, source_row)
        else:
            result = self.fetcher.fetch(
                source,
                etag=source_row.get("etag"),
                last_modified=source_row.get("last_modified"),
            )
            if result.error:
                result.outcome = "error"

        finished = datetime.now(timezone.utc)
        duration_ms = int((finished - started).total_seconds() * 1000)
        if result.error or result.content is None:
            outcome = "not_modified" if result.not_modified else "error"
            if outcome == "not_modified":
                stats.fetches_not_modified += 1
            else:
                stats.fetches_failed += 1
            error = result.error or "nessun contenuto"
            self.repo.record_fetch(
                {
                    "source_id": source.source_id,
                    "started_at": started,
                    "finished_at": finished,
                    "http_status": result.http_status,
                    "not_modified": result.not_modified,
                    "bytes_received": len(result.content) if result.content else 0,
                    "outcome": outcome,
                    "error": error,
                    "etag": result.etag,
                    "last_modified": result.last_modified,
                    "duration_ms": duration_ms,
                }
            )
            backoff = min(
                86400,
                max(
                    source.polling_interval_s,
                    int(self.config.ingestion_backoff_s * (2 ** min(6, int(job.attempts)))),
                ),
            )
            self.repo.update_source_after_fetch(
                source.source_id,
                checked_at=finished,
                http_status=result.http_status,
                success=outcome == "not_modified",
                error=None if outcome == "not_modified" else error,
                etag=result.etag,
                last_modified=result.last_modified,
                next_run_at=finished + timedelta(seconds=backoff),
            )
            if outcome == "not_modified":
                self.repo.complete_job(job.job_id)
            else:
                self.repo.fail_job(job.job_id, error, retry_after_s=backoff)
            return

        try:
            if source.kind == "anm_scraper":
                entries = parse_anm_document(json.loads(result.content.decode("utf-8")), source)
            else:
                entries = parse_feed_bytes(result.content, source)
        except (FeedParseError, ValueError, UnicodeDecodeError) as exc:
            stats.fetches_failed += 1
            error = f"parsing: {exc}"
            self.repo.record_fetch(
                {
                    "source_id": source.source_id,
                    "started_at": started,
                    "finished_at": finished,
                    "http_status": result.http_status,
                    "bytes_received": len(result.content),
                    "entries_seen": 0,
                    "outcome": "parse_error",
                    "error": error,
                    "etag": result.etag,
                    "last_modified": result.last_modified,
                    "duration_ms": duration_ms,
                }
            )
            self.repo.update_source_after_fetch(
                source.source_id,
                checked_at=finished,
                http_status=result.http_status,
                success=False,
                error=error,
                etag=result.etag,
                last_modified=result.last_modified,
                next_run_at=finished + timedelta(seconds=max(300, source.polling_interval_s)),
            )
            self.repo.fail_job(job.job_id, error, retry_after_s=300)
            return

        counts = self._store_entries(source, entries, stats)
        self.repo.record_fetch(
            {
                "source_id": source.source_id,
                "started_at": started,
                "finished_at": finished,
                "http_status": result.http_status,
                "bytes_received": len(result.content),
                "entries_seen": len(entries),
                **counts,
                "outcome": "ok",
                "etag": result.etag,
                "last_modified": result.last_modified,
                "duration_ms": duration_ms,
            }
        )
        cursor = max(
            (entry.published_at for entry in entries if entry.published_at is not None),
            default=None,
        )
        self.repo.update_source_after_fetch(
            source.source_id,
            checked_at=finished,
            http_status=result.http_status,
            success=True,
            error=None,
            etag=result.etag,
            last_modified=result.last_modified,
            next_run_at=finished + timedelta(seconds=source.polling_interval_s),
        )
        if cursor is not None:
            self.repo._execute(
                "UPDATE ingestion_sources SET cursor_ts = %s WHERE source_id = %s",
                (cursor, source.source_id),
            )
            self.conn.commit()
        stats.fetches_ok += 1
        self.repo.complete_job(job.job_id)

    def _fetch_anm(self, source: SourceDefinition, source_row: dict[str, Any]) -> FetchResult:
        try:
            from app.services.ingestion.vendor import anm_scraper
        except ImportError as exc:  # pragma: no cover - dependency guard
            return FetchResult(
                None, False, None, None, None, f"scraper non importabile: {exc}", "error"
            )
        cursor = source_row.get("cursor_ts")
        since: int | None = None
        if isinstance(cursor, datetime):
            since = int((cursor - timedelta(days=1)).timestamp())
        try:
            document = anm_scraper.scrape(
                details=True,
                since_timestamp=since,
                workers=3,
                delay=0.2,
                timeout=float(source.timeout_s),
                retries=source.max_retries,
            )
        except Exception as exc:  # noqa: BLE001 - scraper errors are explicit
            return FetchResult(None, False, None, None, None, f"scraper ANM: {exc}", "error")
        payload = json.dumps(document, ensure_ascii=False).encode("utf-8")
        return FetchResult(200, False, payload, None, None, None, "ok")

    def _store_entries(
        self,
        source: SourceDefinition,
        entries: list[ParsedEntry],
        stats: WorkerStats,
    ) -> dict[str, int]:
        new = updated = filtered = jobs = 0
        for entry in entries:
            content_hash = _content_hash(entry)
            result = self.repo.upsert_document(
                source_id=source.source_id,
                external_id=entry.external_id,
                canonical_url=entry.link,
                title=entry.title,
                body_text=entry.body,
                raw_document=raw_document_json(entry),
                content_hash=content_hash,
                language=entry.language,
                published_at=entry.published_at,
                published_precision=entry.published_precision,
            )
            if result.is_new:
                new += 1
            elif result.changed:
                updated += 1
            if not (result.is_new or result.changed):
                continue
            decision = assess_relevance(
                entry,
                source,
                filter_version=self.config.ingestion_relevance_version,
            )
            if not decision.candidate:
                filtered += 1
                stats.documents_filtered += 1
                self.repo.mark_document(
                    result.document_id,
                    status="filtered",
                    is_relevant=False,
                    relevance_reason=decision.reason,
                )
                self.repo.save_interpretation(
                    result.document_id,
                    content_hash=content_hash,
                    prompt_version="prefilter",
                    schema_version=self.config.ingestion_relevance_version,
                    model=f"prefilter:{self.config.ingestion_relevance_version}",
                    language=entry.language,
                    status="irrelevant",
                    output=decision.to_output(),
                    error=None,
                    latency_ms=0,
                )
            else:
                self.repo.mark_document(
                    result.document_id,
                    status="pending",
                    is_relevant=True,
                    relevance_reason=decision.reason,
                )
                self.repo.enqueue_interpret(result.document_id)
                jobs += 1
        stats.documents_new += new
        stats.documents_updated += updated
        return {
            "documents_new": new,
            "documents_updated": updated,
            "documents_filtered": filtered,
            "interpretation_jobs": jobs,
        }

    def _process_interpret(self, job: ClaimedJob, stats: WorkerStats) -> None:
        if job.document_id is None:
            self.repo.complete_job(job.job_id)
            return
        document = self.repo.document(job.document_id)
        if document is None:
            self.repo.complete_job(job.job_id)
            return
        if document["status"] in {"interpreted", "irrelevant", "filtered"}:
            self.repo.complete_job(job.job_id)
            return
        if not self.repo.lease_document(
            job.document_id, self.worker_id, self.config.ingestion_lease_s
        ):
            self.repo.complete_job(job.job_id)
            return
        attempts = self.repo.increment_attempt(job.document_id)
        source = self._source(str(document["source_id"]))
        if source is None:
            self.repo.mark_document(
                job.document_id,
                status="needs_review",
                error=f"fonte non censita: {document['source_id']}",
            )
            self.repo.fail_job(job.job_id, "fonte non censita", retry_after_s=3600)
            return

        try:
            outcome: ExtractionOutcome = self.extractor.interpret(document, source)
        except LlmUnavailableError as exc:
            stats.interpretations_failed += 1
            status = "needs_review" if attempts >= job.max_attempts else "pending"
            self.repo.mark_document(
                job.document_id, status=status, error=f"provider_unavailable: {exc}"
            )
            self.repo.fail_job(
                job.job_id,
                f"provider_unavailable: {exc}",
                retry_after_s=min(3600, 300 * attempts),
            )
            return
        except (ExtractionError, LlmError, ValueError) as exc:
            stats.interpretations_failed += 1
            status = "needs_review" if attempts >= job.max_attempts else "pending"
            self.repo.mark_document(
                job.document_id, status=status, error=f"estrazione_non_valida: {exc}"
            )
            self.repo.fail_job(
                job.job_id,
                f"estrazione_non_valida: {exc}",
                retry_after_s=min(3600, 300 * attempts),
            )
            return

        extraction = outcome.extraction
        if not extraction.relevant:
            stats.interpretations_irrelevant += 1
            self.repo.mark_document(
                job.document_id,
                status="irrelevant",
                is_relevant=False,
                relevance_reason=extraction.relevance_reason or "irrilevante",
            )
            self.repo.complete_job(job.job_id)
            return

        try:
            resolution: ResolutionResult = self.resolver.resolve_extraction(extraction, source)
            alert: DisruptionRecord | None = self.cataloguer.catalogue(
                document=document,
                source=source,
                extraction=extraction,
                resolution=resolution,
            )
        except Exception as exc:  # noqa: BLE001 - never lose the document
            stats.interpretations_failed += 1
            status = "failed" if attempts >= job.max_attempts else "pending"
            self.repo.mark_document(
                job.document_id, status=status, error=f"catalogazione_fallita: {exc}"
            )
            self.repo.fail_job(
                job.job_id,
                f"catalogazione_fallita: {exc}",
                retry_after_s=min(3600, 120 * attempts),
            )
            return
        stats.interpretations_ok += 1
        if alert is not None:
            stats.alerts_written += 1
        self.repo.mark_document(
            job.document_id,
            status="interpreted",
            is_relevant=True,
            relevance_reason=extraction.relevance_reason,
            catalogued=alert is not None,
        )
        self.repo.complete_job(job.job_id)

    def _process_maintenance(self, job: ClaimedJob, stats: WorkerStats) -> None:
        now = datetime.now(timezone.utc)
        expired = self.disruption_repo.expire_due(now)
        stale = self.disruption_repo.expire_stale_unknown(now)
        stats.expirations += len(expired) + len(stale)
        self.repo.complete_job(job.job_id)

    def verify_sources(self, *, include_disabled: bool = True) -> dict[str, Any]:
        """Attempt every RSS/Atom/ANM source once and return a per-source audit."""
        self.sync_registry()
        report: list[dict[str, Any]] = []
        sources = self.registry.sources if include_disabled else self.registry.enabled()
        for source in sources:
            row = self.repo.source(source.source_id)
            started = datetime.now(timezone.utc)
            if source.kind == "non_rss":
                report.append(
                    {
                        "source_id": source.source_id,
                        "name": source.name,
                        "url": source.url,
                        "kind": source.kind,
                        "class": source.source_class,
                        "status": "skipped_non_rss",
                        "http_status": None,
                        "entries": 0,
                        "error": "fonte censita ma non RSS",
                        "duration_ms": 0,
                    }
                )
                continue
            if not source.enabled:
                report.append(
                    {
                        "source_id": source.source_id,
                        "name": source.name,
                        "url": source.url,
                        "kind": source.kind,
                        "class": source.source_class,
                        "status": "disabled",
                        "http_status": None,
                        "entries": 0,
                        "error": None,
                        "duration_ms": 0,
                    }
                )
                continue
            if source.kind == "anm_scraper":
                result = self._fetch_anm(source, row or {})
            else:
                result = self.fetcher.fetch(
                    source,
                    etag=(row or {}).get("etag"),
                    last_modified=(row or {}).get("last_modified"),
                )
            elapsed = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
            entries = 0
            error = result.error
            if result.content and not error:
                try:
                    if source.kind == "anm_scraper":
                        entries = len(
                            parse_anm_document(json.loads(result.content.decode("utf-8")), source)
                        )
                    else:
                        entries = len(parse_feed_bytes(result.content, source))
                except Exception as exc:  # noqa: BLE001
                    error = f"parsing: {exc}"
            report.append(
                {
                    "source_id": source.source_id,
                    "name": source.name,
                    "url": source.url,
                    "kind": source.kind,
                    "class": source.source_class,
                    "status": "ok"
                    if entries
                    else ("not_modified" if result.not_modified else "error"),
                    "http_status": result.http_status,
                    "entries": entries,
                    "error": error,
                    "duration_ms": elapsed,
                }
            )
        reachable = sum(1 for item in report if item["status"] in {"ok", "not_modified"})
        parsed = sum(1 for item in report if item["entries"] > 0)
        return {
            "sources_total": len(sources),
            "unique_urls": len({source.url for source in sources}),
            "reachable": reachable,
            "parsed_with_entries": parsed,
            "failed": sum(1 for item in report if item["status"] == "error"),
            "skipped_non_rss": sum(1 for item in report if item["status"] == "skipped_non_rss"),
            "disabled": sum(1 for item in report if item["status"] == "disabled"),
            "items": report,
        }


def run_worker(
    *,
    once: bool = False,
    force: bool = False,
    source_id: str | None = None,
    interval_s: float | None = None,
    verify: bool = False,
    config: AppConfig | None = None,
) -> dict[str, Any]:
    cfg = config or load_config()
    worker = IngestionWorker(cfg)
    try:
        if verify:
            return worker.verify_sources()
        if once:
            return worker.run_once(force=force, source_id=source_id)
        return worker.run_forever(interval_s=interval_s)
    finally:
        worker.close()


__all__ = ["IngestionWorker", "WorkerStats", "run_worker"]
