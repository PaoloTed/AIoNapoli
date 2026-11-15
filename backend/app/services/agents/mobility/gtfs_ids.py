"""Explicit identity mapping between GTFS, persisted rows and OTP.

The database persists the original GTFS identifiers unchanged. OTP exposes
them with a graph-instance prefix (``feedId:gtfsId``); the prefix is chosen by
OTP when the graph is built and is not a property of the feed. Therefore it
must be discovered from the running graph (``feeds`` / ``routes.gtfsId``),
never hardcoded to the feed ID observed in a previous test.
"""

from __future__ import annotations


def otp_id(feed_id: str, gtfs_id: str) -> str:
    """Build OTP's ``feedId:gtfsId`` without guessing the feed prefix."""
    feed = str(feed_id).strip()
    gtfs = str(gtfs_id).strip()
    if not feed or ":" in feed:
        raise ValueError(f"feed_id OTP non valido: {feed_id!r}")
    if not gtfs:
        raise ValueError("gtfs_id non può essere vuoto")
    return f"{feed}:{gtfs}"


def parse_otp_id(value: str) -> tuple[str, str]:
    """Split ``feedId:gtfsId`` on the first colon, preserving ID colons."""
    raw = str(value).strip()
    if ":" not in raw:
        raise ValueError(f"ID OTP non feed-scoped: {value!r}")
    feed_id, gtfs_id = raw.split(":", 1)
    if not feed_id or not gtfs_id:
        raise ValueError(f"ID OTP non feed-scoped: {value!r}")
    return feed_id, gtfs_id


def is_feed_scoped_id(value: str) -> bool:
    """Return True for a syntactically valid ``feedId:gtfsId`` value."""
    try:
        parse_otp_id(value)
    except ValueError:
        return False
    return True
