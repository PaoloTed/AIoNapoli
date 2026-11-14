"""Specialized Mobility Agent producing Finding or structured Refusal."""

from __future__ import annotations

from datetime import datetime, timezone

from app.domain.models.finding import AgentName, Finding, FindingType, Severity
from app.domain.models.refusal import Refusal
from app.repositories.base import SourceRepository
from app.services.agents.mobility.itineraries import format_legs_summary, parse_point_wkt
from app.services.agents.mobility.otp_client import OtpClient


class MobilityAgent:
    """Interprets GTFS static, GTFS-RT, service alerts, and OTP routing."""

    def __init__(
        self,
        repository: SourceRepository,
        *,
        otp_client: OtpClient | None = None,
        rt_max_age_s: int = 90,
    ) -> None:
        self._repo = repository
        self._otp = otp_client or OtpClient()
        self._rt_max_age_s = rt_max_age_s

    def evaluate(
        self,
        *,
        route_id: str | None = None,
        origin_stop_id: str | None = None,
        destination_stop_id: str | None = None,
        zone_id: str | None = None,
        horizon_hours: float | None = None,
        allow_simulation: bool = True,
        require_realtime: bool = False,
        now: datetime | None = None,
    ) -> Finding | Refusal:
        ref_now = now or datetime.now(timezone.utc)

        routes = self._repo.get_routes()
        route_ids = {str(r["route_id"]) for r in routes}
        if not route_ids or (route_id is not None and route_id not in route_ids):
            return Refusal(
                agent=AgentName.MOBILITY,
                reason_code="missing_gtfs",
                missing_input=["routes", *([f"route:{route_id}"] if route_id else [])],
                detail=f"Nessun dato GTFS trovato per la linea '{route_id or 'richiesta'}'",
            )

        stops = self._repo.get_stops()
        stops_by_id = {str(s["stop_id"]): s for s in stops}
        if not stops_by_id:
            return Refusal(
                agent=AgentName.MOBILITY,
                reason_code="unmapped_point",
                missing_input=["stops"],
                detail="Tabella fermate GTFS vuota",
            )
        if origin_stop_id is not None and origin_stop_id not in stops_by_id:
            return Refusal(
                agent=AgentName.MOBILITY,
                reason_code="unmapped_point",
                missing_input=[f"stop:{origin_stop_id}"],
                detail=f"Origine '{origin_stop_id}' non mappata su una fermata GTFS",
            )
        if destination_stop_id is not None and destination_stop_id not in stops_by_id:
            return Refusal(
                agent=AgentName.MOBILITY,
                reason_code="unmapped_point",
                missing_input=[f"stop:{destination_stop_id}"],
                detail=f"Destinazione '{destination_stop_id}' non mappata su una fermata GTFS",
            )

        if horizon_hours is not None and horizon_hours > 24.0 and not allow_simulation:
            return Refusal(
                agent=AgentName.MOBILITY,
                reason_code="out_of_horizon",
                missing_input=["gtfs_future_horizon"],
                detail="Finestra temporale oltre l'orizzonte del GTFS statico senza simulazione",
            )

        alerts = self._repo.get_active_service_alerts(now=ref_now)
        positions = self._repo.get_fresh_vehicle_positions(
            now=ref_now,
            max_age_s=self._rt_max_age_s,
        )
        trip_updates = self._repo.get_latest_trip_updates()

        if require_realtime and not positions and not allow_simulation:
            return Refusal(
                agent=AgentName.MOBILITY,
                reason_code="missing_realtime",
                missing_input=["vehicle_positions"],
                detail="Dati real-time assenti per la linea richiesta senza simulazione dichiarata",
            )

        origin_stop = stops_by_id.get(origin_stop_id) if origin_stop_id else None
        dest_stop = stops_by_id.get(destination_stop_id) if destination_stop_id else None
        from_coords = parse_point_wkt(origin_stop.get("geometry") if origin_stop else None) or (
            40.8522,
            14.2724,
        )
        to_coords = parse_point_wkt(dest_stop.get("geometry") if dest_stop else None) or (
            40.8165,
            14.1672,
        )

        itinerary = self._otp.plan_itinerary(
            from_lat=from_coords[0],
            from_lon=from_coords[1],
            to_lat=to_coords[0],
            to_lon=to_coords[1],
        )

        # Derive congestion and severity from active alerts and trip updates
        matching_alerts = [
            a for a in alerts if route_id is None or a.get("route_id") in (route_id, None)
        ]
        max_delay_s = max(
            (
                int(t.get("arrival_delay_s") or 0)
                for t in trip_updates
                if t.get("schedule_relationship") != "no_data"
            ),
            default=0,
        )

        has_disruption = any(a.get("severity") in ("high", "critical") for a in matching_alerts)
        if has_disruption:
            severity = Severity.HIGH
            finding_type = FindingType.ROUTE_DISRUPTION
            congestion_val = 0.88
            confidence = float(matching_alerts[0].get("confidence", 0.9))
        elif max_delay_s >= 300:
            severity = Severity.MEDIUM
            finding_type = FindingType.ROUTE_ALTERNATIVE
            congestion_val = 0.68
            confidence = 0.82
        else:
            severity = Severity.LOW
            finding_type = FindingType.ROUTE_ALTERNATIVE
            congestion_val = 0.35
            confidence = 0.85

        resolved_zone = (
            zone_id
            or (dest_stop.get("zone_id") if dest_stop else None)
            or (matching_alerts[0].get("zone_id") if matching_alerts else None)
            or "Z_BAGNOLI"
        )

        is_simulated = itinerary.is_simulated or any(bool(p.get("is_simulated")) for p in positions)
        if matching_alerts and not itinerary.is_simulated:
            source_id = str(matching_alerts[0].get("source_id") or "anm")
            data_ref = str(matching_alerts[0].get("data_reference") or itinerary.data_reference)
        else:
            source_id = "anm"
            data_ref = (
                str(positions[0].get("data_reference")) if positions else itinerary.data_reference
            )

        content = {
            "zone_id": resolved_zone,
            "congestion": round(congestion_val, 2),
            "line_id": route_id or "L2",
            "estimated_time_min": itinerary.duration_min,
            "recommended_route": format_legs_summary(itinerary.legs),
            "active_vehicles": len(positions),
        }
        if itinerary.fallback_reason:
            content["fallback_reason"] = itinerary.fallback_reason

        return Finding(
            agent=AgentName.MOBILITY,
            type=finding_type,
            content=content,
            confidence=round(min(1.0, max(0.0, confidence)), 2),
            severity=severity,
            source_id=source_id,
            data_reference=data_ref,
            is_simulated=is_simulated,
            timestamp=ref_now,
        )
