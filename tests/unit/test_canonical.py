"""Unit tests for canonical JSON serialization and deterministic SHA-256 hashing."""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

from app.domain.models.finding import AgentName, Finding, FindingType, Severity
from app.utils.canonical import canonical_json


def test_hash_stabile() -> None:
    """NFR-01: identical inputs produce byte-for-byte identical canonical JSON and SHA-256."""
    tz_plus1 = timezone(timedelta(hours=1))
    f_plus1 = Finding(
        agent=AgentName.MOBILITY,
        type=FindingType.ROUTE_DISRUPTION,
        content={"zone_id": "Z_BAGNOLI", "congestion": 0.88001, "meta": {"z": 1, "a": 2}},
        confidence=0.90,
        severity=Severity.HIGH,
        source_id="anm",
        data_reference="rss:1",
        is_simulated=False,
        timestamp=datetime(2026, 11, 14, 17, 12, 0, tzinfo=tz_plus1),
    )
    f_utc = Finding(
        agent=AgentName.MOBILITY,
        type=FindingType.ROUTE_DISRUPTION,
        content={"meta": {"a": 2, "z": 1}, "congestion": 0.88002, "zone_id": "Z_BAGNOLI"},
        confidence=0.904,
        severity=Severity.HIGH,
        source_id="anm",
        data_reference="rss:1",
        is_simulated=False,
        timestamp=datetime(2026, 11, 14, 16, 12, 0, tzinfo=timezone.utc),
    )

    c1 = canonical_json(f_plus1)
    c2 = canonical_json(f_utc)
    assert c1 == c2
    h1 = hashlib.sha256(c1.encode("utf-8")).hexdigest()
    h2 = hashlib.sha256(c2.encode("utf-8")).hexdigest()
    assert h1 == h2

