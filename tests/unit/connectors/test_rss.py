"""Unit tests for RSS severity/confidence derivation, pubDate handling, and Il Mattino encoding."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from app.services.connectors.rss.derivation import derive_severity_and_confidence
from app.services.connectors.rss.parser import parse_rss_feed


def test_severity_confidence() -> None:
    """REQ-CONN-05: deterministic severity and confidence derivation from derivation.yaml."""
    anm = derive_severity_and_confidence("anm", "Guasto e chiusura Linea 2")
    assert anm.severity == "high"
    assert anm.confidence == 0.85

    pc = derive_severity_and_confidence("protezione_civile", "Allerta rossa per nubifragio")
    assert pc.severity == "critical"
    assert pc.confidence == 0.90

    # Aggregators cap critical keywords down to max_severity='high'
    agg = derive_severity_and_confidence("google_news", "Allerta rossa emergenza traffico")
    assert agg.severity == "high"
    assert agg.confidence == 0.40


def test_pubdate_non_build() -> None:
    """REQ-CONN-06: use item <pubDate> and never <channel><lastBuildDate>."""
    xml_bytes = b"""<?xml version="1.0" encoding="utf-8"?>
    <rss version="2.0">
      <channel>
        <title>Test Feed</title>
        <lastBuildDate>Sat, 14 Nov 2026 23:59:00 +0100</lastBuildDate>
        <item>
          <title>Guasto Linea 2</title>
          <guid>https://example.it/?p=1</guid>
          <pubDate>Sat, 14 Nov 2026 16:12:00 +0100</pubDate>
          <description>Dettaglio guasto</description>
        </item>
        <item>
          <title>Articolo senza pubDate</title>
          <guid>https://example.it/?p=2</guid>
          <description>Da escludere per evitare uso lastBuildDate</description>
        </item>
      </channel>
    </rss>"""

    items = parse_rss_feed(xml_bytes, "anm")
    assert len(items) == 1
    assert items[0].alert_id == "anm:1"
    assert items[0].pub_date == datetime(2026, 11, 14, 15, 12, 0, tzinfo=timezone.utc)


def test_mattino_e_date_italiane() -> None:
    """REQ-CONN-07: decode ISO-8859-1 Il Mattino feed and parse Italian date strings."""
    repo_root = Path(__file__).resolve().parents[3]
    xml_bytes = (repo_root / "shared" / "mocks" / "rss_ilmattino_sample.xml").read_bytes()
    assert b"ISO-8859-1" in xml_bytes

    items = parse_rss_feed(xml_bytes, "ilmattino", declared_encoding="ISO-8859-1")
    assert len(items) == 1
    item = items[0]
    assert item.alert_id == "ilmattino:12345"
    assert item.route_id == "L2"
    assert item.zone_id == "Z_BAGNOLI"
    assert "citt" in item.body.lower()
    assert item.pub_date == datetime(2026, 11, 14, 15, 12, 0, tzinfo=timezone.utc)

