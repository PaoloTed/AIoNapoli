"""Crowding Supervisor orchestrating crowding workers (02_architettura_agentica.md §6.2)."""

from __future__ import annotations

from datetime import datetime, timezone

from app.domain.models.finding import AgentName, Finding, FindingType, Severity
from app.domain.models.refusal import Refusal
from app.repositories.base import SourceRepository
from app.services.agents.base import AgentCapability, RunContext, WorkerProtocol
from app.services.agents.blackboard import Blackboard
from app.services.agents.crowding.workers import (
    DensityEstimator,
    EventForecaster,
    OccupancyReader,
    ZoneAggregator,
)


class CrowdingSupervisor:
    name = "crowding_supervisor"
    capabilities = {
        AgentCapability.READ_OCCUPANCY,
        AgentCapability.FORECAST_EVENTS,
        AgentCapability.ESTIMATE_DENSITY,
        AgentCapability.AGGREGATE_ZONES,
    }

    def __init__(
        self,
        repository: SourceRepository,
        *,
        workers: list[WorkerProtocol] | None = None,
    ) -> None:
        self._repo = repository
        self._workers = workers or [
            OccupancyReader(repository),
            EventForecaster(repository),
            DensityEstimator(),
            ZoneAggregator(),
        ]

    def can_handle(self, ctx: RunContext) -> bool:
        return True

    def run(self, ctx: RunContext, blackboard: Blackboard) -> Finding | Refusal:
        ref_now = ctx.now or datetime.now(timezone.utc)

        # 1. Delegate
        for worker in self._workers:
            if worker.can_handle(ctx):
                outcome = worker.run(ctx, blackboard)
                blackboard.put(outcome)

        # 2. Check for missing occupancy
        occ_outcome = blackboard.get("occupancy_reader")
        if not occ_outcome or not occ_outcome.contributed:
            return Refusal(
                agent=AgentName.CROWDING,
                reason_code="missing_occupancy",
                missing_input=["occupancy_estimates"],
                detail="Nessuna stima di occupazione disponibile",
            )

        density = blackboard.value("zone_aggregator", "final_density", 0.50)
        is_sim = occ_outcome.data.get("is_simulated", True)
        data_ref = occ_outcome.data.get("data_reference", "ref_occ")

        if density >= 0.85:
            severity = Severity.HIGH
        elif density >= 0.65:
            severity = Severity.MEDIUM
        else:
            severity = Severity.LOW

        content = {
            "zone_id": ctx.zone_id,
            "density": round(float(density), 2),
            "line_id": "L2",
            "threshold": 0.85,
        }

        return Finding(
            agent=AgentName.CROWDING,
            type=FindingType.DENSITY_ALERT,
            content=content,
            confidence=0.91,
            severity=severity,
            source_id="anm",
            data_reference=data_ref,
            is_simulated=is_sim,
            timestamp=ref_now,
        )
