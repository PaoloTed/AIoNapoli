"""Unit and API tests for Input Agent, Geocoder, and Route Request endpoint (05_agente_input.md)."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.main import create_app
from app.services.facade import BackendService
from app.services.input.geocoder import Geocoder, is_in_naples_bounds
from app.services.input.parser import RequestParser
from app.utils.clock import FixedClock


def test_bounds_napoli() -> None:
    """Verifica bounds geografici di Napoli (40.75-40.95 lat, 14.10-14.40 lon)."""
    assert is_in_naples_bounds(40.8522, 14.2724)  # Napoli centro
    assert is_in_naples_bounds(40.8135, 14.1634)  # Bagnoli
    assert not is_in_naples_bounds(41.9028, 12.4964)  # Roma
    assert not is_in_naples_bounds(45.4642, 9.1900)  # Milano


def test_geocoder_dizionario() -> None:
    """Risoluzione luoghi da dizionario curato."""
    geo = Geocoder()
    bagnoli = geo.resolve("Bagnoli")
    assert bagnoli is not None
    assert bagnoli.kind == "zone"
    assert round(bagnoli.lat, 2) == 40.81

    mann = geo.resolve("Museo Archeologico")
    assert mann is not None
    assert mann.kind == "poi"
    assert mann.resolved_by == "dictionary"


def test_geocoder_coordinate_esplicite() -> None:
    """Risoluzione coordinate dirette nel testo."""
    geo = Geocoder()
    coord = geo.resolve("40.8135, 14.1634")
    assert coord is not None
    assert coord.kind == "coordinate"
    assert round(coord.lat, 4) == 40.8135
    assert round(coord.lon, 4) == 14.1634


def test_frase_informale_completa() -> None:
    """'portami da Bagnoli al MANN domani alle 15 senza troppi cambi' -> TripRequest valido."""
    now = datetime(2026, 11, 15, 10, 0, tzinfo=timezone.utc)
    parser = RequestParser()
    trip_req, parsed, unresolved, question = parser.parse_request(
        "portami da Bagnoli al MANN domani alle 15 senza troppi cambi",
        now=now,
    )

    assert trip_req is not None
    assert trip_req.origin.label == "Bagnoli"
    assert trip_req.destination.label == "Mann"
    assert trip_req.when.day == 16
    assert trip_req.when.hour == 15
    assert trip_req.constraints.get("max_transfers") == 1
    assert not unresolved
    assert question is None


def test_frase_informale_fuorigrotta_plebiscito() -> None:
    """'da Fuorigrotta a Piazza Plebiscito tra un'ora' -> TripRequest valido."""
    now = datetime(2026, 11, 15, 10, 0, tzinfo=timezone.utc)
    parser = RequestParser()
    trip_req, parsed, unresolved, question = parser.parse_request(
        "da Fuorigrotta a Piazza Plebiscito tra un'ora",
        now=now,
    )

    assert trip_req is not None
    assert trip_req.origin.label == "Fuorigrotta"
    assert "Plebiscito" in trip_req.destination.label
    assert trip_req.when.hour == 11
    assert not unresolved


def test_richiesta_incompleta_produce_chiarimento() -> None:
    """Destinazione sconosciuta produce domanda di chiarimento."""
    parser = RequestParser()
    trip_req, parsed, unresolved, question = parser.parse_request(
        "portami da Bagnoli a quel posto laggiu",
    )

    assert trip_req is None
    assert len(unresolved) >= 1
    assert any(u["field"] == "destination" for u in unresolved)
    assert question == "Quale luogo intendi per la destinazione?"


def test_api_route_request_endpoint() -> None:
    """POST /api/v1/route-request con TestClient."""
    clock = FixedClock(datetime(2026, 11, 15, 10, 0, tzinfo=timezone.utc))
    service = BackendService(clock=clock)
    app = create_app(service=service)

    with TestClient(app) as client:
        # 1. Success case
        res = client.post(
            "/api/v1/route-request",
            json={"text": "portami da Bagnoli al MANN domani alle 15 senza troppi cambi"},
        )
        assert res.status_code == 200
        data = res.json()
        assert data["needs_clarification"] is False
        assert data["trip_request"] is not None
        assert data["trip_request"]["origin"]["label"] == "Bagnoli"
        assert data["trip_request"]["destination"]["label"] == "Mann"

        # 2. Clarification case
        res_clarify = client.post(
            "/api/v1/route-request",
            json={"text": "da Bagnoli a un posto segreto"},
        )
        assert res_clarify.status_code == 200
        data_c = res_clarify.json()
        assert data_c["needs_clarification"] is True
        assert data_c["trip_request"] is None
        assert "destinazione" in data_c["question"].lower()
