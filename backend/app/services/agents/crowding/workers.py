"""Specialized workers for Crowding domain (02_architettura_agentica.md §6.2)."""

from __future__ import annotations

from app.domain.logic.units import occupancy_to_density
from app.repositories.base import SourceRepository
from app.services.agents.base import AgentCapability, AgentOutcome, RunContext
from app.services.agents.blackboard import Blackboard


class OccupancyReader:
    name = "occupancy_reader"
    capabilities = {AgentCapability.READ_OCCUPANCY}

    def __init__(self, repository: SourceRepository) -> None:
        self._repo = repository

    def can_handle(self, ctx: RunContext) -> bool:
        return True

    def run(self, ctx: RunContext, blackboard: Blackboard) -> AgentOutcome:
        occupancy_rows = self._repo.get_latest_occupancy()
        if not occupancy_rows:
            return AgentOutcome(
                agent=self.name,
                contributed=False,
                reason="Nessuna stima di occupazione disponibile",
                confidence=0.0,
            )
        max_occ = max(float(r.get("occupancy_pct", 0.0)) for r in occupancy_rows)
        density = occupancy_to_density(max_occ)
        is_sim = any(bool(r.get("is_simulated")) for r in occupancy_rows)
        data_ref = str(occupancy_rows[0].get("data_reference", "ref_occ"))

        return AgentOutcome(
            agent=self.name,
            contributed=True,
            data={
                "max_occupancy_pct": max_occ,
                "density": density,
                "is_simulated": is_sim,
                "data_reference": data_ref,
            },
            confidence=0.85,
        )


class EventForecaster:
    name = "event_forecaster"
    capabilities = {AgentCapability.FORECAST_EVENTS}

    def __init__(self, repository: SourceRepository) -> None:
        self._repo = repository

    def can_handle(self, ctx: RunContext) -> bool:
        return True

    def run(self, ctx: RunContext, blackboard: Blackboard) -> AgentOutcome:
        events = self._repo.get_events(zone_id=ctx.zone_id)
        if not events:
            return AgentOutcome(
                agent=self.name,
                contributed=True,
                data={"event_density_prior": 0.0, "events_count": 0},
                confidence=0.90,
            )
        max_att = max(int(e.get("expected_attendance") or e.get("attendance") or 0) for e in events)
        # 10,000 attendance maps to 0.85 density prior, 50,000+ to 0.95
        if max_att >= 50000:
            prior = 0.95
        elif max_att >= 10000:
            prior = 0.88
        elif max_att > 0:
            prior = 0.60
        else:
            prior = 0.0

        return AgentOutcome(
            agent=self.name,
            contributed=True,
            data={
                "event_density_prior": prior,
                "events_count": len(events),
                "max_attendance": max_att,
            },
            confidence=0.80,
        )


class DensityEstimator:
    name = "density_estimator"
    capabilities = {AgentCapability.ESTIMATE_DENSITY}

    def can_handle(self, ctx: RunContext) -> bool:
        return True

    def run(self, ctx: RunContext, blackboard: Blackboard) -> AgentOutcome:
        # Fallback estimator when sensor readings are missing
        return AgentOutcome(
            agent=self.name,
            contributed=True,
            data={"estimated_density": 0.45},
            confidence=0.70,
        )


class ZoneAggregator:
    name = "zone_aggregator"
    capabilities = {AgentCapability.AGGREGATE_ZONES}

    def can_handle(self, ctx: RunContext) -> bool:
        return True

    def run(self, ctx: RunContext, blackboard: Blackboard) -> AgentOutcome:
        occ_density = blackboard.value("occupancy_reader", "density", None)
        event_prior = blackboard.value("event_forecaster", "event_density_prior", None)
        est_density = blackboard.value("density_estimator", "estimated_density", 0.40)

        candidates = [d for d in (occ_density, event_prior, est_density) if d is not None]
        # Prudent rule from 02_architettura_agentica.md §6.2: max(sensor, prior)
        final_density = max(candidates) if candidates else 0.40

        return AgentOutcome(
            agent=self.name,
            contributed=True,
            data={"final_density": round(final_density, 2)},
            confidence=0.90,
        )
