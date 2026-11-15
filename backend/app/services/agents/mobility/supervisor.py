"""Mobility Supervisor orchestrating mobility workers (02_architettura_agentica.md §6.1)."""

from __future__ import annotations

from datetime import datetime, timezone

from app.domain.models.finding import AgentName, Finding, FindingType, Severity
from app.domain.models.refusal import Refusal
from app.domain.models.routing import NegotiationOutcome
from app.repositories.base import SourceRepository
from app.services.agents.base import AgentCapability, RunContext, WorkerProtocol
from app.services.agents.blackboard import Blackboard
from app.services.agents.mobility.otp_client import OtpClient
from app.services.agents.mobility.workers import (
    AlternativeComparator,
    GtfsReader,
    RealtimeReader,
    RoutePlanner,
    StreetMapper,
)


class MobilitySupervisor:
    name = "mobility_supervisor"
    capabilities = {
        AgentCapability.READ_GTFS,
        AgentCapability.READ_REALTIME,
        AgentCapability.PLAN_ROUTES,
        AgentCapability.COMPARE_ROUTES,
        AgentCapability.STREET_MAPPER,
    }

    def __init__(
        self,
        repository: SourceRepository,
        *,
        otp_client: OtpClient | None = None,
        workers: list[WorkerProtocol] | None = None,
    ) -> None:
        self._repo = repository
        self._otp = otp_client or OtpClient()
        self._workers = workers or [
            GtfsReader(repository),
            RealtimeReader(repository),
            RoutePlanner(self._otp),
            AlternativeComparator(),
            StreetMapper(),
        ]

    def can_handle(self, ctx: RunContext) -> bool:
        return True

    def run(
        self,
        ctx: RunContext,
        blackboard: Blackboard,
        negotiation_outcome: NegotiationOutcome | None = None,
    ) -> Finding | Refusal:
        ref_now = ctx.now or datetime.now(timezone.utc)

        # 1. Selection & Delegation
        for worker in self._workers:
            if worker.can_handle(ctx):
                outcome = worker.run(ctx, blackboard)
                blackboard.put(outcome)

        # Check for GTFS presence
        gtfs_outcome = blackboard.get("gtfs_reader")
        if gtfs_outcome and not gtfs_outcome.contributed:
            return Refusal(
                agent=AgentName.MOBILITY,
                reason_code="missing_gtfs",
                missing_input=["routes", "stops"],
                detail=gtfs_outcome.reason or "Dati GTFS assenti",
            )

        # 2. Check Negotiation Outcome if available
        if negotiation_outcome is not None:
            proposal = negotiation_outcome.final_proposal
            congestion = (
                0.88
                if negotiation_outcome.exhausted
                else (0.65 if proposal.penalty_applied else 0.35)
            )
            confidence = (
                0.60
                if negotiation_outcome.exhausted
                else (0.75 if negotiation_outcome.uncertain else 0.90)
            )
            finding_type = (
                FindingType.ROUTE_DISRUPTION
                if negotiation_outcome.exhausted
                else FindingType.ROUTE_ALTERNATIVE
            )
            severity = (
                Severity.HIGH
                if negotiation_outcome.exhausted
                else (Severity.MEDIUM if proposal.penalty_applied else Severity.LOW)
            )

            content = {
                "zone_id": ctx.zone_id,
                "congestion": congestion,
                "line_id": proposal.route_ids[0] if proposal.route_ids else "L2",
                "estimated_time_min": proposal.total_duration_min,
                "recommended_route": " -> ".join(
                    f"{leg.mode.upper()} {leg.route_id or ''}".strip() for leg in proposal.legs
                ),
                "constraints_applied": list(negotiation_outcome.constraints_applied),
                "iterations": negotiation_outcome.iterations,
                "exhausted": negotiation_outcome.exhausted,
                "uncertain": negotiation_outcome.uncertain,
            }
            return Finding(
                agent=AgentName.MOBILITY,
                type=finding_type,
                content=content,
                confidence=round(confidence, 2),
                severity=severity,
                source_id=proposal.source_id,
                data_reference=proposal.data_reference,
                is_simulated=proposal.is_simulated,
                timestamp=ref_now,
            )

        # 3. Default Composition from Blackboard
        planner_outcome = blackboard.get("route_planner")
        rt_outcome = blackboard.get("realtime_reader")

        if not planner_outcome or not planner_outcome.contributed:
            return Refusal(
                agent=AgentName.MOBILITY,
                reason_code="unmapped_point",
                missing_input=["itinerary"],
                detail="Impossibile calcolare il percorso",
            )

        duration_min = planner_outcome.data.get("duration_min", 30)
        route_text = planner_outcome.data.get("recommended_route", "Bus 151 -> Cumana")
        is_sim = planner_outcome.data.get("is_simulated", True)
        data_ref = planner_outcome.data.get("data_reference", "ref_otp")

        max_delay = rt_outcome.data.get("max_delay_s", 0) if rt_outcome else 0
        if max_delay >= 300:
            congestion = 0.68
            severity = Severity.MEDIUM
        else:
            congestion = 0.35
            severity = Severity.LOW

        content = {
            "zone_id": ctx.zone_id,
            "congestion": congestion,
            "line_id": "151",
            "estimated_time_min": duration_min,
            "recommended_route": route_text,
            "active_vehicles": rt_outcome.data.get("positions_count", 0) if rt_outcome else 0,
        }

        return Finding(
            agent=AgentName.MOBILITY,
            type=FindingType.ROUTE_ALTERNATIVE,
            content=content,
            confidence=0.88,
            severity=severity,
            source_id="anm",
            data_reference=data_ref,
            is_simulated=is_sim,
            timestamp=ref_now,
        )
