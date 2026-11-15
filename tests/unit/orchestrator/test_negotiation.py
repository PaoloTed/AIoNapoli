"""Unit tests for the negotiation cycle (03_ciclo_negoziazione.md §11)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Sequence

import pytest

from app.domain.models.routing import (
    LineTarget,
    RouteLeg,
    RouteProposal,
    SegmentTarget,
    TimeWindow,
    TravelConstraint,
    Waypoint,
    ZoneTarget,
)
from app.domain.models.trace import Trace
from app.domain.models.trip_request import TripLocation, TripRequest
from app.services.orchestrator.negotiation import (
    NoRouteAvailable,
    negotiate,
    post_filter_proposals,
)


def _make_dummy_request() -> TripRequest:
    return TripRequest(
        origin=TripLocation(
            label="Bagnoli",
            lat=40.8135,
            lon=14.1634,
            kind="zone",
            resolved_by="dictionary",
        ),
        destination=TripLocation(
            label="Centro",
            lat=40.8522,
            lon=14.2724,
            kind="zone",
            resolved_by="dictionary",
        ),
        when=datetime(2026, 11, 15, 14, 0, tzinfo=timezone.utc),
    )


def _make_dummy_proposal(
    proposal_id: str,
    routes: tuple[str, ...] = ("151",),
    stops: tuple[str, ...] = ("STOP_A", "STOP_B"),
    duration_min: int = 30,
    headsign: str | None = None,
    start_hour: int = 14,
) -> RouteProposal:
    departure = datetime(2026, 11, 15, start_hour, 0, tzinfo=timezone.utc)
    arrival = datetime(2026, 11, 15, start_hour, duration_min, tzinfo=timezone.utc)
    legs = (
        RouteLeg(
            mode="bus",
            route_id=routes[0] if routes else None,
            from_stop=stops[0],
            to_stop=stops[1] if len(stops) > 1 else stops[0],
            from_stop_id=stops[0],
            to_stop_id=stops[1] if len(stops) > 1 else stops[0],
            departure=departure,
            arrival=arrival,
            duration_min=duration_min,
            zone_ids=("Z_BAGNOLI", "Z_CENTRO"),
            headsign=headsign,
        ),
    )
    return RouteProposal(
        proposal_id=proposal_id,
        origin=Waypoint(
            label="Bagnoli",
            lat=40.8135,
            lon=14.1634,
            kind="zone",
            resolved_by="dictionary",
        ),
        destination=Waypoint(
            label="Centro",
            lat=40.8522,
            lon=14.2724,
            kind="zone",
            resolved_by="dictionary",
        ),
        legs=legs,
        total_duration_min=duration_min,
        transfers=0,
        zone_ids=("Z_BAGNOLI", "Z_CENTRO"),
        route_ids=routes,
        is_simulated=False,
        source_id="anm",
        data_reference="ref_test",
    )


class MockPlanner:
    def __init__(self, proposal_sequence: Sequence[list[RouteProposal]]) -> None:
        self.proposal_sequence = list(proposal_sequence)
        self.call_count = 0
        self.received_constraints: list[Sequence[TravelConstraint]] = []

    def plan(
        self,
        request: TripRequest,
        constraints: Sequence[TravelConstraint],
        num_itineraries: int = 12,
    ) -> list[RouteProposal]:
        self.call_count += 1
        self.received_constraints.append(constraints)
        if self.proposal_sequence:
            return self.proposal_sequence.pop(0)
        return []


class MockValidator:
    def __init__(self, feedback_sequence: Sequence[list[TravelConstraint]]) -> None:
        self.feedback_sequence = list(feedback_sequence)
        self.call_count = 0

    def validate(self, proposal: RouteProposal, ctx: Any = None) -> list[TravelConstraint]:
        self.call_count += 1
        if self.feedback_sequence:
            return self.feedback_sequence.pop(0)
        return []


def test_valido_al_primo_giro() -> None:
    """1. Nessun vincolo, un solo giro."""
    p1 = _make_dummy_proposal("prop_1")
    planner = MockPlanner([[p1]])
    validator = MockValidator([[]])
    trace = Trace()

    outcome = negotiate(_make_dummy_request(), planner, validator, trace=trace)

    assert outcome.iterations == 1
    assert outcome.final_proposal.proposal_id == "prop_1"
    assert not outcome.exhausted
    assert not outcome.rejected
    assert planner.call_count == 1
    assert validator.call_count == 1


def test_chiusura_poi_valido() -> None:
    """2. Un closure, secondo giro valido, iterations=2."""
    p1 = _make_dummy_proposal("prop_1", routes=("151",))
    p2 = _make_dummy_proposal("prop_2", routes=("CUMANA",))
    planner = MockPlanner([[p1], [p2]])

    closure = TravelConstraint(
        kind="closure",
        target=LineTarget(route_id="151"),
        evidence_ref="alert_151",
        source_id="anm",
        confidence=0.9,
    )
    validator = MockValidator([[closure], []])
    trace = Trace()

    outcome = negotiate(_make_dummy_request(), planner, validator, trace=trace)

    assert outcome.iterations == 2
    assert outcome.final_proposal.proposal_id == "prop_2"
    assert len(outcome.rejected) == 1
    assert outcome.rejected[0].proposal_id == "prop_1"
    assert not outcome.exhausted
    assert "alert_151" in outcome.constraints_applied


def test_penalita_non_ricalcola() -> None:
    """3. Un penalty non produce un secondo giro: la proposta resta valida."""
    p1 = _make_dummy_proposal("prop_1")
    planner = MockPlanner([[p1]])

    penalty = TravelConstraint(
        kind="penalty",
        target=ZoneTarget(zone_id="Z_BAGNOLI"),
        evidence_ref="event_surge",
        source_id="events",
        confidence=0.75,
    )
    validator = MockValidator([[penalty]])

    outcome = negotiate(_make_dummy_request(), planner, validator)

    assert outcome.iterations == 1
    assert outcome.final_proposal.proposal_id == "prop_1"
    assert outcome.final_proposal.penalty_applied is True
    assert not outcome.exhausted
    assert len(outcome.rejected) == 0


def test_penalita_ordina_dopo() -> None:
    """4. Una proposta penalizzata resta nei candidati ma ordinata dopo quelle senza."""
    p_unpenalized = _make_dummy_proposal("prop_free", routes=("R7",))
    p_penalized = _make_dummy_proposal("prop_heavy", routes=("151",))

    penalty = TravelConstraint(
        kind="penalty",
        target=LineTarget(route_id="151"),
        applies_at="post_filter",
        evidence_ref="crowd_151",
        source_id="crowding",
        confidence=0.8,
    )

    # Put penalized first in input list
    ordered = post_filter_proposals([p_penalized, p_unpenalized], [penalty])

    # Unpenalized must emerge first
    assert len(ordered) == 2
    assert ordered[0].proposal_id == "prop_free"
    assert ordered[1].proposal_id == "prop_heavy"
    assert ordered[1].penalty_applied is True


def test_vincoli_noti_precaricati() -> None:
    """5. I vincoli noti arrivano al primo calcolo: un solo giro invece di due."""
    p_cumana = _make_dummy_proposal("prop_cumana", routes=("CUMANA",))
    planner = MockPlanner([[p_cumana]])
    validator = MockValidator([[]])

    known = [
        TravelConstraint(
            kind="closure",
            target=LineTarget(route_id="LINEA_2"),
            evidence_ref="alert_l2",
            source_id="anm",
            confidence=0.95,
        )
    ]

    outcome = negotiate(
        _make_dummy_request(),
        planner,
        validator,
        known_constraints=known,
    )

    assert outcome.iterations == 1
    assert planner.call_count == 1
    # Check that known constraint was passed to the planner on first call
    assert any(
        getattr(c.target, "route_id", "") == "LINEA_2" for c in planner.received_constraints[0]
    )


def test_max_giri_raggiunto() -> None:
    """6. Tre chiusure con max 3, exhausted=true."""
    p1 = _make_dummy_proposal("prop_1", routes=("R1",))
    p2 = _make_dummy_proposal("prop_2", routes=("R2",))
    p3 = _make_dummy_proposal("prop_3", routes=("R3",))
    planner = MockPlanner([[p1], [p2], [p3]])

    c1 = TravelConstraint(
        kind="closure",
        target=LineTarget(route_id="R1"),
        evidence_ref="ref_1",
        source_id="anm",
        confidence=0.9,
    )
    c2 = TravelConstraint(
        kind="closure",
        target=LineTarget(route_id="R2"),
        evidence_ref="ref_2",
        source_id="anm",
        confidence=0.9,
    )
    c3 = TravelConstraint(
        kind="closure",
        target=LineTarget(route_id="R3"),
        evidence_ref="ref_3",
        source_id="anm",
        confidence=0.9,
    )
    validator = MockValidator([[c1], [c2], [c3]])

    outcome = negotiate(
        _make_dummy_request(),
        planner,
        validator,
        max_iterations=3,
    )

    assert outcome.iterations == 3
    assert outcome.exhausted is True
    assert len(outcome.rejected) == 3


def test_proposta_identica() -> None:
    """7. Agente ripropone la stessa soluzione, uscita no_progress (exhausted=true)."""
    p1 = _make_dummy_proposal("prop_same", routes=("151",))
    p2 = _make_dummy_proposal("prop_same_again", routes=("151",))  # Same route and stops!
    planner = MockPlanner([[p1], [p2]])

    c1 = TravelConstraint(
        kind="closure",
        target=LineTarget(route_id="151"),
        evidence_ref="ref_dup",
        source_id="anm",
        confidence=0.9,
    )
    validator = MockValidator([[c1], [c1]])

    outcome = negotiate(_make_dummy_request(), planner, validator)

    assert outcome.exhausted is True
    assert outcome.iterations == 2


def test_nessuna_rotta() -> None:
    """8. NoRouteAvailable porta a exhausted=true."""
    planner = MockPlanner([[]])
    validator = MockValidator([])

    with pytest.raises(NoRouteAvailable):
        negotiate(_make_dummy_request(), planner, validator)


def test_uncertain_accettato() -> None:
    """9. Un solo uncertainty, percorso accettato ma contrassegnato incerto."""
    p1 = _make_dummy_proposal("prop_1")
    planner = MockPlanner([[p1]])

    uncertain = TravelConstraint(
        kind="uncertainty",
        target=ZoneTarget(zone_id="Z_BAGNOLI"),
        evidence_ref="stale_feed",
        source_id="rss",
        confidence=0.3,
    )
    validator = MockValidator([[uncertain]])

    outcome = negotiate(_make_dummy_request(), planner, validator)

    assert outcome.iterations == 1
    assert outcome.uncertain is True
    assert not outcome.exhausted


def test_determinismo_ciclo() -> None:
    """10. Due esecuzioni identiche producono la stessa sequenza e lo stesso output."""
    req = _make_dummy_request()
    c = TravelConstraint(
        kind="closure",
        target=LineTarget(route_id="151"),
        evidence_ref="alert_151",
        source_id="anm",
        confidence=0.9,
    )

    p1_a = _make_dummy_proposal("p1", routes=("151",))
    p2_a = _make_dummy_proposal("p2", routes=("CUMANA",))
    p1_b = _make_dummy_proposal("p1", routes=("151",))
    p2_b = _make_dummy_proposal("p2", routes=("CUMANA",))

    out1 = negotiate(req, MockPlanner([[p1_a], [p2_a]]), MockValidator([[c], []]))
    out2 = negotiate(req, MockPlanner([[p1_b], [p2_b]]), MockValidator([[c], []]))

    assert out1.iterations == out2.iterations
    assert out1.constraints_applied == out2.constraints_applied
    assert out1.final_proposal.proposal_id == out2.final_proposal.proposal_id


def test_esclusioni_ordinate() -> None:
    """11. I vincoli applicati sono ordinati alfabeticamente."""
    p1 = _make_dummy_proposal("p1", routes=("151",))
    p2 = _make_dummy_proposal("p2", routes=("CUMANA",))
    planner = MockPlanner([[p1], [p2]])

    c_z = TravelConstraint(
        kind="closure",
        target=LineTarget(route_id="Z"),
        evidence_ref="Z_ref",
        source_id="s",
        confidence=0.9,
    )
    c_a = TravelConstraint(
        kind="closure",
        target=LineTarget(route_id="A"),
        evidence_ref="A_ref",
        source_id="s",
        confidence=0.9,
    )
    validator = MockValidator([[c_z, c_a], []])

    outcome = negotiate(_make_dummy_request(), planner, validator)

    assert list(outcome.constraints_applied) == sorted(outcome.constraints_applied)


def test_log_contiguo() -> None:
    """12. Gli eventi di trace emessi hanno seq contiguo da 1."""
    p1 = _make_dummy_proposal("p1", routes=("151",))
    p2 = _make_dummy_proposal("p2", routes=("CUMANA",))
    closure = TravelConstraint(
        kind="closure",
        target=LineTarget(route_id="151"),
        evidence_ref="ref1",
        source_id="s",
        confidence=0.9,
    )

    trace = Trace()
    negotiate(
        _make_dummy_request(),
        MockPlanner([[p1], [p2]]),
        MockValidator([[closure], []]),
        trace=trace,
    )

    assert len(trace.events) >= 3
    seqs = [e.seq for e in trace.events]
    assert seqs == list(range(1, len(trace.events) + 1))


def test_filtro_finestra() -> None:
    """13. Un vincolo con finestra temporale parziale scarta solo la gamba sovrapposta."""
    p_14h = _make_dummy_proposal("p_14h", start_hour=14)
    p_18h = _make_dummy_proposal("p_18h", start_hour=18)

    window_14_15 = TimeWindow(
        from_at=datetime(2026, 11, 15, 13, 30, tzinfo=timezone.utc),
        to_at=datetime(2026, 11, 15, 15, 0, tzinfo=timezone.utc),
    )
    constraint = TravelConstraint(
        kind="closure",
        target=LineTarget(route_id="151"),
        window=window_14_15,
        applies_at="post_filter",
        evidence_ref="win_closure",
        source_id="anm",
        confidence=0.9,
    )

    filtered = post_filter_proposals([p_14h, p_18h], [constraint])
    assert len(filtered) == 1
    assert filtered[0].proposal_id == "p_18h"


def test_filtro_direzione() -> None:
    """14. Un vincolo per direzione scarta solo quella direzione."""
    p_in = _make_dummy_proposal("p_in", headsign="Centro - Garibaldi")
    p_out = _make_dummy_proposal("p_out", headsign="Pozzuoli - Bagnoli")

    c_inbound = TravelConstraint(
        kind="closure",
        target=LineTarget(route_id="151"),
        direction="inbound",
        applies_at="post_filter",
        evidence_ref="dir_closure",
        source_id="anm",
        confidence=0.9,
    )

    filtered = post_filter_proposals([p_in, p_out], [c_inbound])
    assert len(filtered) == 1
    assert filtered[0].proposal_id == "p_out"


def test_filtro_segmento() -> None:
    """15. Vincolo segmento tra fermata A e B."""
    p_segment_hit = _make_dummy_proposal("p_hit", stops=("STOP_COROGLIO_1", "STOP_COROGLIO_2"))
    p_segment_safe = _make_dummy_proposal("p_safe", stops=("STOP_FUO_1", "STOP_FUO_2"))

    c_segment = TravelConstraint(
        kind="closure",
        target=SegmentTarget(
            route_id="151", from_stop="STOP_COROGLIO_1", to_stop="STOP_COROGLIO_2"
        ),
        applies_at="post_filter",
        evidence_ref="seg_closure",
        source_id="anm",
        confidence=0.9,
    )

    filtered = post_filter_proposals([p_segment_hit, p_segment_safe], [c_segment])
    assert len(filtered) == 1
    assert filtered[0].proposal_id == "p_safe"
