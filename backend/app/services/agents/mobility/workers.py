"""Specialized workers for Mobility domain (02_architettura_agentica.md §6.1)."""

from __future__ import annotations

from app.repositories.base import SourceRepository
from app.services.agents.base import AgentCapability, AgentOutcome, RunContext
from app.services.agents.blackboard import Blackboard
from app.services.agents.mobility.itineraries import format_legs_summary
from app.services.agents.mobility.otp_client import OtpClient


class GtfsReader:
    name = "gtfs_reader"
    capabilities = {AgentCapability.READ_GTFS}

    def __init__(self, repository: SourceRepository) -> None:
        self._repo = repository

    def can_handle(self, ctx: RunContext) -> bool:
        return True

    def run(self, ctx: RunContext, blackboard: Blackboard) -> AgentOutcome:
        routes = self._repo.get_routes()
        stops = self._repo.get_stops()
        if not routes or not stops:
            return AgentOutcome(
                agent=self.name,
                contributed=False,
                reason="Dati GTFS statici assenti o incompleti",
                confidence=0.0,
            )
        data = {
            "route_count": len(routes),
            "stop_count": len(stops),
            "routes": [str(r.get("route_id")) for r in routes],
            "stops_by_id": {str(s["stop_id"]): s for s in stops},
        }
        return AgentOutcome(
            agent=self.name,
            contributed=True,
            data=data,
            confidence=0.95,
        )


class RealtimeReader:
    name = "realtime_reader"
    capabilities = {AgentCapability.READ_REALTIME}

    def __init__(self, repository: SourceRepository) -> None:
        self._repo = repository

    def can_handle(self, ctx: RunContext) -> bool:
        return True

    def run(self, ctx: RunContext, blackboard: Blackboard) -> AgentOutcome:
        now = ctx.now
        positions = self._repo.get_fresh_vehicle_positions(now=now) if now else []
        trip_updates = self._repo.get_latest_trip_updates()
        alerts = self._repo.get_active_service_alerts(now=now)

        max_delay = max(
            (
                int(t.get("arrival_delay_s") or 0)
                for t in trip_updates
                if t.get("schedule_relationship") != "no_data"
            ),
            default=0,
        )
        return AgentOutcome(
            agent=self.name,
            contributed=True,
            data={
                "positions_count": len(positions),
                "max_delay_s": max_delay,
                "alerts_count": len(alerts),
                "is_simulated": any(bool(p.get("is_simulated")) for p in positions)
                if positions
                else True,
            },
            confidence=0.85 if positions else 0.70,
        )


class RoutePlanner:
    name = "route_planner"
    capabilities = {AgentCapability.PLAN_ROUTES}

    def __init__(self, otp_client: OtpClient | None = None) -> None:
        self._otp = otp_client or OtpClient()

    def can_handle(self, ctx: RunContext) -> bool:
        return True

    def run(self, ctx: RunContext, blackboard: Blackboard) -> AgentOutcome:
        try:
            itinerary = self._otp.plan_itinerary(
                from_lat=40.8522,
                from_lon=14.2724,
                to_lat=40.8165,
                to_lon=14.1672,
            )
            return AgentOutcome(
                agent=self.name,
                contributed=True,
                data={
                    "itinerary": itinerary,
                    "duration_min": itinerary.duration_min,
                    "recommended_route": format_legs_summary(itinerary.legs),
                    "is_simulated": itinerary.is_simulated,
                    "data_reference": itinerary.data_reference,
                },
                confidence=0.90,
            )
        except Exception as exc:
            return AgentOutcome(
                agent=self.name,
                contributed=False,
                reason=f"Errore generazione itinerario: {exc}",
                confidence=0.0,
            )


class AlternativeComparator:
    name = "comparator"
    capabilities = {AgentCapability.COMPARE_ROUTES}

    def can_handle(self, ctx: RunContext) -> bool:
        return True

    def run(self, ctx: RunContext, blackboard: Blackboard) -> AgentOutcome:
        itinerary = blackboard.value("route_planner", "itinerary")
        if not itinerary:
            return AgentOutcome(
                agent=self.name,
                contributed=False,
                reason="Nessun itinerario da confrontare",
                confidence=0.0,
            )
        return AgentOutcome(
            agent=self.name,
            contributed=True,
            data={
                "best_itinerary": itinerary,
                "compared_count": len(getattr(itinerary, "proposals", [itinerary])),
            },
            confidence=0.90,
        )


class StreetMapper:
    name = "street_mapper"
    capabilities = {AgentCapability.STREET_MAPPER}

    def can_handle(self, ctx: RunContext) -> bool:
        return True

    def run(self, ctx: RunContext, blackboard: Blackboard) -> AgentOutcome:
        # Resolves streets or zones from text/context
        return AgentOutcome(
            agent=self.name,
            contributed=True,
            data={"mapped_zone": ctx.zone_id},
            confidence=0.85,
        )
