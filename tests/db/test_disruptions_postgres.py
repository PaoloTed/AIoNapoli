"""Live PostgreSQL checks for persistent disruptions and stable references.

All records created here are clearly simulated fixtures (``is_simulated=True``,
``fixture_2c_test`` source) and are removed at test start/end. No production
GTFS/OSM rows are deleted or mutated.
"""

from __future__ import annotations

import os
from datetime import date, datetime, timezone

import pytest

from app.domain.models.disruption import (
    DailyRecurrence,
    Direction,
    DisruptionEffect,
    DisruptionInput,
    DisruptionLinkInput,
    LifecycleStatus,
    LinkEntityType,
    ResolutionStatus,
    Uncertainty,
    VerificationStatus,
)
from app.domain.models.finding import Severity
from app.repositories.disruptions import DisruptionRepository

DATABASE_URL = os.environ.get("DISRUPTION_TEST_DATABASE_URL", "")
GTFS_SCHEMA = os.environ.get("DISRUPTION_TEST_GTFS_SCHEMA", "gtfs_eav")
GTFS_KEY = os.environ.get("DISRUPTION_TEST_GTFS_KEY", "eav")
OSM_KEY = os.environ.get("DISRUPTION_TEST_OSM_KEY", "osm_napoli")

pytestmark = [
    pytest.mark.db,
    pytest.mark.skipif(not DATABASE_URL, reason="DISRUPTION_TEST_DATABASE_URL non impostata"),
]

NOW = datetime(2026, 11, 16, 9, 0, tzinfo=timezone.utc)
SOURCE = "fixture_2c_test"


def _ids(
    repo: DisruptionRepository,
    entity_type: LinkEntityType,
    entity_id: str,
    at: datetime,
    **kwargs: object,
) -> list[str]:
    return [
        row.alert_id
        for row in repo.find_applicable(
            entity_type, entity_id, at, include_simulated=True, **kwargs
        )
        if row.source_id == SOURCE
    ]


def _cleanup(conn: object) -> None:
    cur = conn.cursor()  # type: ignore[attr-defined]
    cur.execute("DELETE FROM service_alerts WHERE source_id LIKE %s", (f"{SOURCE}%",))
    cur.execute(
        "DELETE FROM reference_entities WHERE entity_key LIKE %s",
        (f"gtfs:{GTFS_KEY}:route:__TEST_2C__%",),
    )
    conn.commit()  # type: ignore[attr-defined]


@pytest.fixture()
def repo() -> object:
    psycopg = pytest.importorskip("psycopg")
    conn = psycopg.connect(DATABASE_URL)
    _cleanup(conn)
    repository = DisruptionRepository(
        conn,
        gtfs_schema=GTFS_SCHEMA,
        gtfs_dataset_key=GTFS_KEY,
        osm_dataset_key=OSM_KEY,
    )
    try:
        yield repository
    finally:
        _cleanup(conn)
        conn.close()


def _base(
    alert_id: str,
    *,
    effect: DisruptionEffect = DisruptionEffect.BLOCK,
    links: list[DisruptionLinkInput] | None = None,
    **overrides: object,
) -> DisruptionInput:
    values: dict[str, object] = {
        "source_id": SOURCE,
        "alert_id": alert_id,
        "source_url": f"fixture://2c/{alert_id}",
        "data_reference": f"fixture:2c:{alert_id}",
        "title": f"[SIMULATO] Fixture 2C {alert_id}",
        "description": "Fixture simulata per CHECKPOINT 2C; non è un incidente reale.",
        "alert_type": "closure",
        "effect": effect,
        "severity": Severity.HIGH,
        "confidence": 0.9,
        "published_at": datetime(2026, 11, 14, 10, 0, tzinfo=timezone.utc),
        "valid_from": datetime(2026, 11, 15, 0, 0, tzinfo=timezone.utc),
        "valid_to": datetime(2026, 11, 20, 23, 59, tzinfo=timezone.utc),
        "timezone": "Europe/Rome",
        "lifecycle_status": LifecycleStatus.ACTIVE,
        "verification_status": VerificationStatus.VERIFIED,
        "uncertainty": Uncertainty.LOW,
        "is_simulated": True,
        "links": links
        or [DisruptionLinkInput(entity_type=LinkEntityType.ROUTE, entity_id="2", mode="rail")],
    }
    values.update(overrides)
    return DisruptionInput.model_validate(values)


def test_multi_entity_idempotency_and_revision(repo: DisruptionRepository) -> None:
    links = [
        DisruptionLinkInput(entity_type=LinkEntityType.ROUTE, entity_id="2", mode="rail"),
        DisruptionLinkInput(
            entity_type=LinkEntityType.TRIP,
            entity_id="2080_opttp2026-2030-12",
            direction=Direction.FORWARD,
            mode="rail",
            service_date=date(2026, 11, 16),
        ),
        DisruptionLinkInput(entity_type=LinkEntityType.STOP, entity_id="6711"),
        DisruptionLinkInput(entity_type=LinkEntityType.STOP, entity_id="6112"),
        DisruptionLinkInput(entity_type=LinkEntityType.OSM_WAY, entity_id="way/269910733"),
        DisruptionLinkInput(entity_type=LinkEntityType.OSM_POI, entity_id="way/338168783"),
    ]
    first = repo.upsert(_base("multi-entity", links=links))
    assert first.revision == 1
    assert len(first.links) == 6
    assert all(link.resolution_status is ResolutionStatus.RESOLVED for link in first.links)

    again = repo.upsert(_base("multi-entity", links=links))
    assert again.revision == 1
    assert len(again.links) == 6

    changed = repo.upsert(
        _base(
            "multi-entity",
            links=links,
            title="[SIMULATO] Fixture 2C aggiornata",
        )
    )
    assert changed.revision == 2
    cur = repo._conn.cursor()  # type: ignore[attr-defined]
    cur.execute(
        "SELECT count(*) FROM service_alert_revisions WHERE source_id=%s AND alert_id=%s",
        (SOURCE, "multi-entity"),
    )
    assert cur.fetchone()[0] == 2


def test_temporal_lifecycle_and_direction(repo: DisruptionRepository) -> None:
    active = repo.upsert(_base("active"))
    assert _ids(repo, LinkEntityType.ROUTE, "2", NOW) == ["active"]

    repo.upsert(
        _base(
            "future",
            published_at=datetime(2026, 12, 1, tzinfo=timezone.utc),
            valid_from=datetime(2026, 11, 15, tzinfo=timezone.utc),
            valid_to=datetime(2026, 12, 31, tzinfo=timezone.utc),
        )
    )
    assert "future" not in _ids(repo, LinkEntityType.ROUTE, "2", NOW)

    repo.upsert(
        _base(
            "expired",
            valid_from=datetime(2026, 11, 1, tzinfo=timezone.utc),
            valid_to=datetime(2026, 11, 10, tzinfo=timezone.utc),
        )
    )
    assert "expired" not in _ids(repo, LinkEntityType.ROUTE, "2", NOW)

    resolved = repo.resolve(SOURCE, active.alert_id, at=NOW)
    assert resolved.lifecycle_status is LifecycleStatus.RESOLVED
    assert "active" not in _ids(repo, LinkEntityType.ROUTE, "2", NOW)

    cancelled = repo.upsert(_base("cancelled"))
    cancelled = repo.cancel(SOURCE, cancelled.alert_id, at=NOW)
    assert cancelled.lifecycle_status is LifecycleStatus.CANCELLED

    direction_alert = repo.upsert(
        _base(
            "directional",
            links=[
                DisruptionLinkInput(
                    entity_type=LinkEntityType.ROUTE,
                    entity_id="2",
                    direction=Direction.FORWARD,
                    mode="rail",
                )
            ],
        )
    )
    assert direction_alert.revision == 1
    assert _ids(repo, LinkEntityType.ROUTE, "2", NOW, direction=Direction.FORWARD) == [
        "directional"
    ]
    assert "directional" not in _ids(
        repo, LinkEntityType.ROUTE, "2", NOW, direction=Direction.BACKWARD
    )


def test_daily_recurrence_is_not_continuous(repo: DisruptionRepository) -> None:
    alert = _base(
        "recurring",
        effect=DisruptionEffect.PENALIZE,
        recurrence=DailyRecurrence(start="08:00", end="10:00", days=[0, 1, 2, 3, 4, 5, 6]),
    )
    repo.upsert(alert)
    local_inside = datetime(2026, 11, 16, 8, 30, tzinfo=timezone.utc)  # 09:30 CET
    local_outside = datetime(2026, 11, 16, 11, 30, tzinfo=timezone.utc)  # 12:30 CET
    assert _ids(repo, LinkEntityType.ROUTE, "2", local_inside) == ["recurring"]
    assert "recurring" not in _ids(repo, LinkEntityType.ROUTE, "2", local_outside)


def test_unresolved_and_historical_links(repo: DisruptionRepository) -> None:
    missing = repo.upsert(
        _base(
            "unresolved",
            effect=DisruptionEffect.INFO,
            links=[
                DisruptionLinkInput(
                    entity_type=LinkEntityType.ROUTE,
                    entity_id="NO_SUCH_ROUTE_2C",
                )
            ],
        )
    )
    assert missing.links[0].resolution_status is ResolutionStatus.UNRESOLVED
    assert missing.links[0].entity_key is None
    assert "NO_SUCH_ROUTE_2C" in missing.links[0].raw_reference

    cur = repo._conn.cursor()  # type: ignore[attr-defined]
    cur.execute(
        """
        INSERT INTO reference_entities (
            entity_key, domain, entity_type, dataset_key, entity_id, display_name,
            mode, dataset_version, is_current
        ) VALUES (
            %s, 'gtfs', 'route', %s, '__TEST_2C__',
            'Test historical route', 'bus', 'test-version', FALSE
        )
        """,
        (f"gtfs:{GTFS_KEY}:route:__TEST_2C__", GTFS_KEY),
    )
    repo._conn.commit()  # type: ignore[attr-defined]
    historical = repo.upsert(
        _base(
            "historical",
            effect=DisruptionEffect.INFO,
            links=[
                DisruptionLinkInput(
                    entity_type=LinkEntityType.ROUTE,
                    entity_id="__TEST_2C__",
                )
            ],
        )
    )
    assert historical.links[0].resolution_status is ResolutionStatus.HISTORICAL
    assert historical.links[0].entity_key == f"gtfs:{GTFS_KEY}:route:__TEST_2C__"


def test_trip_service_date_is_checked(repo: DisruptionRepository) -> None:
    alert = repo.upsert(
        _base(
            "trip-date",
            links=[
                DisruptionLinkInput(
                    entity_type=LinkEntityType.TRIP,
                    entity_id="2080_opttp2026-2030-12",
                    service_date=date(2026, 11, 16),
                    mode="rail",
                )
            ],
        )
    )
    assert alert.links[0].service_active is True
    assert _ids(
        repo,
        LinkEntityType.TRIP,
        "2080_opttp2026-2030-12",
        NOW,
        service_date=date(2026, 11, 16),
    ) == ["trip-date"]
    assert "trip-date" not in _ids(
        repo,
        LinkEntityType.TRIP,
        "2080_opttp2026-2030-12",
        NOW,
        service_date=date(2026, 11, 17),
    )
