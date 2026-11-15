"""Offline contract tests for POST /api/v1/journeys/plan."""

from __future__ import annotations

import json
from typing import Any, Callable

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.services.agents.mobility.otp_client import OtpClient
from app.services.facade import BackendService
from app.services.journeys import JourneyPlanner
from app.services.orchestrator.config import load_config

REQUEST = {
    "origin": {"lat": 40.8943044, "lon": 14.2308735},
    "destination": {"lat": 40.8047221, "lon": 14.1745403},
    "depart_at": "2026-11-16T08:00:00",
    "timezone": "Europe/Rome",
    "modes": ["WALK", "BUS", "RAIL", "SUBWAY"],
    "transit_only": True,
    "first": 10,
}


def _plan_payload() -> dict[str, Any]:
    return {
        "data": {
            "planConnection": {
                "edges": [
                    {
                        "node": {
                            "start": "2026-11-16T08:00:00+01:00",
                            "end": "2026-11-16T08:30:00+01:00",
                            "duration": 1800,
                            "walkTime": 600,
                            "walkDistance": 700.0,
                            "numberOfTransfers": 0,
                            "generalizedCost": 1200,
                            "legs": [
                                {
                                    "mode": "WALK",
                                    "transitLeg": False,
                                    "duration": 600,
                                    "start": {"scheduledTime": "2026-11-16T08:00:00+01:00"},
                                    "end": {"scheduledTime": "2026-11-16T08:10:00+01:00"},
                                    "from": {"lat": 40.8943, "lon": 14.2308},
                                    "to": {"lat": 40.89, "lon": 14.23},
                                },
                                {
                                    "mode": "SUBWAY",
                                    "transitLeg": True,
                                    "duration": 1200,
                                    "start": {"scheduledTime": "2026-11-16T08:10:00+01:00"},
                                    "end": {"scheduledTime": "2026-11-16T08:30:00+01:00"},
                                    "route": {
                                        "gtfsId": "17:4955",
                                        "shortName": "L1",
                                        "longName": "Metropolitana Linea 1",
                                        "mode": "SUBWAY",
                                        "agency": {
                                            "gtfsId": "17:ANM",
                                            "name": "Azienda Napoletana Mobilità",
                                        },
                                    },
                                    "trip": {"gtfsId": "17:trip_l1"},
                                    "from": {
                                        "lat": 40.89,
                                        "lon": 14.23,
                                        "stop": {"gtfsId": "17:6312", "name": "CHIAIANO"},
                                    },
                                    "to": {
                                        "lat": 40.8047,
                                        "lon": 14.1745,
                                        "stop": {"gtfsId": "17:2167", "name": "COROGLIO"},
                                    },
                                },
                            ],
                        }
                    }
                ],
                "routingErrors": [],
            }
        }
    }


def _service(handler: Callable[[httpx.Request], httpx.Response]) -> BackendService:
    config = load_config()
    otp = OtpClient(
        base_url="http://otp.test",
        timeout_s=1.0,
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )
    return BackendService(
        config=config,
        journey_planner=JourneyPlanner(config, otp_client=otp),
    )


def _client(handler: Callable[[httpx.Request], httpx.Response]) -> TestClient:
    return TestClient(create_app(service=_service(handler)))


def test_valid_request_returns_itinerary_and_identifiers() -> None:
    captured: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(200, json=_plan_payload(), request=request)

    with _client(handler) as client:
        response = client.post("/api/v1/journeys/plan", json=REQUEST)

    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert body["contract_version"] == "1.0.0"
    assert body["status"] == "ok"
    assert body["timezone"] == "Europe/Rome"
    assert body["routing_errors"] == []
    assert body["source"]["source_id"] == "otp"
    assert body["source"]["is_simulated"] is False

    itinerary = body["itineraries"][0]
    assert itinerary["duration_s"] == 1800
    assert itinerary["transfers"] == 0
    leg = itinerary["legs"][1]
    assert leg["route_id"] == "17:4955"
    assert leg["trip_id"] == "17:trip_l1"
    assert leg["from_stop_id"] == "17:6312"
    assert leg["to_stop_id"] == "17:2167"
    assert leg["operator"] == "Azienda Napoletana Mobilità"
    assert leg["agency_id"] == "ANM"

    variables = captured[0]["variables"]
    assert variables["dateTime"] == {"earliestDeparture": "2026-11-16T08:00:00+01:00"}
    assert variables["first"] == 10
    assert variables["modes"]["transitOnly"] is True
    assert "SUBWAY" in [item["mode"] for item in variables["modes"]["transit"]["transit"]]


def test_arrive_by_uses_latest_arrival() -> None:
    captured: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(json.loads(request.content))
        return httpx.Response(200, json=_plan_payload(), request=request)

    payload = {key: value for key, value in REQUEST.items() if key != "depart_at"}
    payload["arrive_by"] = "2026-11-16T09:00:00"

    with _client(handler) as client:
        response = client.post("/api/v1/journeys/plan", json=payload)

    assert response.status_code == 200
    assert captured[0]["variables"]["dateTime"] == {"latestArrival": "2026-11-16T09:00:00+01:00"}


def test_no_route_is_an_explicit_empty_result() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "data": {
                    "planConnection": {
                        "edges": [],
                        "routingErrors": [
                            {
                                "code": "NO_TRANSIT_CONNECTION_IN_SEARCH_WINDOW",
                                "description": "Nessun servizio nella finestra",
                            }
                        ],
                    }
                }
            },
            request=request,
        )

    with _client(handler) as client:
        response = client.post("/api/v1/journeys/plan", json=REQUEST)

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "no_route"
    assert body["itineraries"] == []
    assert body["routing_errors"][0]["code"] == "NO_TRANSIT_CONNECTION_IN_SEARCH_WINDOW"


@pytest.mark.parametrize(
    ("transport", "status", "code"),
    [
        (httpx.ReadTimeout("timeout"), 504, "otp_timeout"),
        (httpx.ConnectError("offline"), 503, "otp_unavailable"),
    ],
)
def test_transport_errors_are_distinct(transport: Exception, status: int, code: str) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise transport

    with _client(handler) as client:
        response = client.post("/api/v1/journeys/plan", json=REQUEST)

    assert response.status_code == status
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == code


def test_http_error_is_distinct() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="down", request=request)

    with _client(handler) as client:
        response = client.post("/api/v1/journeys/plan", json=REQUEST)

    assert response.status_code == 502
    assert response.json()["code"] == "otp_http_error"


def test_graphql_error_is_distinct() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"errors": [{"message": "CoordinateValue non valido"}]},
            request=request,
        )

    with _client(handler) as client:
        response = client.post("/api/v1/journeys/plan", json=REQUEST)

    assert response.status_code == 502
    assert response.json()["code"] == "otp_graphql_error"


def test_invalid_response_is_distinct() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"not-json", request=request)

    with _client(handler) as client:
        response = client.post("/api/v1/journeys/plan", json=REQUEST)

    assert response.status_code == 502
    assert response.json()["code"] == "otp_invalid_response"


@pytest.mark.parametrize(
    ("patch", "field"),
    [
        ({"origin": {"lat": 91, "lon": 14.2}}, "origin.lat"),
        ({"origin": {"lat": 40.8, "lon": 181}}, "origin.lon"),
        ({"timezone": "Mars/Olympus"}, "timezone"),
        ({"modes": ["WALK"]}, "modes"),
        ({"modes": ["FLYING_SAUCER"]}, "modes"),
        ({"first": 0}, "first"),
        ({"arrive_by": "2026-11-16T09:00:00"}, "request"),
    ],
)
def test_invalid_input_is_422(patch: dict[str, Any], field: str) -> None:
    payload = {**REQUEST, **patch}

    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("input non valido: nessuna chiamata OTP attesa")

    with _client(handler) as client:
        response = client.post("/api/v1/journeys/plan", json=payload)

    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "invalid_journey_request"
    if field != "request":
        assert body["field"] == field


def test_malformed_json_is_422() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("JSON non valido: nessuna chiamata OTP attesa")

    with _client(handler) as client:
        response = client.post(
            "/api/v1/journeys/plan",
            content=b"{not-json",
            headers={"Content-Type": "application/json"},
        )

    assert response.status_code == 422
    assert response.json()["code"] == "invalid_journey_request"
    assert response.json()["field"] == "request"
