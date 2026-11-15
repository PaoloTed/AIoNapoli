"""Unit tests for agent registry, blackboard, and supervisors (02_architettura_agentica.md)."""

from __future__ import annotations

from datetime import datetime, timezone

from app.domain.models.finding import AgentName, Finding
from app.domain.models.routing import (
    NegotiationOutcome,
    RouteLeg,
    RouteProposal,
    Waypoint,
)
from app.domain.models.trace import Trace
from app.services.agents.base import AgentCapability, AgentOutcome, RunContext
from app.services.agents.blackboard import Blackboard
from app.services.agents.context.supervisor import ContextSupervisor
from app.services.agents.crowding.supervisor import CrowdingSupervisor
from app.services.agents.mobility.supervisor import MobilitySupervisor
from app.services.agents.registry import load_registry
from app.services.orchestrator.run_supervisor import RunSupervisor
from app.utils.clock import FixedClock


class FakeRepo:
    def get_routes(self) -> list[dict]:
        return [{"route_id": "151"}]

    def get_stops(self, zone_id: str | None = None) -> list[dict]:
        return [{"stop_id": "STOP_GAR_01"}]

    def get_active_service_alerts(self, now: datetime | None = None) -> list[dict]:
        return [{"alert_id": "A1", "source_id": "anm", "severity": "medium", "confidence": 0.85}]

    def get_events(self, zone_id: str | None = None) -> list[dict]:
        return [
            {
                "event_id": "E1",
                "expected_attendance": 12000,
                "window_start": "2026-11-15T10:00:00Z",
                "window_end": "2026-11-15T20:00:00Z",
            }
        ]

    def get_latest_weather(self, zone_id: str | None = None) -> list[dict]:
        return [{"alert_level": "gialla", "precipitation_mm": 5.0, "data_reference": "meteo"}]

    def get_latest_occupancy(self, line: str | None = None) -> list[dict]:
        return [{"occupancy_pct": 72.0, "data_reference": "occ"}]

    def get_fresh_vehicle_positions(
        self, now: datetime, max_age_s: int = 90, route_id: str | None = None
    ) -> list[dict]:
        return [{"vehicle_id": "V1", "data_reference": "gps"}]

    def get_latest_trip_updates(self, route_id: str | None = None) -> list[dict]:
        return []


def test_registry_validation() -> None:
    """Caricamento e validazione del file registry.yaml."""
    reg = load_registry()
    assert reg.version == 1
    assert reg.order == ["mobility", "crowding", "context"]
    assert "mobility" in reg.agents
    assert "crowding" in reg.agents
    assert "context" in reg.agents


def test_blackboard_determinismo() -> None:
    """Il blackboard sovrascrive solo se confidence è strettamente maggiore."""
    bb = Blackboard(run_id="run_1")

    o1 = AgentOutcome(agent="worker_a", contributed=True, confidence=0.7, data={"val": 1})
    bb.put(o1)
    assert bb.value("worker_a", "val") == 1

    # Equal confidence -> keeps existing (deterministic first-in-order)
    o2 = AgentOutcome(agent="worker_a", contributed=True, confidence=0.7, data={"val": 2})
    bb.put(o2)
    assert bb.value("worker_a", "val") == 1

    # Higher confidence -> overwrites
    o3 = AgentOutcome(agent="worker_a", contributed=True, confidence=0.85, data={"val": 3})
    bb.put(o3)
    assert bb.value("worker_a", "val") == 3


def test_blackboard_missing() -> None:
    """Verifica capacità mancanti nel blackboard."""
    bb = Blackboard(run_id="run_2")
    missing = bb.missing({AgentCapability.READ_GTFS, AgentCapability.ASSESS_IMPACT})
    assert "assess_impact" in missing
    assert "read_gtfs" in missing


def test_mobility_supervisor_con_negotiation() -> None:
    """MobilitySupervisor accetta NegotiationOutcome e produce finding coerente."""
    repo = FakeRepo()
    sup = MobilitySupervisor(repo)  # type: ignore[arg-type]
    ctx = RunContext(
        run_id="run_3", zone_id="Z_BAGNOLI", now=datetime(2026, 11, 15, 14, 0, tzinfo=timezone.utc)
    )
    bb = Blackboard(run_id="run_3")

    prop = RouteProposal(
        proposal_id="p1",
        origin=Waypoint(
            label="Bagnoli", lat=40.81, lon=14.16, kind="zone", resolved_by="dictionary"
        ),
        destination=Waypoint(
            label="Centro", lat=40.85, lon=14.27, kind="zone", resolved_by="dictionary"
        ),
        legs=(
            RouteLeg(
                mode="bus",
                route_id="151",
                from_stop="A",
                to_stop="B",
                departure=ctx.now,
                arrival=ctx.now,
                duration_min=25,
            ),
        ),
        total_duration_min=25,
        transfers=0,
        zone_ids=("Z_BAGNOLI", "Z_CENTRO"),
        route_ids=("151",),
        is_simulated=False,
        source_id="anm",
        data_reference="ref1",
    )
    outcome = NegotiationOutcome(
        final_proposal=prop,
        iterations=2,
        exhausted=False,
        uncertain=False,
        constraints_applied=("alert_closure",),
    )

    finding = sup.run(ctx, bb, negotiation_outcome=outcome)
    assert isinstance(finding, Finding)
    assert finding.agent == AgentName.MOBILITY
    assert finding.content["estimated_time_min"] == 25
    assert finding.content["iterations"] == 2
    assert "alert_closure" in finding.content["constraints_applied"]


def test_crowding_supervisor() -> None:
    """CrowdingSupervisor aggrega occupancy e produce finding density_alert."""
    repo = FakeRepo()
    sup = CrowdingSupervisor(repo)  # type: ignore[arg-type]
    ctx = RunContext(
        run_id="run_4", zone_id="Z_BAGNOLI", now=datetime(2026, 11, 15, 14, 0, tzinfo=timezone.utc)
    )
    bb = Blackboard(run_id="run_4")

    finding = sup.run(ctx, bb)
    assert isinstance(finding, Finding)
    assert finding.agent == AgentName.CROWDING
    assert "density" in finding.content
    assert finding.content["density"] > 0.0


def test_context_supervisor() -> None:
    """ContextSupervisor aggrega meteo ed eventi e produce finding impact_assessment."""
    repo = FakeRepo()
    sup = ContextSupervisor(repo)  # type: ignore[arg-type]
    ctx = RunContext(
        run_id="run_5", zone_id="Z_BAGNOLI", now=datetime(2026, 11, 15, 14, 0, tzinfo=timezone.utc)
    )
    bb = Blackboard(run_id="run_5")

    finding = sup.run(ctx, bb)
    assert isinstance(finding, Finding)
    assert finding.agent == AgentName.CONTEXT
    assert "alert_level" in finding.content


def test_run_supervisor_execution() -> None:
    """RunSupervisor esegue i 3 supervisori nell'ordine registered e popola il trace."""
    repo = FakeRepo()
    clock = FixedClock(datetime(2026, 11, 15, 14, 0, tzinfo=timezone.utc))
    trace = Trace()
    run_sup = RunSupervisor(repo, clock=clock)  # type: ignore[arg-type]

    findings = run_sup.execute_agents(zone_id="Z_BAGNOLI", trace=trace)
    assert len(findings) == 3
    agents = [f.agent for f in findings if isinstance(f, Finding)]
    assert agents == [AgentName.MOBILITY, AgentName.CROWDING, AgentName.CONTEXT]

    # Verify trace events
    delegations = [e for e in trace.events if e.event_type == "worker_delegated"]
    assert len(delegations) == 3
