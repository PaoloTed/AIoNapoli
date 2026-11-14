"""Unit tests for the OTP client corrections (ricerche/ricerca2/03b).

Each test pins one of the seven defects fixed in ``otp_client.py``. The point of
the file is to make the defects impossible to reintroduce silently.
"""

from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from app.services.agents.mobility.itineraries import RouteLeg, format_legs_summary
from app.services.agents.mobility.otp_client import (
    DEFAULT_ENDPOINT_PATH,
    ItineraryResult,
    OtpClient,
    OtpMalformedResponse,
    build_query,
    normalise_leg,
)

ENDPOINT = "http://otp.test:8080"


def _omni_handler(response_body: Any) -> tuple[httpx.Client, list[dict[str, Any]]]:
    """Build a client that records every request body and replays one response."""
    seen: list[dict[str, Any]] = []

    def _handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content.decode("utf-8")))
        return httpx.Response(200, json=response_body)

    return httpx.Client(transport=httpx.MockTransport(_handler)), seen


def _itinerary(duration: int, route: str, from_stop: str, to_stop: str) -> dict[str, Any]:
    return {
        "duration": duration,
        "walkDistance": 120.0,
        "startTime": "2026-11-14T16:40:00+01:00",
        "legs": [
            {
                "mode": "BUS",
                "duration": duration - 60,
                "startTime": "2026-11-14T16:40:00+01:00",
                "headsign": "Bagnoli",
                "route": {"shortName": route},
                "from": {"name": "A", "lat": 40.85, "lon": 14.27, "stop": {"gtfsId": from_stop}},
                "to": {"name": "B", "lat": 40.82, "lon": 14.19, "stop": {"gtfsId": to_stop}},
            }
        ],
    }


TWO_ITINERARIES = {
    "data": {
        "plan": {
            "itineraries": [
                _itinerary(1200, "151", "STOP_GAR_01", "STOP_FUI_01"),
                _itinerary(1500, "R7", "STOP_GAR_02", "STOP_BAG_01"),
                _itinerary(1800, "CUMANA", "STOP_FUI_01", "STOP_BAG_01"),
            ]
        }
    }
}


# --- difetto 1: endpoint ---------------------------------------------------


def test_endpoint_predefinito() -> None:
    """OTP 2.x serves the GTFS GraphQL API at /otp/gtfs/v1, not the 1.x router path."""
    assert DEFAULT_ENDPOINT_PATH == "/otp/gtfs/v1"
    assert OtpClient(base_url=ENDPOINT).endpoint == f"{ENDPOINT}/otp/gtfs/v1"


def test_endpoint_configurabile() -> None:
    """A deployment with a different router must not need a code change."""
    client = OtpClient(base_url=ENDPOINT, endpoint_path="otp/routers/default/index/graphql")
    assert client.endpoint == f"{ENDPOINT}/otp/routers/default/index/graphql"


# --- difetto 2: la query chiede le fermate ---------------------------------


def test_query_chiede_le_fermate() -> None:
    """Without stop.gtfsId no constraint on segment or direction is expressible."""
    query = build_query(
        with_modes=False, with_banned=False, with_unpreferred=False, with_start_time=False
    )
    assert "stop { gtfsId }" in query
    assert "headsign" in query
    assert "shortName" in query


def test_query_senza_banned_non_menziona_il_tipo() -> None:
    """A wrong input type name invalidates the document: omit it when unused."""
    query = build_query(
        with_modes=False, with_banned=False, with_unpreferred=False, with_start_time=False
    )
    assert "InputBanned" not in query
    assert "InputUnpreferred" not in query


# --- difetto 3: gambe normalizzate -----------------------------------------


def test_gamba_normalizzata_legge_le_fermate() -> None:
    """The stop identifiers survive normalisation; a raw dict would lose them."""
    leg = normalise_leg(TWO_ITINERARIES["data"]["plan"]["itineraries"][0]["legs"][0])
    assert isinstance(leg, RouteLeg)
    assert leg.from_stop_id == "STOP_GAR_01"
    assert leg.to_stop_id == "STOP_FUI_01"
    assert leg.route == "151"
    assert leg.headsign == "Bagnoli"


def test_gamba_normalizzata_accetta_la_fixture_legacy() -> None:
    """The recorded fixture stores the line as a bare string and the stop as stopId."""
    leg = normalise_leg(
        {
            "mode": "BUS",
            "route": "151",
            "stopId": "ignored",
            "from": {"name": "Piazza Garibaldi", "stopId": "STOP_GAR_01"},
            "to": {"name": "Campi Flegrei", "stopId": "STOP_FUO_01"},
            "duration": 900,
        }
    )
    assert leg.route == "151"
    assert leg.from_stop_id == "STOP_GAR_01"
    assert leg.duration_s == 900


def test_sintesi_delle_gambe() -> None:
    """The route label used in the finding keeps working with typed legs."""
    leg = RouteLeg(mode="BUS", route="151", duration_s=900)
    assert format_legs_summary([leg]) == "BUS 151"


# --- difetto 4: banned e unpreferred --------------------------------------


def test_banned_passato_al_motore() -> None:
    """A closure must reach the engine, otherwise it can only be filtered downstream."""
    client, seen = _omni_handler(TWO_ITINERARIES)
    otp = OtpClient(base_url=ENDPOINT, http_client=client)
    otp.plan_itinerary(
        from_lat=40.85,
        from_lon=14.27,
        to_lat=40.82,
        to_lon=14.19,
        banned={"routes": ["ANM:R7"]},
    )
    assert seen[0]["variables"]["banned"] == {"routes": ["ANM:R7"]}
    assert "banned: $banned" in seen[0]["query"]
    assert "$banned: InputBanned" in seen[0]["query"]


def test_unpreferred_passato_al_motore() -> None:
    """A penalty reorders instead of excluding, so it needs its own argument."""
    client, seen = _omni_handler(TWO_ITINERARIES)
    otp = OtpClient(base_url=ENDPOINT, http_client=client)
    otp.plan_itinerary(
        from_lat=40.85,
        from_lon=14.27,
        to_lat=40.82,
        to_lon=14.19,
        unpreferred={"routes": ["ANM:R7"]},
        unpreferred_cost="0s + 3.0 t",
    )
    assert seen[0]["variables"]["unpreferred"] == {"routes": ["ANM:R7"]}
    assert seen[0]["variables"]["unpreferredCost"] == "0s + 3.0 t"


def test_num_itineraries_inoltrato() -> None:
    """The engine default is 50; the cycle decides how many it needs."""
    client, seen = _omni_handler(TWO_ITINERARIES)
    otp = OtpClient(base_url=ENDPOINT, http_client=client)
    otp.plan_itinerary(
        from_lat=40.85, from_lon=14.27, to_lat=40.82, to_lon=14.19, num_itineraries=50
    )
    assert seen[0]["variables"]["numItineraries"] == 50


# --- difetto 5: tutti gli itinerari ---------------------------------------


def test_restituisce_tutti_gli_itinerari() -> None:
    """Keeping only itineraries[0] made banning useless: there was nothing left to choose."""
    client, _ = _omni_handler(TWO_ITINERARIES)
    otp = OtpClient(base_url=ENDPOINT, http_client=client)
    result = otp.plan_itinerary(from_lat=40.85, from_lon=14.27, to_lat=40.82, to_lon=14.19)
    assert isinstance(result, ItineraryResult)
    assert len(result.proposals) == 3
    assert [p.duration_min for p in result.proposals] == [20, 25, 30]
    assert result.duration_min == 20
    assert result.is_simulated is False


# --- difetto 6: nessuna coordinata di default -----------------------------


def test_coordinate_obbligatorie() -> None:
    """An implicit waypoint would silently route the wrong trip."""
    client, _ = _omni_handler(TWO_ITINERARIES)
    otp = OtpClient(base_url=ENDPOINT, http_client=client)
    with pytest.raises(TypeError):
        otp.plan_itinerary(to_lat=40.82, to_lon=14.19)  # type: ignore[call-arg]


# --- difetto 7: eccezioni distinte ----------------------------------------


def test_motore_irraggiungibile_attiva_la_fixture() -> None:
    """A refused connection is unavailability: the demo degrades and declares it."""

    def _refuse(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("OTP offline", request=request)

    client = httpx.Client(transport=httpx.MockTransport(_refuse))
    otp = OtpClient(base_url=ENDPOINT, http_client=client)
    result = otp.plan_itinerary(from_lat=40.85, from_lon=14.27, to_lat=40.82, to_lon=14.19)
    assert result.is_simulated is True
    assert result.source_id == "otp_fixture"
    assert result.fallback_reason and result.fallback_reason.startswith("otp_non_disponibile")


def test_endpoint_sbagliato_non_e_un_errore_fatale() -> None:
    """A 404 almost always means a wrong endpoint, and must still fall back."""
    client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(404)))
    otp = OtpClient(base_url=ENDPOINT, http_client=client)
    result = otp.plan_itinerary(from_lat=40.85, from_lon=14.27, to_lat=40.82, to_lon=14.19)
    assert result.is_simulated is True
    assert "endpoint_non_trovato" in (result.fallback_reason or "")


def test_risposta_malformata_attiva_la_fixture() -> None:
    """A GraphQL error block is a shape problem, not a crash."""
    body = {"errors": [{"message": "Unknown argument banned"}]}
    client, _ = _omni_handler(body)
    otp = OtpClient(base_url=ENDPOINT, http_client=client)
    result = otp.plan_itinerary(from_lat=40.85, from_lon=14.27, to_lat=40.82, to_lon=14.19)
    assert result.is_simulated is True
    assert "graphql_errors" in (result.fallback_reason or "")


def test_errore_di_programmazione_non_diventa_fallback() -> None:
    """A bug in this module must surface: silently marking data as simulated hides it."""

    def _handler(request: httpx.Request) -> httpx.Response:
        # ``legs`` is a string, not a list: normalisation will try to iterate it.
        return httpx.Response(200, json={"data": {"plan": {"itineraries": [{"legs": 42}]}}})

    client = httpx.Client(transport=httpx.MockTransport(_handler))
    otp = OtpClient(base_url=ENDPOINT, http_client=client)
    with pytest.raises(TypeError):
        otp.plan_itinerary(from_lat=40.85, from_lon=14.27, to_lat=40.82, to_lon=14.19)


def test_decode_segnala_la_forma_sbagliata() -> None:
    """``OtpMalformedResponse`` is raised by us, so it is a declared outcome."""
    from app.services.agents.mobility.otp_client import _decode

    with pytest.raises(OtpMalformedResponse):
        _decode({"data": {"plan": {"itineraries": []}}})
