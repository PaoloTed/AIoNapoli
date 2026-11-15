"""Level-1 Orchestrator (RunSupervisor) managing supervisors and negotiation cycle.

Defined in implementations/01_agenti_negoziazione/02_architettura_agentica.md §7.
"""

from __future__ import annotations

import uuid
from datetime import timezone

from app.domain.models.finding import Finding
from app.domain.models.refusal import Refusal
from app.domain.models.routing import (
    NegotiationOutcome,
    RouteLeg,
    RouteProposal,
    TravelConstraint,
    Waypoint,
)
from app.domain.models.trace import Trace
from app.domain.models.trip_request import TripLocation, TripRequest
from app.repositories.base import SourceRepository
from app.services.agents.base import RunContext
from app.services.agents.blackboard import Blackboard
from app.services.agents.context.supervisor import ContextSupervisor
from app.services.agents.crowding.supervisor import CrowdingSupervisor
from app.services.agents.incidents.agent import IncidentsAgent
from app.services.agents.mobility.otp_client import OtpClient
from app.services.agents.mobility.supervisor import MobilitySupervisor
from app.services.agents.registry import RegistryConfig, load_registry
from app.services.orchestrator.negotiation import negotiate
from app.utils.clock import Clock, SystemClock


class OtpRoutePlannerAdapter:
    """Adapts OtpClient to the RoutePlanner protocol used by the negotiation cycle."""

    def __init__(self, otp_client: OtpClient) -> None:
        self._otp = otp_client

    def plan(
        self,
        request: TripRequest,
        constraints: list[TravelConstraint],
        num_itineraries: int = 12,
    ) -> list[RouteProposal]:
        banned_routes = [
            getattr(c.target, "route_id")
            for c in constraints
            if hasattr(c.target, "route_id") and getattr(c.target, "route_id")
        ]
        banned_stops = [
            getattr(c.target, "stop_id")
            for c in constraints
            if hasattr(c.target, "stop_id") and getattr(c.target, "stop_id")
        ]

        result = self._otp.plan_itinerary(
            from_lat=request.origin.lat,
            from_lon=request.origin.lon,
            to_lat=request.destination.lat,
            to_lon=request.destination.lon,
            banned_routes=banned_routes,
            banned_stops=banned_stops,
            num_itineraries=num_itineraries,
        )

        proposals_raw = getattr(result, "proposals", [result])
        output: list[RouteProposal] = []
        origin_wp = Waypoint(
            label=request.origin.label,
            lat=request.origin.lat,
            lon=request.origin.lon,
            kind=request.origin.kind,
            resolved_by=request.origin.resolved_by,
        )
        dest_wp = Waypoint(
            label=request.destination.label,
            lat=request.destination.lat,
            lon=request.destination.lon,
            kind=request.destination.kind,
            resolved_by=request.destination.resolved_by,
        )

        for i, item in enumerate(proposals_raw):
            route_ids: list[str] = []
            legs_list: list[RouteLeg] = []
            cur_time = request.when
            for leg in item.legs:
                r_id = getattr(leg, "route", None)
                if r_id:
                    route_ids.append(str(r_id))
                dur_m = max(1, int(getattr(leg, "duration_s", 600) / 60))
                dep = cur_time
                arr = cur_time
                leg_mode = str(getattr(leg, "mode", "bus")).lower()
                valid_modes = {"walk", "bus", "metro", "tram", "funicular", "rail"}
                mode_str = leg_mode if leg_mode in valid_modes else "bus"

                legs_list.append(
                    RouteLeg(
                        mode=mode_str,  # type: ignore[arg-type]
                        route_id=r_id,
                        from_stop=getattr(leg, "from_stop_name", "") or "Origine",
                        to_stop=getattr(leg, "to_stop_name", "") or "Destinazione",
                        from_stop_id=getattr(leg, "from_stop_id", None),
                        to_stop_id=getattr(leg, "to_stop_id", None),
                        departure=dep,
                        arrival=arr,
                        duration_min=dur_m,
                        zone_ids=(request.origin.label, request.destination.label),
                        headsign=getattr(leg, "headsign", None),
                    )
                )

            output.append(
                RouteProposal(
                    proposal_id=f"prop_{i + 1}_{item.data_reference[:8]}",
                    origin=origin_wp,
                    destination=dest_wp,
                    legs=tuple(legs_list),
                    total_duration_min=item.duration_min,
                    transfers=max(0, len(item.legs) - 1),
                    zone_ids=(request.origin.label, request.destination.label),
                    route_ids=tuple(dict.fromkeys(route_ids)),
                    is_simulated=item.is_simulated,
                    source_id=item.source_id,
                    data_reference=item.data_reference,
                    exclude_applied=tuple(banned_routes + banned_stops),
                )
            )

        return output


class RunSupervisor:
    """Level-1 orchestrator managing vertical supervisors, blackboard, and negotiation."""

    def __init__(
        self,
        repository: SourceRepository,
        *,
        otp_client: OtpClient | None = None,
        clock: Clock | None = None,
        registry: RegistryConfig | None = None,
        enable_negotiation: bool = True,
    ) -> None:
        self._repo = repository
        self._otp = otp_client or OtpClient()
        self._clock = clock or SystemClock()
        self._registry = registry or load_registry()
        self._enable_negotiation = enable_negotiation
        self._incidents = IncidentsAgent(repository, clock=self._clock)

        self._mobility_sup = MobilitySupervisor(repository, otp_client=self._otp)
        self._crowding_sup = CrowdingSupervisor(repository)
        self._context_sup = ContextSupervisor(repository)

    def execute_agents(
        self,
        *,
        zone_id: str = "Z_BAGNOLI",
        trip_request: TripRequest | None = None,
        trace: Trace | None = None,
    ) -> list[Finding | Refusal]:
        now = self._clock.now()
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        else:
            now = now.astimezone(timezone.utc)

        run_id = f"run_{uuid.uuid4().hex[:8]}"
        ctx = RunContext(
            run_id=run_id,
            zone_id=zone_id,
            now=now,
            trip_request=trip_request,
        )
        blackboard = Blackboard(run_id=run_id)

        # 1. Optionally run negotiation cycle
        negotiation_outcome: NegotiationOutcome | None = None
        if self._enable_negotiation:
            active_request = trip_request or TripRequest(
                origin=TripLocation(
                    label="Bagnoli", lat=40.8522, lon=14.2724, kind="zone", resolved_by="dictionary"
                ),
                destination=TripLocation(
                    label="Fuorigrotta",
                    lat=40.8165,
                    lon=14.1672,
                    kind="zone",
                    resolved_by="dictionary",
                ),
                when=now,
            )
            planner = OtpRoutePlannerAdapter(self._otp)
            known_constraints = self._incidents.get_known_constraints(now)
            try:
                negotiation_outcome = negotiate(
                    request=active_request,
                    planner=planner,
                    validator=self._incidents,
                    known_constraints=known_constraints,
                    trace=trace,
                    now=now,
                    ctx=ctx,
                )
            except Exception:
                pass

        # 2. Execute vertical supervisors in deterministic order
        findings_or_refusals: list[Finding | Refusal] = []

        # Mobility
        if "mobility" in self._registry.order:
            if trace is not None:
                trace.worker_delegated(
                    agent="mobility_supervisor",
                    capabilities=sorted(str(c.value) for c in self._mobility_sup.capabilities),
                    can_handle_reason="default_pipeline",
                )
            m_res = self._mobility_sup.run(ctx, blackboard, negotiation_outcome=negotiation_outcome)
            findings_or_refusals.append(m_res)
            if trace is not None:
                trace.worker_outcome(
                    agent="mobility_supervisor",
                    contributed=isinstance(m_res, Finding),
                    reason=m_res.detail if isinstance(m_res, Refusal) else "",
                )

        # Crowding
        if "crowding" in self._registry.order:
            if trace is not None:
                trace.worker_delegated(
                    agent="crowding_supervisor",
                    capabilities=sorted(str(c.value) for c in self._crowding_sup.capabilities),
                    can_handle_reason="default_pipeline",
                )
            c_res = self._crowding_sup.run(ctx, blackboard)
            findings_or_refusals.append(c_res)
            if trace is not None:
                trace.worker_outcome(
                    agent="crowding_supervisor",
                    contributed=isinstance(c_res, Finding),
                    reason=c_res.detail if isinstance(c_res, Refusal) else "",
                )

        # Context
        if "context" in self._registry.order:
            if trace is not None:
                trace.worker_delegated(
                    agent="context_supervisor",
                    capabilities=sorted(str(c.value) for c in self._context_sup.capabilities),
                    can_handle_reason="default_pipeline",
                )
            x_res = self._context_sup.run(ctx, blackboard)
            findings_or_refusals.append(x_res)
            if trace is not None:
                trace.worker_outcome(
                    agent="context_supervisor",
                    contributed=isinstance(x_res, Finding),
                    reason=x_res.detail if isinstance(x_res, Refusal) else "",
                )

        return findings_or_refusals
