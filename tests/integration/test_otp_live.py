"""Opt-in live regression tests against OTP and the persisted GTFS database.

Run only when both services are available:

    OTP_LIVE_BASE_URL=http://127.0.0.1:8080 \
    OTP_LIVE_DATABASE_URL=postgresql://postgres:postgres@127.0.0.1:5432/mobility \
    pytest -m live_otp --force-enable-socket -q tests/integration/test_otp_live.py

The default suite skips this module: no network and no database are required
in CI. Feed IDs are discovered from ``agencies`` on every run.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from app.domain.models.finding import Finding
from app.main import create_app
from app.repositories.postgres import PostgresSourceRepository
from app.services.agents.mobility.agent import MobilityAgent
from app.services.agents.mobility.gtfs_ids import parse_otp_id
from app.services.agents.mobility.otp_client import (
    DEFAULT_MODES,
    OtpClient,
    OtpNoRouteError,
)
from app.services.agents.mobility.otp_graph import map_feeds_to_datasets
from app.services.facade import BackendService
from app.services.journeys import JourneyPlanner
from app.services.orchestrator.config import load_config

OTP_BASE_URL = os.environ.get("OTP_LIVE_BASE_URL", "")
DATABASE_URL = os.environ.get("OTP_LIVE_DATABASE_URL", "")
DATASETS_RAW = os.environ.get("OTP_LIVE_DATASETS", "eav:gtfs_eav,anm:gtfs_anm")
ORIGIN = (40.8943044, 14.2308735)  # Via Domenico Biondi
DESTINATION = (40.8047221, 14.1745403)  # Città della Scienza
DEPARTURE = datetime(2026, 11, 16, 8, 0, tzinfo=ZoneInfo("Europe/Rome"))

pytestmark = [
    pytest.mark.network,
    pytest.mark.live_otp,
    pytest.mark.skipif(
        not (OTP_BASE_URL and DATABASE_URL),
        reason="OTP_LIVE_BASE_URL / OTP_LIVE_DATABASE_URL non impostate",
    ),
]


def _datasets() -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for token in DATASETS_RAW.split(","):
        token = token.strip()
        if token:
            key, schema = token.split(":", 1)
            pairs.append((key.strip(), schema.strip()))
    return pairs


@pytest.fixture(scope="module")
def otp() -> OtpClient:
    return OtpClient(base_url=OTP_BASE_URL, timeout_s=30, mode="real")


@pytest.fixture(scope="module")
def repo() -> Any:
    psycopg = pytest.importorskip("psycopg")
    conn = psycopg.connect(DATABASE_URL)
    repository = PostgresSourceRepository(conn, gtfs_datasets=_datasets())
    try:
        yield repository
    finally:
        conn.close()


@pytest.fixture(scope="module")
def feed_mapping(otp: OtpClient, repo: Any) -> dict[str, str]:
    infos = repo.get_datasets_info()
    mapping = map_feeds_to_datasets(otp.discover_feed_agencies(), infos)
    assert "anm" in mapping.values()
    assert "eav" in mapping.values()
    assert len(set(mapping.values())) == len(mapping)
    return mapping


@pytest.fixture(scope="module")
def db_index(repo: Any) -> dict[str, Any]:
    routes = {(row["dataset_key"], str(row["gtfs_route_id"])): row for row in repo.get_routes()}
    stops = {(row["dataset_key"], str(row["gtfs_stop_id"])): row for row in repo.get_stops()}
    return {"routes": routes, "stops": stops, "trips": {}, "stop_times": {}}


def _dataset_for_leg(leg: dict[str, Any], mapping: dict[str, str]) -> str:
    feed_id, _ = parse_otp_id(str(leg["route_id"]))
    assert feed_id in mapping, f"feed OTP {feed_id} non mappato"
    return mapping[feed_id]


def _verify_leg(repo: Any, db_index: dict[str, Any], dataset: str, leg: dict[str, Any]) -> None:
    assert leg["transit_leg"] is True
    feed_id, route_id = parse_otp_id(str(leg["route_id"]))
    _, trip_id = parse_otp_id(str(leg["trip_id"]))
    _, from_stop_id = parse_otp_id(str(leg["from_stop_id"]))
    _, to_stop_id = parse_otp_id(str(leg["to_stop_id"]))
    assert feed_id

    route = db_index["routes"].get((dataset, route_id))
    assert route is not None, f"route {route_id} assente da {dataset}"
    assert route["gtfs_route_id"] == route_id
    assert route["route_id"] == f"{dataset}:{route_id}"

    trip_key = (dataset, route_id)
    if trip_key not in db_index["trips"]:
        db_index["trips"][trip_key] = repo.get_trips(f"{dataset}:{route_id}")
    trip = next(
        (row for row in db_index["trips"][trip_key] if str(row["gtfs_trip_id"]) == trip_id),
        None,
    )
    assert trip is not None, f"trip {trip_id} assente dalla route {route_id}"

    from_stop = db_index["stops"].get((dataset, from_stop_id))
    to_stop = db_index["stops"].get((dataset, to_stop_id))
    assert from_stop is not None, f"stop {from_stop_id} assente da {dataset}"
    assert to_stop is not None, f"stop {to_stop_id} assente da {dataset}"

    stop_time_key = (dataset, trip_id)
    if stop_time_key not in db_index["stop_times"]:
        db_index["stop_times"][stop_time_key] = repo.get_stop_times(f"{dataset}:{trip_id}")
    stop_times = db_index["stop_times"][stop_time_key]
    from_time = next((row for row in stop_times if str(row["gtfs_stop_id"]) == from_stop_id), None)
    to_time = next((row for row in stop_times if str(row["gtfs_stop_id"]) == to_stop_id), None)
    assert from_time is not None and to_time is not None
    assert str(leg["start_scheduled"])[11:19] == from_time["departure_time"]
    assert str(leg["end_scheduled"])[11:19] == to_time["arrival_time"]


def test_l1_closed_live_has_no_l1_and_db_coherent_alternative(
    otp: OtpClient,
    repo: Any,
    feed_mapping: dict[str, str],
    db_index: dict[str, Any],
) -> None:
    l1_routes = otp.discover_routes(short_name="L1", agency_name="ANM")
    assert len(l1_routes) == 1
    l1 = l1_routes[0]
    assert feed_mapping[l1.feed_id] == "anm"

    plan = otp.plan_itineraries(
        from_lat=ORIGIN[0],
        from_lon=ORIGIN[1],
        to_lat=DESTINATION[0],
        to_lon=DESTINATION[1],
        depart_at=DEPARTURE,
        first=10,
        modes=DEFAULT_MODES,
        transit_only=True,
        exclude_route_ids=(l1.scoped_id,),
    )

    assert plan.routing_errors == []
    assert plan.itineraries, "attesa almeno un'alternativa reale"
    transit_legs = [
        leg for itinerary in plan.itineraries for leg in itinerary.legs if leg.get("transit_leg")
    ]
    assert transit_legs
    assert all(leg.get("route_id") != l1.scoped_id for leg in transit_legs)
    assert all(leg.get("route_short_name") != "L1" for leg in transit_legs)

    for leg in transit_legs:
        dataset = _dataset_for_leg(leg, feed_mapping)
        _verify_leg(repo, db_index, dataset, leg)


def test_feed_mapping_live_is_derived_from_agencies(
    otp: OtpClient, repo: Any, feed_mapping: dict[str, str]
) -> None:
    infos = {row["dataset_key"]: row for row in repo.get_datasets_info()}
    assert set(infos) == {"anm", "eav"}
    assert set(feed_mapping.values()) == {"anm", "eav"}

    routes = repo.get_routes()
    for dataset in ("anm", "eav"):
        sample = next(row for row in routes if row["dataset_key"] == dataset)
        assert sample["gtfs_route_id"]
        assert sample["route_id"] == f"{dataset}:{sample['gtfs_route_id']}"
        assert infos[dataset]["gtfs_schema"].startswith("gtfs_")
        assert infos[dataset]["source_sha256"]


def test_mobility_agent_live_uses_l1_exclusion(
    otp: OtpClient, repo: Any, feed_mapping: dict[str, str]
) -> None:
    l1 = otp.discover_routes(short_name="L1", agency_name="ANM")[0]
    assert feed_mapping[l1.feed_id] == "anm"
    agent = MobilityAgent(repo, otp_client=otp)
    result = agent.evaluate(
        route_id="anm:4955",
        origin_stop_id="anm:6312",
        destination_stop_id="anm:2167",
        exclude_route_ids=(l1.scoped_id,),
        now=DEPARTURE,
    )
    assert isinstance(result, Finding)
    assert result.content["itineraries_count"] >= 1
    assert "L1" not in str(result.content["recommended_route"])


def test_date_matrix_live(otp: OtpClient, feed_mapping: dict[str, str]) -> None:
    days = [
        "2026-11-16",  # lunedì, dentro la validità ANM
        "2026-11-21",  # sabato
        "2026-11-22",  # domenica
        "2026-12-31",  # ultimo giorno di validità ANM
        "2027-01-01",  # fuori validità ANM
    ]
    for day in days:
        departure = datetime.fromisoformat(f"{day}T08:00:00").replace(
            tzinfo=ZoneInfo("Europe/Rome")
        )
        try:
            plan = otp.plan_itineraries(
                from_lat=ORIGIN[0],
                from_lon=ORIGIN[1],
                to_lat=DESTINATION[0],
                to_lon=DESTINATION[1],
                depart_at=departure,
                first=10,
                modes=DEFAULT_MODES,
                transit_only=True,
            )
        except OtpNoRouteError as exc:
            assert day == "2027-01-01", f"{day}: no route inatteso ({exc})"
            continue

        anm_legs = [
            leg
            for itinerary in plan.itineraries
            for leg in itinerary.legs
            if leg.get("transit_leg") and _dataset_for_leg(leg, feed_mapping) == "anm"
        ]
        if day == "2027-01-01":
            assert not anm_legs, "fuori validità ANM non devono comparire corse ANM"
        else:
            assert plan.itineraries, f"{day}: nessun itinerario"
            assert anm_legs, f"{day}: nessuna corsa ANM"


def test_journey_endpoint_live() -> None:
    config = load_config().model_copy(
        update={
            "otp_base_url": OTP_BASE_URL,
            "otp_timeout_s": 30.0,
            "routing_mode": "real",
            "routing_timezone": "Europe/Rome",
        }
    )
    planner = JourneyPlanner(config)
    service = BackendService(config=config, journey_planner=planner)
    app = create_app(service=service)
    payload = {
        "origin": {"lat": ORIGIN[0], "lon": ORIGIN[1]},
        "destination": {"lat": DESTINATION[0], "lon": DESTINATION[1]},
        "depart_at": "2026-11-16T08:00:00",
        "timezone": "Europe/Rome",
        "modes": list(DEFAULT_MODES),
        "transit_only": True,
        "first": 5,
    }
    with TestClient(app) as client:
        response = client.post("/api/v1/journeys/plan", json=payload)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["source"]["is_simulated"] is False
    assert body["itineraries"]
    transit_legs = [
        leg for itinerary in body["itineraries"] for leg in itinerary["legs"] if leg["transit_leg"]
    ]
    assert transit_legs
    assert all(leg["route_id"] and leg["trip_id"] for leg in transit_legs)
    assert all(leg["operator"] for leg in transit_legs)
