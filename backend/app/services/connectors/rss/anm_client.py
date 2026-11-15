"""ANM news scraper adapter for RSS disruption connector (06_agente_scraping.md)."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.connectors.rss.cache import DocumentCache
from app.services.connectors.rss.derivation import (
    derive_severity_and_confidence,
    load_derivation_rules,
)
from app.services.connectors.rss.normalize import compute_document_hash, normalize_text

_ROUTE_RE = re.compile(
    r"\b(linea\s+[12]|r\d+|c\d+|\d{3}|cumana|circumvesuviana|metro\s+linea\s+\d)\b",
    re.IGNORECASE,
)


class AnmClient:
    """Acquires and maps ANM news into normalized service_alerts rows."""

    def __init__(
        self,
        news_file: Path | None = None,
        cache: DocumentCache | None = None,
    ) -> None:
        self._news_file = news_file or Path("anm_info/anm_news.json")
        self._cache = cache or DocumentCache()
        self._rules = load_derivation_rules()

    def load_articles(self, limit: int = 30) -> list[dict[str, Any]]:
        """Load articles from scraped JSON file or fallback."""
        if self._news_file.exists():
            try:
                data = json.loads(self._news_file.read_text(encoding="utf-8"))
                items = data.get("news") or data.get("articles") or []
                return items[:limit]
            except Exception:
                pass
        return []

    def map_article(
        self,
        article: dict[str, Any],
        *,
        is_simulated: bool = False,
    ) -> tuple[dict[str, Any], str, bool]:
        """Map an ANM article to service_alerts row.

        Returns (row_dict, document_hash, was_cached).
        """
        art_id = str(article.get("id") or article.get("Id") or article.get("title", "unknown")[:20])
        alert_id = f"anm:{art_id}"
        title = str(article.get("title") or article.get("Title") or "").strip()[:300]
        raw_body = str(article.get("body") or article.get("Body") or article.get("summary") or "")
        body = normalize_text(raw_body)
        doc_hash = compute_document_hash(body)
        was_cached = self._cache.has(doc_hash)

        if not was_cached:
            self._cache.put(doc_hash)

        # Route extraction from title/body keywords
        route_id = None
        m_route = _ROUTE_RE.search(title) or _ROUTE_RE.search(body)
        if m_route:
            route_id = m_route.group(1).upper().replace("LINEA ", "L")

        derived = derive_severity_and_confidence("anm", title, body, rules=self._rules)

        pub_date_raw = (
            article.get("date") or article.get("PublishedDate") or article.get("scraped_at")
        )
        valid_from = datetime.now(timezone.utc).isoformat()
        if isinstance(pub_date_raw, str) and pub_date_raw:
            try:
                valid_from = datetime.fromisoformat(pub_date_raw.replace("Z", "+00:00")).isoformat()
            except ValueError:
                pass

        url = str(article.get("url") or article.get("Link") or "https://www.anm.it/notizie")

        row = {
            "alert_id": alert_id,
            "route_id": route_id,
            "stop_id": None,
            "severity": derived.severity,
            "valid_from": valid_from,
            "valid_to": None,
            "source_id": "anm",
            "confidence": 0.85,
            "title": title,
            "body": body,
            "zone_id": None,
            "is_simulated": is_simulated,
            "data_reference": url,
            "ingested_at": datetime.now(timezone.utc).isoformat(),
        }

        return row, doc_hash, was_cached
