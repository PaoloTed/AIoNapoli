"""Feed discovery/mapping tests that never assume a numeric feed ID."""

from __future__ import annotations

import json
from typing import Any, Callable

import httpx
import pytest

from app.services.agents.mobility.gtfs_ids import parse_otp_id
from app.services.agents.mobility.otp_client import OtpClient
from app.services.agents.mobility.otp_graph import map_feeds_to_datasets

DATASETS = [
    {
        "dataset_key": "eav",
        "gtfs_schema": "gtfs_eav",
        "agency_ids": "EAVO,NA0004",
    },
    {
        "dataset_key": "anm",
        "gtfs_schema": "gtfs_anm",
        "agency_ids": "ANM,FS",
    },
]


def _handler(capture: list[dict[str, Any]]) -> Callable[[httpx.Request], httpx.Response]:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        capture.append(payload)
        query = str(payload.get("query") or "")
        if "routes" in query:
            return httpx.Response(
                200,
                json={
                    "data": {
                        "routes": [
                            {
                                "gtfsId": "17:4955",
                                "shortName": "L1",
                                "longName": "Metropolitana Linea 1",
                                "mode": "SUBWAY",
                                "agency": {
                                    "gtfsId": "17:ANM",
                                    "name": "Azienda Napoletana Mobilità",
                                },
                            },
                            {
                                "gtfsId": "17:4778",
                                "shortName": "L2",
                                "longName": "Linea 2",
                                "mode": "RAIL",
                                "agency": {"gtfsId": "17:FS", "name": "Trenitalia"},
                            },
                            {
                                "gtfsId": "91:2",
                                "shortName": "2",
                                "longName": "Napoli - Aversa",
                                "mode": "RAIL",
                                "agency": {"gtfsId": "91:NA0004", "name": "Eav srl"},
                            },
                        ]
                    }
                },
                request=request,
            )
        if "agencies" in query:
            return httpx.Response(
                200,
                json={
                    "data": {
                        "agencies": [
                            {"gtfsId": "17:ANM", "name": "Azienda Napoletana Mobilità"},
                            {"gtfsId": "17:FS", "name": "Trenitalia"},
                            {
                                "gtfsId": "91:NA0004",
                                "name": "Eav srl - Divisione Ferrovia",
                            },
                            {"gtfsId": "91:EAVO", "name": "Eav srl - Divisione Autolinea"},
                        ]
                    }
                },
                request=request,
            )
        raise AssertionError(f"query inattesa: {query}")

    return handler


def _client(capture: list[dict[str, Any]]) -> OtpClient:
    return OtpClient(
        base_url="http://otp.test",
        timeout_s=1.0,
        http_client=httpx.Client(transport=httpx.MockTransport(_handler(capture))),
    )


def test_discovery_uses_short_name_and_agency_not_feed_number() -> None:
    capture: list[dict[str, Any]] = []
    client = _client(capture)
    routes = client.discover_routes(short_name="L1", agency_name="ANM")

    assert len(capture) == 1
    assert [route.scoped_id for route in routes] == ["17:4955"]
    assert routes[0].feed_id == "17"
    assert routes[0].gtfs_id == "4955"
    assert routes[0].agency_id == "ANM"
    assert routes[0].agency_name == "Azienda Napoletana Mobilità"


def test_feed_mapping_is_derived_from_agencies() -> None:
    capture: list[dict[str, Any]] = []
    client = _client(capture)
    feed_agencies = client.discover_feed_agencies()
    mapping = map_feeds_to_datasets(feed_agencies, DATASETS)

    assert mapping == {"17": "anm", "91": "eav"}
    assert mapping["17"] != mapping["91"]
    assert feed_agencies["91"] == {"NA0004", "EAVO"}


def test_ambiguous_feed_is_rejected_instead_of_guessed() -> None:
    with pytest.raises(ValueError, match="ambiguo"):
        map_feeds_to_datasets(
            {"5": {"ANM", "NA0004"}},
            DATASETS,
        )


def test_original_gtfs_ids_remain_available() -> None:
    feed_id, route_id = parse_otp_id("91:388_CodUdp:D600_31943746")
    assert feed_id == "91"
    assert route_id == "388_CodUdp:D600_31943746"
