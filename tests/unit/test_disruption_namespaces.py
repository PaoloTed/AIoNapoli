"""Regression coverage: coincident ANM/EAV IDs must never share a reference."""

from datetime import date, datetime, timezone

import pytest

from app.domain.models.disruption import DisruptionLinkInput, LinkEntityType
from app.repositories.disruptions import DisruptionRepository


@pytest.mark.parametrize("kind", [LinkEntityType.ROUTE, LinkEntityType.TRIP, LinkEntityType.STOP])
def test_gtfs_keys_are_dataset_scoped(kind: LinkEntityType) -> None:
    eav = DisruptionRepository._entity_key(kind, "same:id", "eav")
    anm = DisruptionRepository._entity_key(kind, "same:id", "anm")
    assert eav == f"gtfs:eav:{kind.value}:same:id"
    assert anm == f"gtfs:anm:{kind.value}:same:id"
    assert eav != anm


def test_explicit_dataset_is_used_before_reference_lookup() -> None:
    repo = DisruptionRepository(None)
    seen = []

    def reference(key):
        seen.append(key)
        return {"dataset_key": "anm", "dataset_version": "v1", "is_current": True}

    repo._reference = reference
    link = repo._resolve_link(
        DisruptionLinkInput(entity_type=LinkEntityType.ROUTE, entity_id="2", dataset_key="anm")
    )
    assert seen == ["gtfs:anm:route:2"]
    assert link["entity_key"] == "gtfs:anm:route:2"
    assert link["dataset_key"] == "anm"


def test_unresolved_links_keep_dataset_identity() -> None:
    repo = DisruptionRepository(None)
    repo._reference = lambda key: None
    eav, anm = [
        repo._resolve_link(
            DisruptionLinkInput(
                entity_type=LinkEntityType.ROUTE, entity_id="missing", dataset_key=dataset
            )
        )
        for dataset in ("eav", "anm")
    ]
    assert eav["entity_key"] is None and anm["entity_key"] is None
    assert eav["link_ref"] != anm["link_ref"]


def test_trip_calendar_uses_dataset_schema() -> None:
    repo = DisruptionRepository(None)
    queries = []

    def fetch(sql, params=()):
        queries.append((sql, params))
        if "FROM gtfs_datasets" in sql:
            assert params == ("anm",)
            return [{"gtfs_schema": "gtfs_anm"}]
        return [{"active": False}]

    repo._fetchall = fetch
    assert repo._service_active("2", date(2026, 11, 16), "anm") is False
    assert '"gtfs_anm".trips' in queries[1][0]
    assert '"gtfs_eav"' not in queries[1][0]


def test_applicability_query_can_select_anm() -> None:
    repo = DisruptionRepository(None)
    queries = []
    repo._fetchall = lambda sql, params=(): queries.append((sql, params)) or []
    assert (
        repo.find_applicable(
            LinkEntityType.ROUTE,
            "2",
            datetime(2026, 11, 16, tzinfo=timezone.utc),
            dataset_key="anm",
        )
        == []
    )
    assert queries[0][1][0] == "gtfs:anm:route:2"


def test_invalid_dataset_cannot_build_ambiguous_key() -> None:
    with pytest.raises(ValueError):
        DisruptionRepository._entity_key(LinkEntityType.ROUTE, "2", "eav:route")
