"""RSS/Atom and ANM normalization without network access."""

from __future__ import annotations

from datetime import timezone

import pytest

from app.config.sources import SourceDefinition
from app.services.ingestion.parsing import (
    FeedParseError,
    parse_anm_document,
    parse_feed_bytes,
)


def _source(**overrides: object) -> SourceDefinition:
    values = {
        "source_id": "test_feed",
        "name": "Test feed",
        "url": "https://example.test/feed",
        "kind": "rss",
        "source_class": "official_transport",
        "operator": "eav",
        "local_relevance": "not_required",
        "provenance": ["test_feed"],
    }
    values.update(overrides)
    return SourceDefinition.model_validate(values)


def test_rss_parsing_keeps_guid_text_and_date() -> None:
    raw = b"""<?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0"><channel><title>Test</title>
      <item>
        <title>Linea 9 sospesa</title>
        <guid isPermaLink="false">https://example.test/?p=123</guid>
        <link>https://example.test/linea-9</link>
        <description>&lt;p&gt;Sospensione &lt;b&gt;temporanea&lt;/b&gt;
        dalle 08:00.&lt;/p&gt;</description>
        <pubDate>Fri, 14 Nov 2026 10:30:00 +0100</pubDate>
      </item>
    </channel></rss>"""
    entries = parse_feed_bytes(raw, _source())
    assert len(entries) == 1
    entry = entries[0]
    assert entry.external_id == "https://example.test/?p=123"
    assert entry.title == "Linea 9 sospesa"
    assert "Sospensione temporanea" in entry.body
    assert entry.published_at is not None
    assert entry.published_at.tzinfo is not None
    assert entry.published_at.astimezone(timezone.utc).hour == 9


def test_atom_parsing_uses_updated_date() -> None:
    raw = b"""<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <title>INGV</title>
      <entry>
        <id>urn:test:1</id>
        <title>Terremoto Campi Flegrei</title>
        <updated>2026-11-14T16:30:00Z</updated>
        <summary>Magnitudo 2.1</summary>
      </entry>
    </feed>"""
    entries = parse_feed_bytes(raw, _source(kind="atom", source_class="national_context"))
    assert len(entries) == 1
    assert entries[0].external_id == "urn:test:1"
    assert entries[0].published_at is not None
    assert entries[0].published_precision == "second"


def test_italian_date_is_supported_when_feedparser_does_not_parse_it() -> None:
    raw = b"""<?xml version="1.0" encoding="ISO-8859-1"?>
    <rss version="2.0"><channel><title>Mattino</title>
      <item>
        <title>Traffico a Napoli</title>
        <guid>https://example.test/mattino-1</guid>
        <description>Code in tangenziale</description>
        <pubDate>sab, 14 nov 2026 16:51:00</pubDate>
      </item>
    </channel></rss>"""
    entries = parse_feed_bytes(raw, _source(source_id="ilmattino_napoli"))
    assert entries[0].published_at is not None
    assert entries[0].published_at.astimezone(timezone.utc).month == 11


def test_html_response_is_not_a_feed() -> None:
    with pytest.raises(FeedParseError):
        parse_feed_bytes(b"<!doctype html><html><body>login</body></html>", _source())


def test_anm_document_keeps_italian_body_and_date() -> None:
    document = {
        "meta": {"timezone": "Europe/Rome", "scraper_version": "1.1.0"},
        "articles": [
            {
                "id": "a0gTEST",
                "title": "VARIAZIONI AL SERVIZIO",
                "date": "2026-11-12",
                "summary": "Sintesi",
                "body_text": "ANM informa che la linea 1 e' sospesa.",
                "url": "https://www.anm.it/notizia/a0gTEST",
                "categories": ["metro", "servizio"],
            }
        ],
    }
    entries = parse_anm_document(document, _source(source_id="anm_news", kind="anm_scraper"))
    assert len(entries) == 1
    assert entries[0].external_id == "a0gTEST"
    assert "linea 1" in entries[0].body
    assert entries[0].published_at is not None
    assert entries[0].published_precision == "day"
