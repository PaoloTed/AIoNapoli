"""Contract tests for the OTP 2.10 GTFS GraphQL client."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
from zoneinfo import ZoneInfo

import httpx
import pytest

from app.domain.models.finding import Finding
from app.domain.models.refusal import Refusal
from app.repositories.memory import InMemorySourceRepository
from app.services.agents.mobility.agent import MobilityAgent
from app.services.agents.mobility.otp_client import (
    ItineraryPlan,
    OtpClient,
    OtpGraphQLError,
    OtpHttpError,
    OtpInvalidResponseError,
    OtpNoRouteError,
    OtpTimeoutError,
    OtpUnavailableError,
)

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "otp2"
DEPARTURE = datetime(2026, 11, 16, 8, 0, tzinfo=ZoneInfo("Europe/Rome"))
ORIGIN = (40.851017, 14.272976)  # Napoli P. Garibaldi
DESTINATION = (40.759526, 14.451518)  # Torre Annunziata - Oplonti


def load_fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def make_client(
    handler: Callable[[httpx.Request], httpx.Response],
    *,
    mode: str = "real",
) -> OtpClient:
    return OtpClient(
        base_url="http://otp.test",
        timeout_s=1.0,
        mode=mode,  # type: ignore[arg-type]
        http_client=httpx.Client(transport=httpx.MockTransport(handler)),
    )


def json_handler(
    payload: dict[str, Any],
    *,
    status_code: int = 200,
    capture: list[dict[str, Any]] | None = None,
) -> Callable[[httpx.Request], httpx.Response]:
    def handler(request: httpx.Request) -> httpx.Response:
        if capture is not None:
            capture.append(json.loads(request.content))
        return httpx.Response(status_code, json=payload, request=request)

    return handler


def plan(
    client: OtpClient,
    *,
    exclude_route_ids: tuple[str, ...] = (),
) -> ItineraryPlan:
    return client.plan_itineraries(
        from_lat=ORIGIN[0],
        from_lon=ORIGIN[1],
        to_lat=DESTINATION[0],
        to_lon=DESTINATION[1],
        depart_at=DEPARTURE,
        first=8,
        modes=("WALK", "BUS", "RAIL"),
        transit_only=True,
        exclude_route_ids=exclude_route_ids,
    )


def minimal_payload() -> dict[str, Any]:
    """A valid response with only mandatory fields populated."""
    return {
        "data": {
            "planConnection": {
                "edges": [
                    {
                        "node": {
                            "start": "2026-11-16T08:00:00+01:00",
                            "end": "2026-11-16T08:10:00+01:00",
                            "duration": 600,
                            "legs": [
                                {
                                    "mode": "RAIL",
                                    "transitLeg": True,
                                    "duration": 600,
                                    "start": {
                                        "scheduledTime": "2026-11-16T08:00:00+01:00"
                                    },
                                    "end": {
                                        "scheduledTime": "2026-11-16T08:10:00+01:00"
                                    },
                                    "route": {"gtfsId": "1:1"},
                                    "trip": {"gtfsId": "1:trip"},
                                    "from": {
                                        "lat": 40.0,
                                        "lon": 14.0,
                                        "stop": {"gtfsId": "1:a"},
                                    },
                                    "to": {
                                        "lat": 40.1,
                                        "lon": 14.1,
                                        "stop": {"gtfsId": "1:b"},
                                    },
                                }
                            ],
                        }
                    }
                ],
                "routingErrors": [],
            }
        }
    }


def test_multiple_itineraries_and_identifiers() -> None:
    client = make_client(json_handler(load_fixture("plan_baseline_b.json")))
    result = plan(client)

    assert len(result.itineraries) == 6
    assert result.is_simulated is False
    assert result.routing_errors == []
    first = result.itineraries[0]
    assert first.duration_s == 1770
    assert first.transfers == 0
    assert first.legs[0]["route_id"] == "1:1"
    assert first.legs[0]["trip_id"].startswith("1:")
    assert first.legs[0]["from_stop_id"] == "1:6003"
    assert first.legs[0]["to_stop_id"] == "1:6041"
    assert first.legs[0]["start_scheduled"] == "2026-11-16T08:03:00+01:00"
    assert first.legs[0]["geometry"]
    assert first.legs[0]["geometry_length"] > 0


def test_minimal_itinerary_accepts_missing_optional_fields() -> None:
    client = make_client(json_handler(minimal_payload()))
    result = plan(client)
    assert len(result.itineraries) == 1
    assert result.itineraries[0].duration_s == 600
    leg = result.itineraries[0].legs[0]
    assert leg["route_id"] == "1:1"
    assert leg["trip_id"] == "1:trip"
    assert leg["geometry"] is None
    assert result.itineraries[0].walk_time_s is None
    assert result.itineraries[0].transfers is None


def test_incomplete_itinerary_is_invalid() -> None:
    payload = {
        "data": {
            "planConnection": {
                "edges": [{"node": {"legs": [{"mode": "RAIL"}]}}],
                "routingErrors": [],
            }
        }
    }
    client = make_client(json_handler(payload))
    with pytest.raises(OtpInvalidResponseError):
        plan(client)


def test_incoherent_leg_times_and_duration_are_invalid() -> None:
    payload = minimal_payload()
    node = payload["data"]["planConnection"]["edges"][0]["node"]
    node["legs"][0]["end"]["scheduledTime"] = "2026-11-16T07:50:00+01:00"
    client = make_client(json_handler(payload))
    with pytest.raises(OtpInvalidResponseError):
        plan(client)

    payload = minimal_payload()
    node = payload["data"]["planConnection"]["edges"][0]["node"]
    node["duration"] = 500
    client = make_client(json_handler(payload))
    with pytest.raises(OtpInvalidResponseError):
        plan(client)

    payload = minimal_payload()
    node = payload["data"]["planConnection"]["edges"][0]["node"]
    node["duration"] = -1
    client = make_client(json_handler(payload))
    with pytest.raises(OtpInvalidResponseError):
        plan(client)

    payload = minimal_payload()
    node = payload["data"]["planConnection"]["edges"][0]["node"]
    node["start"] = "2026-11-16T07:59:00+01:00"
    node["duration"] = 660
    client = make_client(json_handler(payload))
    with pytest.raises(OtpInvalidResponseError):
        plan(client)

    payload = minimal_payload()
    node = payload["data"]["planConnection"]["edges"][0]["node"]
    node["legs"][0]["duration"] = -1
    client = make_client(json_handler(payload))
    with pytest.raises(OtpInvalidResponseError):
        plan(client)


def test_duration_is_calculated_only_from_valid_times() -> None:
    payload = minimal_payload()
    node = payload["data"]["planConnection"]["edges"][0]["node"]
    del node["duration"]
    del node["legs"][0]["duration"]
    client = make_client(json_handler(payload))
    result = plan(client)
    assert result.itineraries[0].duration_s == 600
    assert result.itineraries[0].legs[0]["duration_s"] == 600.0

    payload = minimal_payload()
    node = payload["data"]["planConnection"]["edges"][0]["node"]
    del node["duration"]
    del node["start"]
    del node["end"]
    del node["legs"][0]["duration"]
    client = make_client(json_handler(payload))
    result = plan(client)
    assert result.itineraries[0].duration_s == 600
    assert result.itineraries[0].start == "2026-11-16T08:00:00+01:00"
    assert result.itineraries[0].end == "2026-11-16T08:10:00+01:00"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("lat", None),
        ("lon", 181),
        ("lat", 91),
    ],
)
def test_invalid_response_coordinates_are_invalid_response(field: str, value: Any) -> None:
    payload = minimal_payload()
    node = payload["data"]["planConnection"]["edges"][0]["node"]
    node["legs"][0]["from"][field] = value
    client = make_client(json_handler(payload))
    with pytest.raises(OtpInvalidResponseError):
        plan(client)


def test_recorded_baseline_with_missing_coordinate_is_invalid_response() -> None:
    payload = load_fixture("plan_baseline_b.json")
    node = payload["data"]["planConnection"]["edges"][0]["node"]
    node["legs"][0]["from"]["lat"] = None
    client = make_client(json_handler(payload))
    with pytest.raises(OtpInvalidResponseError):
        plan(client)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("lat", None),
        ("lon", 181),
    ],
)
def test_mobility_maps_invalid_response_coordinate_to_otp_error(
    field: str, value: Any
) -> None:
    payload = minimal_payload()
    node = payload["data"]["planConnection"]["edges"][0]["node"]
    node["legs"][0]["from"][field] = value
    client = make_client(json_handler(payload))
    agent = MobilityAgent(
        InMemorySourceRepository(load_fixtures=True),
        otp_client=client,
    )
    result = agent.evaluate(
        route_id="L2",
        origin_stop_id="STOP_GAR_01",
        destination_stop_id="STOP_BAG_01",
        now=DEPARTURE,
    )
    assert isinstance(result, Refusal)
    assert result.reason_code == "otp_error"
    assert f"leg.from.{field}" in result.detail


def test_transit_leg_requires_route_trip_and_stop_ids() -> None:
    payload = minimal_payload()
    node = payload["data"]["planConnection"]["edges"][0]["node"]
    node["legs"][0]["trip"] = {}
    client = make_client(json_handler(payload))
    with pytest.raises(OtpInvalidResponseError):
        plan(client)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("from_lat", 91),
        ("from_lat", -91),
        ("from_lon", 181),
        ("to_lon", -181),
        ("to_lat", float("nan")),
        ("to_lon", float("inf")),
        ("from_lat", "40"),
        ("to_lat", True),
    ],
)
def test_invalid_coordinates_are_rejected_before_network(field: str, value: Any) -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        raise AssertionError("invalid coordinates must not reach the network")

    client = make_client(handler)
    kwargs = {
        "from_lat": ORIGIN[0],
        "from_lon": ORIGIN[1],
        "to_lat": DESTINATION[0],
        "to_lon": DESTINATION[1],
        "depart_at": DEPARTURE,
    }
    kwargs[field] = value
    with pytest.raises(ValueError, match=field):
        client.plan_itineraries(**kwargs)
    assert calls == []


def test_exclusion_is_a_graphql_variable_and_not_concatenated() -> None:
    captured: list[dict[str, Any]] = []
    client = make_client(
        json_handler(load_fixture("plan_excluded_b.json"), capture=captured)
    )
    result = plan(client, exclude_route_ids=("1:1",))

    assert len(captured) == 1
    request = captured[0]
    assert request["query"] == request["query"].strip()
    assert "1:1" not in request["query"]
    variables = request["variables"]
    assert variables["first"] == 8
    assert variables["dateTime"] == {"earliestDeparture": "2026-11-16T08:00:00+01:00"}
    assert variables["modes"] == {
        "direct": [],
        "transit": {"transit": [{"mode": "BUS"}, {"mode": "RAIL"}]},
        "transitOnly": True,
    }
    assert variables["preferences"] == {
        "transit": {"filters": [{"exclude": [{"routes": ["1:1"]}]}]}
    }

    route_ids = [leg["route_id"] for itinerary in result.itineraries for leg in itinerary.legs]
    assert len(result.itineraries) == 4
    assert "1:1" not in route_ids
    assert {"1:4", "1:1."} & set(route_ids)


def test_arrive_by_uses_latest_arrival_with_timezone() -> None:
    captured: list[dict[str, Any]] = []
    client = make_client(
        json_handler(load_fixture("plan_baseline_b.json"), capture=captured)
    )
    client.plan_itineraries(
        from_lat=ORIGIN[0],
        from_lon=ORIGIN[1],
        to_lat=DESTINATION[0],
        to_lon=DESTINATION[1],
        arrive_by=DEPARTURE,
        first=8,
    )
    assert captured[0]["variables"]["dateTime"] == {
        "latestArrival": "2026-11-16T08:00:00+01:00"
    }


def test_no_route_is_distinct_from_upstream_failure() -> None:
    client = make_client(json_handler(load_fixture("no_route_a.json")))
    with pytest.raises(OtpNoRouteError) as exc_info:
        plan(client, exclude_route_ids=("1:2",))
    assert exc_info.value.routing_errors[0]["code"] == "NO_TRANSIT_CONNECTION"


def test_timeout_is_distinct() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timed out", request=request)

    client = make_client(handler)
    with pytest.raises(OtpTimeoutError):
        plan(client)


def test_http_error_is_distinct() -> None:
    client = make_client(json_handler({"error": "down"}, status_code=503))
    with pytest.raises(OtpHttpError) as exc_info:
        plan(client)
    assert exc_info.value.status_code == 503


def test_graphql_error_with_http_200_is_distinct() -> None:
    client = make_client(json_handler(load_fixture("graphql_error.json")))
    with pytest.raises(OtpGraphQLError) as exc_info:
        plan(client)
    assert "CoordinateValue" in str(exc_info.value)


def test_invalid_json_is_distinct() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"not-json", request=request)

    client = make_client(handler)
    with pytest.raises(OtpInvalidResponseError):
        plan(client)


def test_missing_plan_connection_is_invalid_response() -> None:
    client = make_client(json_handler({"data": {}}))
    with pytest.raises(OtpInvalidResponseError):
        plan(client)


def test_routing_errors_with_usable_itineraries_are_preserved() -> None:
    client = make_client(json_handler(load_fixture("plan_with_warning.json")))
    result = plan(client)
    assert len(result.itineraries) == 6
    assert result.routing_errors[0]["code"] == "NO_TRANSIT_CONNECTION"
    assert result.routing_errors[0]["description"]


def test_demo_never_calls_http_and_is_marked_simulated() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        raise AssertionError("demo mode must not perform HTTP requests")

    client = make_client(handler, mode="demo")
    result = plan(client)
    assert calls == []
    assert result.is_simulated is True
    assert result.source_id == "otp_fixture"
    assert result.fallback_reason == "demo_mode_fixture"
    assert result.itineraries


def test_real_mode_never_falls_back_to_fixture() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    client = make_client(handler, mode="real")
    with pytest.raises(OtpUnavailableError):
        plan(client)


def test_exclusion_requires_feed_scoped_id() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("validation must happen before HTTP")

    client = make_client(handler)
    with pytest.raises(ValueError, match="feedId:routeId"):
        plan(client, exclude_route_ids=("1",))


def test_real_agent_does_not_invent_coordinates() -> None:
    agent = MobilityAgent(
        InMemorySourceRepository(load_fixtures=True),
        otp_client=OtpClient(mode="real"),
    )
    result = agent.evaluate(route_id="L2")
    assert isinstance(result, Refusal)
    assert result.reason_code == "unmapped_point"
    assert result.missing_input == ["origin_coordinates"]


def test_demo_agent_finding_is_explicitly_simulated() -> None:
    agent = MobilityAgent(
        InMemorySourceRepository(load_fixtures=True),
        otp_client=OtpClient(mode="demo"),
    )
    result = agent.evaluate(route_id="L2")
    assert isinstance(result, Finding)
    assert result.is_simulated is True
    assert result.content["fallback_reason"] == "demo_mode_fixture"
    assert result.content["itineraries_count"] == 1
    assert result.content["estimated_time_min"] == 20


def test_mobility_agent_uses_config_and_maps_no_route_to_refusal(monkeypatch) -> None:
    from app.services.orchestrator.config import load_config

    monkeypatch.setenv("ROUTING_MODE", "demo")
    monkeypatch.setenv("OTP_BASE_URL", "http://otp.example")
    monkeypatch.setenv("OTP_TIMEOUT_S", "2.5")
    monkeypatch.setenv("ROUTING_TIMEZONE", "Europe/Rome")
    config = load_config()
    agent = MobilityAgent(InMemorySourceRepository(load_fixtures=True), config=config)
    assert agent._otp.base_url == "http://otp.example"
    assert agent._otp.timeout_s == 2.5
    assert agent._otp.mode == "demo"
    assert agent._otp.timezone == "Europe/Rome"

    class NoRouteOtp:
        mode = "real"

        def plan_itineraries(self, **kwargs: Any) -> ItineraryPlan:
            raise OtpNoRouteError([{"code": "NO_TRANSIT_CONNECTION"}])

    refusal = MobilityAgent(
        InMemorySourceRepository(load_fixtures=True), otp_client=NoRouteOtp()  # type: ignore[arg-type]
    ).evaluate(
        route_id="L2",
        origin_stop_id="STOP_GAR_01",
        destination_stop_id="STOP_BAG_01",
    )
    assert isinstance(refusal, Refusal)
    assert refusal.reason_code == "no_route"
