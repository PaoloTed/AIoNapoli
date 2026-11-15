"""RSS/Atom and ANM scraper normalization without any LLM call."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from html import unescape
from typing import Any
from zoneinfo import ZoneInfo

import feedparser
from bs4 import BeautifulSoup

from app.config.sources import SourceDefinition
from app.services.connectors.rss.parser import parse_rss_date


class FeedParseError(ValueError):
    """The endpoint answered but did not contain a usable feed."""


@dataclass(frozen=True)
class ParsedEntry:
    external_id: str
    title: str
    body: str
    link: str | None
    published_at: datetime | None
    published_precision: str
    language: str
    raw: dict[str, Any]


def _json_safe(value: Any, depth: int = 0) -> Any:
    if depth > 6:
        return str(value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _json_safe(item, depth + 1) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item, depth + 1) for item in value]
    if hasattr(value, "tm_year"):
        try:
            return datetime(*value[:6], tzinfo=timezone.utc).isoformat()
        except (TypeError, ValueError):
            return str(value)
    return str(value)


def html_to_text(value: str | None) -> str:
    if not value:
        return ""
    soup = BeautifulSoup(value, "html.parser")
    for tag in soup(["script", "style", "noscript", "template", "iframe"]):
        tag.decompose()
    text = soup.get_text(" ", strip=True)
    return re.sub(r"\s+", " ", unescape(text)).strip()


def _entry_date(entry: Any, source: SourceDefinition) -> tuple[datetime | None, str]:
    for key in ("published_parsed", "updated_parsed", "created_parsed"):
        parsed = entry.get(key)
        if parsed:
            try:
                value = datetime(*parsed[:6], tzinfo=timezone.utc)
                return value, "second"
            except (TypeError, ValueError):
                continue
    for key in ("published", "updated", "created", "pubDate"):
        raw = entry.get(key)
        if not isinstance(raw, str) or not raw.strip():
            continue
        try:
            value = parse_rss_date(raw)
        except ValueError:
            continue
        precision = "day" if not re.search(r"\d{1,2}:\d{2}", raw) else "second"
        return value, precision
    return None, "unknown"


def parse_feed_bytes(raw_bytes: bytes, source: SourceDefinition) -> list[ParsedEntry]:
    """Parse RSS or Atom bytes defensively, preserving a raw JSON snapshot."""
    if not raw_bytes or not raw_bytes.strip():
        raise FeedParseError("risposta vuota")
    head = raw_bytes[:512].lstrip().lower()
    if head.startswith(b"<!doctype html") or head.startswith(b"<html"):
        raise FeedParseError("la risposta e' HTML, non un feed RSS/Atom")

    parsed = feedparser.parse(raw_bytes)
    entries = parsed.get("entries")
    if not entries:
        if parsed.get("bozo"):
            reason = parsed.get("bozo_exception")
            raise FeedParseError(f"feed non interpretabile: {reason}")
        raise FeedParseError("feed senza entry (possibile endpoint vuoto o cambiato)")

    result: list[ParsedEntry] = []
    seen: set[str] = set()
    for entry in entries:
        title = html_to_text(entry.get("title"))
        if not title:
            title = "(senza titolo)"
        body_parts: list[str] = []
        contents = entry.get("content")
        if isinstance(contents, list):
            for item in contents:
                if isinstance(item, dict):
                    body_parts.append(html_to_text(item.get("value")))
        if not any(body_parts):
            body_parts.append(html_to_text(entry.get("summary")))
        if not any(body_parts):
            body_parts.append(html_to_text(entry.get("description")))
        body = "\n".join(part for part in body_parts if part)
        link = entry.get("link") if isinstance(entry.get("link"), str) else None
        fallback_digest = hashlib.sha256(
            f"{source.source_id}\x00{title}\x00{body}".encode("utf-8")
        ).hexdigest()[:20]
        external_id = (
            entry.get("id") or entry.get("guid") or link or f"{source.source_id}:{fallback_digest}"
        )
        external_id = str(external_id).strip()
        if not external_id or external_id in seen:
            continue
        seen.add(external_id)
        published_at, precision = _entry_date(entry, source)
        result.append(
            ParsedEntry(
                external_id=external_id,
                title=title,
                body=body or title,
                link=link,
                published_at=published_at,
                published_precision=precision,
                language=source.language,
                raw={
                    "feed_title": parsed.get("feed", {}).get("title"),
                    "entry": _json_safe(dict(entry)),
                },
            )
        )
    if not result:
        raise FeedParseError("feed con entry prive di identificativo")
    return result


def parse_anm_document(document: dict[str, Any], source: SourceDefinition) -> list[ParsedEntry]:
    """Convert the team scraper's article JSON into the common document shape."""
    articles = document.get("articles")
    if not isinstance(articles, list):
        raise FeedParseError("scraper ANM senza lista articles")
    meta = document.get("meta") if isinstance(document.get("meta"), dict) else {}
    timezone_name = str(meta.get("timezone") or source.timezone)
    try:
        tz = ZoneInfo(timezone_name)
    except Exception:
        tz = ZoneInfo("Europe/Rome")
    result: list[ParsedEntry] = []
    for article in articles:
        if not isinstance(article, dict):
            continue
        external_id = str(article.get("id") or "").strip()
        if not external_id:
            continue
        title = str(article.get("title") or "").strip() or "(senza titolo)"
        body = str(article.get("body_text") or "").strip()
        if not body:
            body = str(article.get("summary") or "").strip()
        published_at: datetime | None = None
        raw_date = article.get("date")
        if isinstance(raw_date, str) and raw_date.strip():
            try:
                day = datetime.fromisoformat(raw_date[:10])
                published_at = day.replace(tzinfo=tz).astimezone(timezone.utc)
            except ValueError:
                published_at = None
        result.append(
            ParsedEntry(
                external_id=external_id,
                title=title,
                body=body or title,
                link=article.get("url") if isinstance(article.get("url"), str) else None,
                published_at=published_at,
                published_precision="day" if published_at else "unknown",
                language=source.language,
                raw={"scraper_meta": _json_safe(meta), "article": _json_safe(article)},
            )
        )
    if not result:
        raise FeedParseError("scraper ANM senza articoli validi")
    return result


def raw_document_json(entry: ParsedEntry) -> str:
    return json.dumps(entry.raw, ensure_ascii=False, sort_keys=True)


__all__ = [
    "FeedParseError",
    "ParsedEntry",
    "html_to_text",
    "parse_anm_document",
    "parse_feed_bytes",
    "raw_document_json",
]
