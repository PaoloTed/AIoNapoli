"""Live PostgreSQL checks for the OSM territory catalogue.

These tests are opt-in and require a database populated by
``infra/postgres/import-osm.sh`` plus the psycopg driver.
"""

from __future__ import annotations

import os

import pytest

from app.repositories.territory import OSMTerritoryRepository

DATABASE_URL = os.environ.get("OSM_TEST_DATABASE_URL", "")
SCHEMA = os.environ.get("OSM_TEST_SCHEMA", "osm_territory")
DATASET_KEY = os.environ.get("OSM_TEST_DATASET_KEY", "osm_napoli")

pytestmark = [
    pytest.mark.db,
    pytest.mark.skipif(not DATABASE_URL, reason="OSM_TEST_DATABASE_URL non impostata"),
]


def _repository() -> tuple[OSMTerritoryRepository, object]:
    psycopg = pytest.importorskip("psycopg")
    conn = psycopg.connect(DATABASE_URL)
    return OSMTerritoryRepository(conn, schema=SCHEMA, dataset_key=DATASET_KEY), conn


def test_search_known_roads_and_pois() -> None:
    repo, conn = _repository()
    try:
        info = repo.get_dataset_info()
        assert info is not None
        assert info["source_sha256"]
        assert info["dataset_version"]

        roads = repo.search_ways("Via Toledo", limit=10)
        assert len(roads) >= 2
        assert all(row["osm_key"].startswith("way/") for row in roads)
        assert all(row["geometry"].startswith("LINESTRING(") for row in roads)

        riviera = repo.search_ways("Riviera di Chiaia", limit=10)
        assert riviera
        assert any(row["name"] == "Riviera di Chiaia" for row in riviera)

        castel = repo.search_pois("Castel dell'Ovo", limit=10)
        assert castel
        assert any(row["name"] == "Castel dell'Ovo" for row in castel)

        museo = repo.search_pois("Museo archeologico nazionale di Napoli", limit=10)
        assert museo
        assert any(row["osm_key"].startswith("relation/") for row in museo)

        road = repo.get_way(roads[0]["osm_key"])
        poi = repo.get_poi(castel[0]["osm_key"])
        assert road is not None and road["osm_key"] == roads[0]["osm_key"]
        assert poi is not None and poi["osm_key"] == castel[0]["osm_key"]
    finally:
        conn.close()


def test_proximity_and_intersection_in_metres() -> None:
    repo, conn = _repository()
    try:
        near_ways = repo.find_ways_near(14.2495, 40.8479, radius_m=300, limit=20)
        assert near_ways
        assert all(row["distance_m"] >= 0 for row in near_ways)
        assert min(row["distance_m"] for row in near_ways) <= 300

        near_pois = repo.find_pois_near(14.2480, 40.8277, radius_m=300, limit=20)
        assert near_pois
        assert min(row["distance_m"] for row in near_pois) <= 300

        intersecting = repo.find_ways_intersecting(14.248, 40.846, 14.251, 40.849)
        assert intersecting
        assert all(row["osm_key"].startswith("way/") for row in intersecting)
    finally:
        conn.close()
