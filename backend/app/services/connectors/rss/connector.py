"""RSS / Disruption connector normalizing official alerts into service_alerts."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

from app.repositories.base import SourceRepository
from app.services.connectors.base import ConnectorOutcome
from app.services.connectors.rss.derivation import (
    derive_severity_and_confidence,
    load_derivation_rules,
)
from app.services.connectors.rss.parser import parse_rss_feed


class RssConnector:
    """Ingests RSS / news feeds into service_alerts with deterministic derivation."""

    source_id: str = "anm"
    frequency: str = "oraria"

    def __init__(
        self,
        repository: SourceRepository,
        *,
        feed_url: str = "",
        source_id: str = "anm",
        timeout_s: float = 10.0,
        declared_encoding: str | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        self._repo = repository
        self._feed_url = feed_url
        self.source_id = source_id
        self._timeout_s = timeout_s
        self._declared_encoding = declared_encoding
        self._client = client
        self._rules = load_derivation_rules()

    def ingest_bytes(
        self,
        raw_bytes: bytes,
        *,
        is_simulated: bool = False,
        declared_encoding: str | None = None,
    ) -> ConnectorOutcome:
        started_at = datetime.now(timezone.utc)
        items = parse_rss_feed(
            raw_bytes,
            self.source_id,
            declared_encoding=declared_encoding or self._declared_encoding,
        )
        rows: list[dict[str, Any]] = []
        notes: list[str] = []
        for item in items:
            derived = derive_severity_and_confidence(
                self.source_id,
                item.title,
                item.body,
                rules=self._rules,
            )
            if derived.matched_keyword is None:
                notes.append(f"{item.alert_id}:keyword_default")
            rows.append(
                {
                    "alert_id": item.alert_id,
                    "route_id": item.route_id,
                    "stop_id": None,
                    "severity": derived.severity,
                    "valid_from": item.pub_date.isoformat(),
                    "valid_to": None,
                    "source_id": self.source_id,
                    "confidence": derived.confidence,
                    "title": item.title,
                    "body": item.body,
                    "zone_id": item.zone_id,
                    "is_simulated": is_simulated,
                    "data_reference": item.data_reference,
                    "ingested_at": started_at.isoformat(),
                }
            )
        written = self._repo.upsert_service_alerts(rows)
        finished_at = datetime.now(timezone.utc)
        detail = ";".join(notes) if notes else "rss_ok"
        self._repo.record_ingestion_run(
            {
                "connector": "rss",
                "started_at": started_at.isoformat(),
                "finished_at": finished_at.isoformat(),
                "rows_written": written,
                "is_simulated": is_simulated,
                "outcome": "fallback" if is_simulated else "ok",
                "detail": detail,
            }
        )
        return ConnectorOutcome(
            connector="rss",
            source_id=self.source_id,
            rows_written=written,
            is_simulated=is_simulated,
            outcome="fallback" if is_simulated else "ok",
            detail=detail,
        )

    def run(self) -> ConnectorOutcome:
        if not self._feed_url:
            return self.fallback(reason="feed_url_non_configurato")
        try:
            if self._client is not None:
                resp = self._client.get(self._feed_url, timeout=self._timeout_s)
            else:
                with httpx.Client(timeout=self._timeout_s) as client:
                    resp = client.get(self._feed_url)
            resp.raise_for_status()
            return self.ingest_bytes(resp.content, is_simulated=False)
        except Exception as exc:
            return self.fallback(reason=f"feed_non_raggiungibile:{type(exc).__name__}")

    def fallback(self, reason: str = "manual_fallback") -> ConnectorOutcome:
        started_at = datetime.now(timezone.utc)
        repo_root = Path(__file__).resolve().parents[5]
        sample_xml = repo_root / "shared" / "mocks" / "rss_ilmattino_sample.xml"
        if sample_xml.exists():
            raw = sample_xml.read_bytes()
            items = parse_rss_feed(raw, self.source_id, declared_encoding="iso-8859-1")
        else:
            items = []

        rows: list[dict[str, Any]] = []
        if items:
            for item in items:
                derived = derive_severity_and_confidence(
                    self.source_id,
                    item.title,
                    item.body,
                    rules=self._rules,
                )
                rows.append(
                    {
                        "alert_id": item.alert_id,
                        "route_id": item.route_id or "L2",
                        "stop_id": None,
                        "severity": derived.severity,
                        "valid_from": item.pub_date.isoformat(),
                        "valid_to": None,
                        "source_id": self.source_id,
                        "confidence": derived.confidence,
                        "title": item.title,
                        "body": item.body,
                        "zone_id": item.zone_id or "Z_BAGNOLI",
                        "is_simulated": True,
                        "data_reference": f"fallback:{item.data_reference}",
                        "ingested_at": started_at.isoformat(),
                    }
                )
        else:
            rows.append(
                {
                    "alert_id": f"{self.source_id}:fallback-l2",
                    "route_id": "L2",
                    "stop_id": None,
                    "severity": "high",
                    "valid_from": started_at.isoformat(),
                    "valid_to": None,
                    "source_id": self.source_id,
                    "confidence": 0.85,
                    "title": "Guasto Linea 2 tra Cavour e Mergellina",
                    "body": "Sospensione parziale Linea 2 per guasto al segnalamento",
                    "zone_id": "Z_BAGNOLI",
                    "is_simulated": True,
                    "data_reference": "fallback:rss_simulated",
                    "ingested_at": started_at.isoformat(),
                }
            )

        written = self._repo.upsert_service_alerts(rows)
        finished_at = datetime.now(timezone.utc)
        self._repo.record_ingestion_run(
            {
                "connector": "rss",
                "started_at": started_at.isoformat(),
                "finished_at": finished_at.isoformat(),
                "rows_written": written,
                "is_simulated": True,
                "outcome": "fallback",
                "detail": reason,
            }
        )
        return ConnectorOutcome(
            connector="rss",
            source_id=self.source_id,
            rows_written=written,
            is_simulated=True,
            outcome="fallback",
            detail=reason,
        )
