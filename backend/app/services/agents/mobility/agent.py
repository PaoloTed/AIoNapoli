"""Specialized Mobility Agent producing Finding or structured Refusal."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone

from app.domain.models.config import AppConfig
from app.domain.models.finding import AgentName, Finding, FindingType, Severity
from app.domain.models.refusal import Refusal
from app.repositories.base import SourceRepository
from app.services.agents.mobility.itineraries import format_legs_summary, parse_point_wkt
from app.services.agents.mobility.otp_client import (
    DEFAULT_MODES,
    OtpClient,
    OtpGraphQLError,
    OtpHttpError,
    OtpInvalidResponseError,
    OtpNoRouteError,
    OtpTimeoutError,
    OtpUnavailableError,
)


class MobilityAgent:
    """Interprets GTFS static, GTFS-RT, service alerts, and OTP routing."""

    def __init__(
        self,
        repository: SourceRepository,
        *,
        otp_client: OtpClient | None = None,
        config: AppConfig | None = None,
        rt_max_age_s: int = 90,
    ) -> None:
        self._repo = repository
        if otp_client is not None:
            self._otp = otp_client
        elif config is not None:
            self._otp = OtpClient(
                base_url=config.otp_base_url,
                timeout_s=config.otp_timeout_s,
                mode=config.routing_mode,
                timezone=config.routing_timezone,
            )
        else:
            self._otp = OtpClient()
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
        exclude_route_ids: Sequence[str] = (),
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
        from_coords = parse_point_wkt(origin_stop.get("geometry") if origin_stop else None)
        to_coords = parse_point_wkt(dest_stop.get("geometry") if dest_stop else None)

        if origin_stop_id is not None and from_coords is None:
            return Refusal(
                agent=AgentName.MOBILITY,
                reason_code="unmapped_point",
                missing_input=[f"origin_geometry:{origin_stop_id}"],
                detail=f"Origine '{origin_stop_id}' senza coordinate utilizzabili",
            )
        if destination_stop_id is not None and to_coords is None:
            return Refusal(
                agent=AgentName.MOBILITY,
                reason_code="unmapped_point",
                missing_input=[f"destination_geometry:{destination_stop_id}"],
                detail=f"Destinazione '{destination_stop_id}' senza coordinate utilizzabili",
            )

        # A real routing request must never invent coordinates. Demo mode uses
        # the recorded fixture and is the only path allowed to omit them.
        if from_coords is None or to_coords is None:
            if self._otp.mode != "demo":
                missing = "origin_coordinates" if from_coords is None else "destination_coordinates"
                return Refusal(
                    agent=AgentName.MOBILITY,
                    reason_code="unmapped_point",
                    missing_input=[missing],
                    detail="Coordinate di origine/destinazione mancanti per il routing reale",
                )
            from_coords = from_coords or (40.8522, 14.2724)
            to_coords = to_coords or (40.8165, 14.1672)

        try:
            plan = self._otp.plan_itineraries(
                from_lat=from_coords[0],
                from_lon=from_coords[1],
                to_lat=to_coords[0],
                to_lon=to_coords[1],
                depart_at=ref_now,
                first=5,
                modes=DEFAULT_MODES,
                exclude_route_ids=exclude_route_ids,
            )
        except OtpNoRouteError as exc:
            return Refusal(
                agent=AgentName.MOBILITY,
                reason_code="no_route",
                missing_input=["otp_itineraries"],
                detail=str(exc),
            )
        except OtpTimeoutError as exc:
            return Refusal(
                agent=AgentName.MOBILITY,
                reason_code="otp_timeout",
                missing_input=["otp"],
                detail=str(exc),
            )
        except OtpUnavailableError as exc:
            return Refusal(
                agent=AgentName.MOBILITY,
                reason_code="otp_unavailable",
                missing_input=["otp"],
                detail=str(exc),
            )
        except (OtpHttpError, OtpGraphQLError, OtpInvalidResponseError) as exc:
            return Refusal(
                agent=AgentName.MOBILITY,
                reason_code="otp_error",
                missing_input=["otp"],
                detail=str(exc),
            )

        itinerary = plan.itineraries[0]

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
        )
        first_route_id = next(
            (leg.get("route_id") for leg in itinerary.legs if leg.get("route_id")), None
        )
        duration_min = (
            round(itinerary.duration_s / 60) if itinerary.duration_s is not None else None
        )

        is_simulated = plan.is_simulated or any(
            bool(p.get("is_simulated")) for p in positions
        )
        if matching_alerts and not plan.is_simulated:
            source_id = str(matching_alerts[0].get("source_id") or "anm")
            data_ref = str(matching_alerts[0].get("data_reference") or plan.data_reference)
        elif positions and not plan.is_simulated:
            source_id = str(positions[0].get("source_id") or "anm")
            data_ref = str(positions[0].get("data_reference") or plan.data_reference)
        else:
            source_id = plan.source_id
            data_ref = plan.data_reference

        content = {
            "zone_id": resolved_zone,
            "congestion": round(congestion_val, 2),
            "line_id": route_id or first_route_id or "unknown",
            "estimated_time_min": duration_min,
            "duration_s": itinerary.duration_s,
            "itineraries_count": len(plan.itineraries),
            "recommended_route": format_legs_summary(itinerary.legs),
            "active_vehicles": len(positions),
        }
        if plan.fallback_reason:
            content["fallback_reason"] = plan.fallback_reason
        if plan.routing_errors:
            content["routing_warnings"] = plan.routing_errors

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
