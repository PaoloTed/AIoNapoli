"""Defensive RSS parser handling ISO-8859-1, Italian dates, and pubDate-only timestamps."""

from __future__ import annotations

import hashlib
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import parse_qs, urlparse

_ITALIAN_MONTHS: dict[str, int] = {
    "gennaio": 1,
    "gen": 1,
    "febbraio": 2,
    "feb": 2,
    "marzo": 3,
    "mar": 3,
    "aprile": 4,
    "apr": 4,
    "maggio": 5,
    "mag": 5,
    "giugno": 6,
    "giu": 6,
    "luglio": 7,
    "lug": 7,
    "agosto": 8,
    "ago": 8,
    "settembre": 9,
    "set": 9,
    "sett": 9,
    "ottobre": 10,
    "ott": 10,
    "novembre": 11,
    "nov": 11,
    "dicembre": 12,
    "dic": 12,
}

_ITALIAN_WEEKDAYS_RE = re.compile(
    r"^(?:luned[iì]|marted[iì]|mercoled[iì]|gioved[iì]|venerd[iì]|sabato|domenica|"
    r"lun|mar|mer|gio|ven|sab|dom)[,\s]+",
    re.IGNORECASE,
)

_ITALIAN_DATE_RE = re.compile(
    r"(\d{1,2})\s+([a-zA-Zàèéìòù]+)\s+(\d{4})(?:\s+(\d{1,2}):(\d{2})(?::(\d{2}))?)?"
    r"(?:\s*([+-]\d{4}|UTC|GMT|CET|CEST))?",
    re.IGNORECASE,
)

_XML_ENCODING_RE = re.compile(rb'encoding=["\']([A-Za-z0-9._-]+)["\']', re.IGNORECASE)


@dataclass(frozen=True)
class ParsedRssItem:
    alert_id: str
    title: str
    body: str
    pub_date: datetime
    data_reference: str
    route_id: str | None = None
    zone_id: str | None = None


def decode_feed_bytes(raw_bytes: bytes, declared_encoding: str | None = None) -> str:
    """Decode raw RSS bytes respecting XML encoding declaration (e.g., ISO-8859-1)."""
    encoding = declared_encoding
    if encoding is None:
        match = _XML_ENCODING_RE.search(raw_bytes[:256])
        if match:
            encoding = match.group(1).decode("ascii", errors="ignore")
    if encoding:
        text = raw_bytes.decode(encoding, errors="replace")
        # Normalize XML encoding declaration to UTF-8 for ElementTree parsing
        text = re.sub(
            r'encoding=["\'][A-Za-z0-9._-]+["\']',
            'encoding="utf-8"',
            text,
            count=1,
            flags=re.IGNORECASE,
        )
        return text
    try:
        return raw_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return raw_bytes.decode("iso-8859-1", errors="replace")


def parse_rss_date(raw_date: str) -> datetime:
    """Parse standard RFC 2822, ISO 8601, or Italian date strings to UTC datetime."""
    cleaned = raw_date.strip()
    if not cleaned:
        raise ValueError("Data RSS vuota")

    # Try RFC 2822 first
    try:
        dt = parsedate_to_datetime(cleaned)
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
    except (TypeError, ValueError):
        pass

    # Try ISO 8601
    try:
        dt = datetime.fromisoformat(cleaned.replace("Z", "+00:00"))
        return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)
    except ValueError:
        pass

    # Try Italian formatted dates (Il Mattino / Vigili del Fuoco)
    stripped_wd = _ITALIAN_WEEKDAYS_RE.sub("", cleaned).strip()
    match = _ITALIAN_DATE_RE.search(stripped_wd)
    if match:
        day = int(match.group(1))
        month_name = match.group(2).lower()
        month = _ITALIAN_MONTHS.get(month_name)
        if month is not None:
            year = int(match.group(3))
            hour = int(match.group(4) or 0)
            minute = int(match.group(5) or 0)
            second = int(match.group(6) or 0)
            tz_token = match.group(7)
            tz = timezone.utc
            if tz_token:
                if tz_token.startswith(("+", "-")) and len(tz_token) == 5:
                    sign = 1 if tz_token[0] == "+" else -1
                    off_h = int(tz_token[1:3])
                    off_m = int(tz_token[3:5])
                    tz = timezone(timedelta(hours=sign * off_h, minutes=sign * off_m))
                elif tz_token.upper() == "CET":
                    tz = timezone(timedelta(hours=1))
                elif tz_token.upper() == "CEST":
                    tz = timezone(timedelta(hours=2))
            dt = datetime(year, month, day, hour, minute, second, tzinfo=tz)
            return dt.astimezone(timezone.utc)

    raise ValueError(f"Formato data RSS non riconosciuto: {raw_date}")


def derive_alert_id(source_id: str, guid: str | None, title: str, pub_date_raw: str) -> str:
    """Derive deterministic alert_id per SCHEMA.md §4.1."""
    if guid:
        parsed = urlparse(guid)
        qs = parse_qs(parsed.query)
        if "p" in qs and qs["p"] and qs["p"][0].isdigit():
            return f"{source_id}:{qs['p'][0]}"
        digest = hashlib.sha1(guid.encode("utf-8")).hexdigest()[:16]
        return f"{source_id}:{digest}"
    digest = hashlib.sha1(f"{title}|{pub_date_raw}".encode("utf-8")).hexdigest()[:16]
    return f"{source_id}:{digest}"


def _infer_route_and_zone(text: str) -> tuple[str | None, str | None]:
    lower = text.lower()
    route_id: str | None = None
    zone_id: str | None = None
    if "linea 2" in lower or " l2" in lower:
        route_id = "L2"
    elif "r2" in lower:
        route_id = "R2"
    elif "151" in lower:
        route_id = "151"

    if "bagnoli" in lower:
        zone_id = "Z_BAGNOLI"
    elif "fuorigrotta" in lower:
        zone_id = "Z_FUORIGROTTA"
    elif "garibaldi" in lower:
        zone_id = "Z_GARIBALDI"
    elif "municipio" in lower or "beverello" in lower:
        zone_id = "Z_MUNICIPIO"
    elif "decumani" in lower or "spaccanapoli" in lower:
        zone_id = "Z_CENTRO_STORICO"
    return route_id, zone_id


def parse_rss_feed(
    raw_bytes: bytes,
    source_id: str,
    *,
    declared_encoding: str | None = None,
) -> list[ParsedRssItem]:
    """Parse RSS XML strictly using item pubDate (never channel lastBuildDate)."""
    xml_text = decode_feed_bytes(raw_bytes, declared_encoding=declared_encoding)
    root = ET.fromstring(xml_text)

    items: list[ParsedRssItem] = []
    for item_el in root.findall(".//item"):
        title = (item_el.findtext("title") or "").strip()
        description = (item_el.findtext("description") or "").strip()
        guid = (item_el.findtext("guid") or "").strip() or None
        link = (item_el.findtext("link") or "").strip()
        pub_date_raw = (item_el.findtext("pubDate") or "").strip()
        if not pub_date_raw:
            # Never fall back to channel/lastBuildDate (REQ-CONN-06)
            continue

        pub_dt = parse_rss_date(pub_date_raw)
        alert_id = derive_alert_id(source_id, guid, title, pub_date_raw)
        data_ref = guid or link or f"rss:{source_id}:{alert_id}"
        route_id, zone_id = _infer_route_and_zone(f"{title} {description}")
        items.append(
            ParsedRssItem(
                alert_id=alert_id,
                title=title or "(senza titolo)",
                body=description,
                pub_date=pub_dt,
                data_reference=data_ref,
                route_id=route_id,
                zone_id=zone_id,
            )
        )
    return items

