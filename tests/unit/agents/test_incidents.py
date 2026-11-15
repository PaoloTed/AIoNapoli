"""Unit tests for IncidentsAgent (04_agente_imprevisti.md §8)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.domain.models.routing import (
    LineTarget,
    RouteLeg,
    RouteProposal,
    StopTarget,
    Waypoint,
    ZoneTarget,
)
from app.services.agents.incidents.agent import IncidentsAgent
from app.utils.clock import FixedClock


def _make_proposal(
    routes: tuple[str, ...] = ("151",),
    stops: tuple[str, ...] = ("STOP_GAR_01", "STOP_FUO_01"),
    zones: tuple[str, ...] = ("Z_CENTRO", "Z_FUORIGROTTA"),
    mode: str = "bus",
    departure: datetime | None = None,
    arrival: datetime | None = None,
) -> RouteProposal:
    dep = departure or datetime(2026, 11, 15, 14, 0, tzinfo=timezone.utc)
    arr = arrival or datetime(2026, 11, 15, 14, 30, tzinfo=timezone.utc)
    legs = (
        RouteLeg(
            mode=mode,  # type: ignore[arg-type]
            route_id=routes[0] if routes else None,
            from_stop=stops[0],
            to_stop=stops[1],
            from_stop_id=stops[0],
            to_stop_id=stops[1],
            departure=dep,
            arrival=arr,
            duration_min=30,
            zone_ids=zones,
        ),
    )
    return RouteProposal(
        proposal_id="prop_test",
        origin=Waypoint(
            label="Centro", lat=40.85, lon=14.27, kind="zone", resolved_by="dictionary"
        ),
        destination=Waypoint(
            label="Fuorigrotta", lat=40.82, lon=14.19, kind="zone", resolved_by="dictionary"
        ),
        legs=legs,
        total_duration_min=30,
        transfers=0,
        zone_ids=zones,
        route_ids=routes,
        is_simulated=False,
        source_id="anm",
        data_reference="ref_test",
    )


class MockRepo:
    def __init__(
        self,
        alerts: list[dict[str, Any]] | None = None,
        events: list[dict[str, Any]] | None = None,
        should_raise: bool = False,
    ) -> None:
        self.alerts = alerts if alerts is not None else []
        self.events = events if events is not None else []
        self.should_raise = should_raise

    def get_active_service_alerts(self, now: datetime | None = None) -> list[dict[str, Any]]:
        if self.should_raise:
            raise RuntimeError("Database connection lost")
        return self.alerts

    def get_events(self, zone_id: str | None = None) -> list[dict[str, Any]]:
        if self.should_raise:
            raise RuntimeError("Database connection lost")
        return self.events


def test_fermata_coinvolta() -> None:
    """1. Alert con stop_id nel percorso produce closure su fermata."""
    repo = MockRepo(
        alerts=[
            {
                "alert_id": "AL_STOP_1",
                "stop_id": "STOP_GAR_01",
                "severity": "high",
                "confidence": 0.95,
                "source_id": "anm",
            }
        ]
    )
    agent = IncidentsAgent(repo)  # type: ignore[arg-type]
    prop = _make_proposal(stops=("STOP_GAR_01", "STOP_FUO_01"))

    constraints = agent.validate(prop)
    assert len(constraints) == 1
    assert constraints[0].kind == "closure"
    assert isinstance(constraints[0].target, StopTarget)
    assert constraints[0].target.stop_id == "STOP_GAR_01"


def test_linea_diretta() -> None:
    """2. Alert con route_id produce closure su linea."""
    repo = MockRepo(
        alerts=[
            {
                "alert_id": "AL_ROUTE_151",
                "route_id": "151",
                "severity": "critical",
                "confidence": 0.90,
                "source_id": "anm",
            }
        ]
    )
    agent = IncidentsAgent(repo)  # type: ignore[arg-type]
    prop = _make_proposal(routes=("151",))

    constraints = agent.validate(prop)
    assert len(constraints) == 1
    assert constraints[0].kind == "closure"
    assert isinstance(constraints[0].target, LineTarget)
    assert constraints[0].target.route_id == "151"


def test_zona_condivisa() -> None:
    """3. Alert con zona produce closure su zona."""
    repo = MockRepo(
        alerts=[
            {
                "alert_id": "AL_ZONE_FUO",
                "zone_id": "Z_FUORIGROTTA",
                "severity": "high",
                "confidence": 0.80,
                "source_id": "anm",
            }
        ]
    )
    agent = IncidentsAgent(repo)  # type: ignore[arg-type]
    prop = _make_proposal(zones=("Z_CENTRO", "Z_FUORIGROTTA"))

    constraints = agent.validate(prop)
    assert len(constraints) == 1
    assert constraints[0].kind == "closure"
    assert isinstance(constraints[0].target, ZoneTarget)
    assert constraints[0].target.zone_id == "Z_FUORIGROTTA"


def test_evento_produce_penalita() -> None:
    """4. Evento attivo in zona produce penalty, NON closure (04_agente_imprevisti.md §5.1)."""
    now = datetime(2026, 11, 15, 14, 0, tzinfo=timezone.utc)
    repo = MockRepo(
        events=[
            {
                "event_id": "EV_MARADONA_MATCH",
                "zone_id": "Z_FUORIGROTTA",
                "expected_attendance": 55000,
                "start_time": "2026-11-15T12:00:00+00:00",
                "end_time": "2026-11-15T18:00:00+00:00",
            }
        ]
    )
    agent = IncidentsAgent(repo, clock=FixedClock(now))  # type: ignore[arg-type]
    prop = _make_proposal(zones=("Z_FUORIGROTTA",))

    constraints = agent.validate(prop)
    assert len(constraints) == 1
    assert constraints[0].kind == "penalty"
    assert isinstance(constraints[0].target, ZoneTarget)
    assert constraints[0].target.zone_id == "Z_FUORIGROTTA"
    assert constraints[0].confidence == 0.75


def test_evento_fuori_finestra() -> None:
    """5. Evento in zona ma fuori finestra non produce vincoli."""
    now = datetime(2026, 11, 15, 14, 0, tzinfo=timezone.utc)
    repo = MockRepo(
        events=[
            {
                "event_id": "EV_CONCERT_YESTERDAY",
                "zone_id": "Z_FUORIGROTTA",
                "expected_attendance": 20000,
                "start_time": "2026-11-14T12:00:00+00:00",
                "end_time": "2026-11-14T18:00:00+00:00",
            }
        ]
    )
    agent = IncidentsAgent(repo, clock=FixedClock(now))  # type: ignore[arg-type]
    prop = _make_proposal(
        zones=("Z_FUORIGROTTA",),
        departure=now,
        arrival=datetime(2026, 11, 15, 14, 30, tzinfo=timezone.utc),
    )

    constraints = agent.validate(prop)
    assert len(constraints) == 0


def test_sciopero_bus_non_colpisce_metro() -> None:
    """6. Sciopero con route_type incompatibile non produce vincoli."""
    repo = MockRepo(
        alerts=[
            {
                "alert_id": "STRIKE_BUS",
                "route_type": "bus",
                "route_id": "LINEA_1",
                "confidence": 0.85,
            }
        ]
    )
    agent = IncidentsAgent(repo)  # type: ignore[arg-type]
    # Proposal uses metro mode, not bus
    prop = _make_proposal(routes=("LINEA_1",), mode="metro")

    constraints = agent.validate(prop)
    assert len(constraints) == 0


def test_fonte_vecchia_incerta() -> None:
    """7. Alert oltre la soglia di freschezza produce uncertainty."""
    now = datetime(2026, 11, 15, 14, 0, tzinfo=timezone.utc)
    old_date = datetime(2026, 11, 1, 10, 0, tzinfo=timezone.utc)  # 14 days old (> 7 days)
    repo = MockRepo(
        alerts=[
            {
                "alert_id": "AL_STALE",
                "route_id": "151",
                "valid_from": old_date.isoformat(),
                "confidence": 0.85,
            }
        ]
    )
    agent = IncidentsAgent(repo, clock=FixedClock(now))  # type: ignore[arg-type]
    prop = _make_proposal(routes=("151",))

    constraints = agent.validate(prop)
    assert len(constraints) == 1
    assert constraints[0].kind == "uncertainty"
    assert constraints[0].confidence == 0.30


def test_nessun_dato() -> None:
    """8. Tabelle vuote producono un solo vincolo uncertainty con motivo."""
    repo = MockRepo(alerts=[], events=[])
    agent = IncidentsAgent(repo)  # type: ignore[arg-type]
    prop = _make_proposal()

    constraints = agent.validate(prop)
    assert len(constraints) == 1
    assert constraints[0].kind == "uncertainty"
    assert constraints[0].confidence == 0.30
    assert constraints[0].evidence_ref == "no_data_available"


def test_ordinamento_vincoli() -> None:
    """9. I vincoli sono ordinati per confidenza decrescente."""
    repo = MockRepo(
        alerts=[
            {"alert_id": "AL_LOW", "route_id": "151", "confidence": 0.6},
            {"alert_id": "AL_HIGH", "stop_id": "STOP_GAR_01", "confidence": 0.95},
        ]
    )
    agent = IncidentsAgent(repo)  # type: ignore[arg-type]
    prop = _make_proposal(routes=("151",), stops=("STOP_GAR_01", "STOP_FUO_01"))

    constraints = agent.validate(prop)
    assert len(constraints) == 2
    assert constraints[0].confidence >= constraints[1].confidence
    assert constraints[0].evidence_ref == "AL_HIGH"


def test_determinismo_vincoli() -> None:
    """10. Stesso input, due chiamate, stessa lista."""
    repo = MockRepo(
        alerts=[
            {"alert_id": "AL_1", "route_id": "151", "confidence": 0.90},
            {"alert_id": "AL_2", "stop_id": "STOP_GAR_01", "confidence": 0.95},
        ]
    )
    agent = IncidentsAgent(repo)  # type: ignore[arg-type]
    prop = _make_proposal(routes=("151",), stops=("STOP_GAR_01", "STOP_FUO_01"))

    c1 = agent.validate(prop)
    c2 = agent.validate(prop)
    assert c1 == c2


def test_nessuna_eccezione() -> None:
    """11. Repository che solleva produce uncertainty, mai eccezione."""
    repo = MockRepo(should_raise=True)
    agent = IncidentsAgent(repo)  # type: ignore[arg-type]
    prop = _make_proposal()

    constraints = agent.validate(prop)
    assert len(constraints) == 1
    assert constraints[0].kind == "uncertainty"
    assert constraints[0].evidence_ref == "repo_error"


def test_massimo_dieci() -> None:
    """12. Con 12 ostacoli restituisce solo i 10 più confidenti."""
    alerts = [
        {"alert_id": f"AL_{i:02d}", "route_id": "151", "confidence": 0.5 + (i * 0.03)}
        for i in range(15)
    ]
    repo = MockRepo(alerts=alerts)
    agent = IncidentsAgent(repo)  # type: ignore[arg-type]
    prop = _make_proposal(routes=("151",))

    constraints = agent.validate(prop)
    assert len(constraints) == 10
    # First is highest confidence
    assert constraints[0].evidence_ref == "AL_14"
