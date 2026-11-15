"""Offline regression: exclude the discovered L1 feed-scoped route ID."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Callable
from zoneinfo import ZoneInfo

import httpx

from app.domain.models.finding import Finding
from app.repositories.memory import InMemorySourceRepository
from app.services.agents.mobility.agent import MobilityAgent
from app.services.agents.mobility.otp_client import DEFAULT_MODES, OtpClient

DEPARTURE = datetime(2026, 11, 16, 8, 0, tzinfo=ZoneInfo("Europe/Rome"))
ORIGIN = (40.8943044, 14.2308735)
DESTINATION = (40.8047221, 14.1745403)
ANM = {"gtfsId": "17:ANM", "name": "Azienda Napoletana Mobilità"}
EAV = {"gtfsId": "91:NA0004", "name": "Eav srl - Divisione Ferrovia"}
L1_SCOPED = "17:4955"


def _leg(
    *,
    mode: str,
    start: str,
    end: str,
    from_lat: float,
    from_lon: float,
    to_lat: float,
    to_lon: float,
    transit: bool,
    route_id: str | None = None,
    short_name: str | None = None,
    agency: dict[str, str] | None = None,
    trip_id: str | None = None,
    from_stop: str | None = None,
    to_stop: str | None = None,
) -> dict[str, Any]:
    duration = int((datetime.fromisoformat(end) - datetime.fromisoformat(start)).total_seconds())
    leg: dict[str, Any] = {
        "mode": mode,
        "transitLeg": transit,
        "duration": duration,
        "start": {"scheduledTime": start},
        "end": {"scheduledTime": end},
        "from": {"lat": from_lat, "lon": from_lon},
        "to": {"lat": to_lat, "lon": to_lon},
    }
    if route_id is not None:
        leg["route"] = {
            "gtfsId": route_id,
            "shortName": short_name,
            "longName": short_name,
            "mode": mode,
            "agency": agency,
        }
    if trip_id is not None:
        leg["trip"] = {"gtfsId": trip_id}
    if from_stop is not None:
        leg["from"]["stop"] = {"gtfsId": from_stop}
    if to_stop is not None:
        leg["to"]["stop"] = {"gtfsId": to_stop}
    return leg


def _plan_payload() -> dict[str, Any]:
    """Two usable alternatives: ANM bus C1 and EAV rail 9."""
    return {
        "data": {
            "planConnection": {
                "edges": [
                    {
                        "node": {
                            "start": "2026-11-16T08:00:00+01:00",
                            "end": "2026-11-16T09:00:00+01:00",
                            "duration": 3600,
                            "numberOfTransfers": 1,
                            "legs": [
                                _leg(
                                    mode="WALK",
                                    start="2026-11-16T08:00:00+01:00",
                                    end="2026-11-16T08:10:00+01:00",
                                    from_lat=ORIGIN[0],
                                    from_lon=ORIGIN[1],
                                    to_lat=40.89,
                                    to_lon=14.23,
                                    transit=False,
                                ),
                                _leg(
                                    mode="BUS",
                                    start="2026-11-16T08:10:00+01:00",
                                    end="2026-11-16T08:40:00+01:00",
                                    from_lat=40.89,
                                    from_lon=14.23,
                                    to_lat=40.85,
                                    to_lon=14.20,
                                    transit=True,
                                    route_id="17:3438",
                                    short_name="C1",
                                    agency=ANM,
                                    trip_id="17:388_CodUdp:D600_31932034",
                                    from_stop="17:3419",
                                    to_stop="17:3151",
                                ),
                                _leg(
                                    mode="RAIL",
                                    start="2026-11-16T08:50:00+01:00",
                                    end="2026-11-16T09:00:00+01:00",
                                    from_lat=40.85,
                                    from_lon=14.20,
                                    to_lat=DESTINATION[0],
                                    to_lon=DESTINATION[1],
                                    transit=True,
                                    route_id="91:9",
                                    short_name="9",
                                    agency=EAV,
                                    trip_id="91:90930_opttp2026-2030-9",
                                    from_stop="91:6801",
                                    to_stop="91:6804",
                                ),
                            ],
                        }
                    },
                    {
                        "node": {
                            "start": "2026-11-16T08:05:00+01:00",
                            "end": "2026-11-16T09:10:00+01:00",
                            "duration": 3900,
                            "numberOfTransfers": 0,
                            "legs": [
                                _leg(
                                    mode="BUS",
                                    start="2026-11-16T08:05:00+01:00",
                                    end="2026-11-16T09:10:00+01:00",
                                    from_lat=ORIGIN[0],
                                    from_lon=ORIGIN[1],
                                    to_lat=DESTINATION[0],
                                    to_lon=DESTINATION[1],
                                    transit=True,
                                    route_id="17:4702",
                                    short_name="168",
                                    agency=ANM,
                                    trip_id="17:388_CodUdp:D600_31935113",
                                    from_stop="17:3133",
                                    to_stop="17:2002",
                                )
                            ],
                        }
                    },
                ],
                "routingErrors": [],
            }
        }
    }


def _handler(capture: list[dict[str, Any]]) -> Callable[[httpx.Request], httpx.Response]:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        query = str(payload.get("query") or "")
        if "routes" in query:
            return httpx.Response(
                200,
                json={
                    "data": {
                        "routes": [
                            {
                                "gtfsId": L1_SCOPED,
                                "shortName": "L1",
                                "longName": "Metropolitana Linea 1",
                                "mode": "SUBWAY",
                                "agency": ANM,
                            },
                            {
                                "gtfsId": "91:2",
                                "shortName": "2",
                                "longName": "Napoli - Aversa",
                                "mode": "RAIL",
                                "agency": EAV,
                            },
                        ]
                    }
                },
                request=request,
            )
        capture.append(payload.get("variables") or {})
        return httpx.Response(200, json=_plan_payload(), request=request)

    return handler


def _client(capture: list[dict[str, Any]]) -> OtpClient:
    return OtpClient(
        base_url="http://otp.test",
        timeout_s=1.0,
        http_client=httpx.Client(transport=httpx.MockTransport(_handler(capture))),
    )


def test_l1_closed_has_no_l1_and_at_least_one_alternative() -> None:
    capture: list[dict[str, Any]] = []
    client = _client(capture)

    l1_routes = client.discover_routes(short_name="L1", agency_name="ANM")
    assert [route.scoped_id for route in l1_routes] == [L1_SCOPED]

    plan = client.plan_itineraries(
        from_lat=ORIGIN[0],
        from_lon=ORIGIN[1],
        to_lat=DESTINATION[0],
        to_lon=DESTINATION[1],
        depart_at=DEPARTURE,
        first=10,
        modes=DEFAULT_MODES,
        transit_only=True,
        exclude_route_ids=(l1_routes[0].scoped_id,),
    )

    assert plan.routing_errors == []
    assert len(plan.itineraries) >= 1
    route_ids = [
        leg["route_id"]
        for itinerary in plan.itineraries
        for leg in itinerary.legs
        if leg.get("route_id")
    ]
    assert L1_SCOPED not in route_ids
    assert all(
        leg.get("route_short_name") != "L1"
        for itinerary in plan.itineraries
        for leg in itinerary.legs
    )
    assert set(route_ids) & {"17:3438", "17:4702"}

    assert capture, "la richiesta di piano deve essere stata inviata"
    variables = capture[0]
    assert variables["preferences"] == {
        "transit": {"filters": [{"exclude": [{"routes": [L1_SCOPED]}]}]}
    }
    transit_modes = [item["mode"] for item in variables["modes"]["transit"]["transit"]]
    assert "SUBWAY" in transit_modes


def test_mobility_agent_uses_the_discovered_exclusion() -> None:
    capture: list[dict[str, Any]] = []
    agent = MobilityAgent(
        InMemorySourceRepository(load_fixtures=True),
        otp_client=_client(capture),
    )

    result = agent.evaluate(
        route_id="L2",
        origin_stop_id="STOP_GAR_01",
        destination_stop_id="STOP_BAG_01",
        exclude_route_ids=(L1_SCOPED,),
        now=DEPARTURE,
    )

    assert isinstance(result, Finding)
    assert result.content["itineraries_count"] >= 1
    assert L1_SCOPED not in str(result.content)
    assert "L1" not in str(result.content["recommended_route"])
