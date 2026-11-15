"""Live PostgreSQL checks for the authoritative GTFS repository adapter.

These tests are opt-in: they require a real database populated by
``infra/postgres/import-gtfs.sh`` and the psycopg driver.
"""

from __future__ import annotations

import os

import pytest

from app.repositories.postgres import PostgresSourceRepository

DATABASE_URL = os.environ.get("GTFS_TEST_DATABASE_URL", "")
SCHEMA = os.environ.get("GTFS_TEST_SCHEMA", "gtfs_eav")
DATASET_KEY = os.environ.get("GTFS_TEST_DATASET_KEY", "eav")

pytestmark = [
    pytest.mark.db,
    pytest.mark.skipif(not DATABASE_URL, reason="GTFS_TEST_DATABASE_URL non impostata"),
]


def _repository() -> tuple[PostgresSourceRepository, object]:
    psycopg = pytest.importorskip("psycopg")
    conn = psycopg.connect(DATABASE_URL)
    return PostgresSourceRepository(
        conn,
        gtfs_schema=SCHEMA,
        gtfs_dataset_key=DATASET_KEY,
    ), conn


def test_repository_reads_imported_network() -> None:
    repo, conn = _repository()
    try:
        info = repo.get_dataset_info()
        assert info is not None
        assert info["gtfs_schema"] == SCHEMA
        assert info["source_sha256"]
        assert info["dataset_version"]

        routes = repo.get_routes()
        stops = repo.get_stops()
        trips = repo.get_trips("2")
        assert routes and stops and trips
        assert all(stop["zone_id"] is None for stop in stops)
        assert all(stop["geometry"].startswith("POINT(") for stop in stops)

        first_trip = trips[0]["trip_id"]
        stop_times = repo.get_stop_times(first_trip)
        assert stop_times
        assert stop_times[0]["trip_id"] == first_trip

        active = repo.get_active_trips("2026-11-16")
        assert len(active) == 682

        shapes = repo.get_shapes()
        assert shapes
        assert shapes[0]["geometry"].startswith("LINESTRING(")
    finally:
        conn.close()


def test_repository_keeps_multiple_datasets_distinct() -> None:
    """EAV and ANM remain visible even when their original stop IDs collide."""
    psycopg = pytest.importorskip("psycopg")
    conn = psycopg.connect(DATABASE_URL)
    repo = PostgresSourceRepository(
        conn,
        gtfs_datasets=[("eav", "gtfs_eav"), ("anm", "gtfs_anm")],
    )
    try:
        infos = {row["dataset_key"]: row for row in repo.get_datasets_info()}
        assert set(infos) == {"eav", "anm"}
        assert infos["eav"]["gtfs_schema"] == "gtfs_eav"
        assert infos["anm"]["gtfs_schema"] == "gtfs_anm"

        stops = repo.get_stops()
        stop_keys = {(row["dataset_key"], row["gtfs_stop_id"]) for row in stops}
        assert ("eav", "6238") in stop_keys
        assert ("anm", "6238") in stop_keys
        assert {row["stop_id"] for row in stops if row["gtfs_stop_id"] == "6238"} == {
            "eav:6238",
            "anm:6238",
        }

        routes = repo.get_routes()
        assert any(
            row["dataset_key"] == "anm" and row["gtfs_route_id"] == "4955"
            for row in routes
        )
        assert any(
            row["dataset_key"] == "eav" and row["gtfs_route_id"] == "2"
            for row in routes
        )
    finally:
        conn.close()


def test_over_24h_times_are_preserved() -> None:
    repo, conn = _repository()
    try:
        # 2025-09-22 is inside the EAV bus services' original validity.
        stop_times = repo.get_active_stop_times("2025-09-22")
        assert any(
            (row["arrival_time"] or "") >= "24:00:00"
            or (row["departure_time"] or "") >= "24:00:00"
            for row in stop_times
        )
    finally:
        conn.close()
