"""Deterministic Incidents specialist: alerts + GTFS + OSM geometry -> impacts."""

from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from app.domain.models.config import AppConfig
from app.domain.models.disruption import (
    DisruptionEffect,
    DisruptionLinkRecord,
    DisruptionRecord,
    LinkEntityType,
    ResolutionStatus,
)
from app.repositories.disruptions import DisruptionRepository
from app.repositories.territory import OSMTerritoryRepository
from app.services.agents.incidents.geometry import (
    distance_to_polyline_m,
    leg_polyline,
    line_wkt,
)
from app.services.agents.incidents.gtfs_queries import GtfsQueries
from app.services.agents.incidents.models import (
    Constraint,
    ItineraryAssessment,
    LegImpact,
    RoadCheck,
)
from app.services.agents.mobility.gtfs_ids import parse_otp_id
from app.services.agents.mobility.otp_client import OtpClient

SURFACE_MODES = {
    "WALK",
    "BICYCLE",
    "CAR",
    "BUS",
    "COACH",
    "TRAM",
    "TROLLEYBUS",
}
RAIL_MODES = {
    "SUBWAY",
    "RAIL",
    "FUNICULAR",
    "CABLE_CAR",
    "GONDOLA",
    "MONORAIL",
    "FERRY",
    "AIRPLANE",
}
WALK_LIKE = {"WALK", "BICYCLE"}
HIGHER_OVERLAP_MODES = {"BUS", "COACH", "TRAM", "TROLLEYBUS", "CAR"}
_WKT_POINT_RE = re.compile(r"(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)")


def _parse_dt(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _strip_scope(value: str | None) -> tuple[str | None, str | None]:
    if not value:
        return None, None
    try:
        return parse_otp_id(value)
    except ValueError:
        return None, value


def _mode(value: str | None) -> str:
    return (value or "").strip().upper()


def _wkt_points(wkt: str | None) -> list[tuple[float, float]]:
    if not wkt:
        return []
    return [(float(lat), float(lon)) for lon, lat in _WKT_POINT_RE.findall(wkt)]


def _polyline_distance_m(
    left: list[tuple[float, float]], right: list[tuple[float, float]]
) -> float:
    if not left or not right:
        return float("inf")
    return min(distance_to_polyline_m(lat, lon, right) for lat, lon in left)


class IncidentAgent:
    """Specialist invoked by the journey orchestrator, never a prompt file."""

    def __init__(
        self,
        disruption_repository: DisruptionRepository,
        gtfs_queries: GtfsQueries,
        territory_repository: OSMTerritoryRepository,
        config: AppConfig,
        *,
        otp_client: OtpClient | None = None,
        source_ids: set[str] | None = None,
    ) -> None:
        self._repo = disruption_repository
        self._gtfs = gtfs_queries
        self._territory = territory_repository
        self._config = config
        self._otp = otp_client
        self._source_ids = source_ids
        self._tz = ZoneInfo(config.routing_timezone)

    # -- public API -----------------------------------------------------
    def load_alerts(
        self,
        start: datetime,
        end: datetime,
        *,
        include_simulated: bool = False,
    ) -> list[DisruptionRecord]:
        alerts = self._repo.list_relevant(start, end, include_simulated=include_simulated)
        if self._source_ids is not None:
            alerts = [alert for alert in alerts if alert.source_id in self._source_ids]
        return alerts

    def route_scope_map(
        self,
        *,
        feed_mapping: dict[str, str],
        datasets_info: list[dict[str, Any]],
    ) -> dict[tuple[str, str], str]:
        """Map ``(dataset, original route id)`` to the current OTP scoped id."""
        if self._otp is None:
            return {}
        try:
            routes = self._otp.discover_routes()
        except Exception:
            return {}
        result: dict[tuple[str, str], str] = {}
        agency_to_dataset = self._agency_to_dataset(datasets_info)
        for route in routes:
            dataset = feed_mapping.get(route.feed_id)
            if dataset is None and route.agency_id:
                dataset = agency_to_dataset.get(route.agency_id)
            if dataset:
                result[(dataset, route.gtfs_id)] = route.scoped_id
        return result

    def initial_constraints(
        self,
        alerts: list[DisruptionRecord],
        *,
        start: datetime,
        end: datetime,
        feed_mapping: dict[str, str],
        datasets_info: list[dict[str, Any]],
        route_scope_map: dict[tuple[str, str], str],
    ) -> tuple[list[Constraint], list[str]]:
        """Route exclusions that can be applied before the first OTP call."""
        constraints: dict[str, Constraint] = {}
        warnings: list[str] = []
        for alert in alerts:
            if alert.effect is not DisruptionEffect.BLOCK:
                continue
            if not self._alert_time_overlaps(alert, start, end):
                continue
            for link in alert.links:
                if not link.is_current:
                    continue
                if link.resolution_status is not ResolutionStatus.RESOLVED:
                    continue
                if link.entity_type is LinkEntityType.ROUTE:
                    self._add_route_constraint(
                        constraints,
                        warnings,
                        alert,
                        str(link.entity_id),
                        link.dataset_key,
                        route_scope_map,
                        "route_block",
                    )
                elif link.entity_type is LinkEntityType.TRIP:
                    dataset = link.dataset_key
                    if not dataset:
                        warnings.append(f"{alert.source_id}/{alert.alert_id}: trip senza dataset")
                        continue
                    trip = self._gtfs.trip(dataset, str(link.entity_id))
                    if trip is None:
                        warnings.append(
                            f"{alert.source_id}/{alert.alert_id}: trip "
                            f"{link.entity_id} assente da {dataset}"
                        )
                        continue
                    self._add_route_constraint(
                        constraints,
                        warnings,
                        alert,
                        str(trip["route_id"]),
                        dataset,
                        route_scope_map,
                        "trip_block_expanded_to_route",
                    )
                    warnings.append(
                        f"{alert.source_id}/{alert.alert_id}: blocco trip espanso alla route "
                        f"{dataset}:{trip['route_id']} (OTP 2.10 non supporta esclusione trip)"
                    )
        return list(constraints.values()), warnings

    def _add_route_constraint(
        self,
        constraints: dict[str, Constraint],
        warnings: list[str],
        alert: DisruptionRecord,
        route_id: str,
        dataset_key: str | None,
        route_scope_map: dict[tuple[str, str], str],
        scope: str,
    ) -> None:
        if not dataset_key:
            warnings.append(f"{alert.source_id}/{alert.alert_id}: route {route_id} senza dataset")
            return
        scoped = route_scope_map.get((dataset_key, route_id))
        if not scoped:
            warnings.append(
                f"{alert.source_id}/{alert.alert_id}: route {dataset_key}:{route_id} "
                "non presente nel grafo OTP corrente"
            )
            return
        constraints[scoped] = Constraint(
            route_id=route_id,
            scoped_route_id=scoped,
            dataset_key=dataset_key,
            source_id=alert.source_id,
            alert_id=alert.alert_id,
            reason=alert.title,
            scope=scope,
        )

    def assess_itineraries(
        self,
        itineraries: list[dict[str, Any]],
        *,
        alerts: list[DisruptionRecord],
        feed_mapping: dict[str, str],
        datasets_info: list[dict[str, Any]],
        start: datetime,
        end: datetime,
    ) -> list[ItineraryAssessment]:
        way_rows = self._load_way_rows(alerts)
        agency_to_dataset = self._agency_to_dataset(datasets_info)
        assessments: list[ItineraryAssessment] = []
        for index, itinerary in enumerate(itineraries):
            assessment = ItineraryAssessment(itinerary_index=index)
            legs = itinerary.get("legs") if isinstance(itinerary.get("legs"), list) else []
            for leg_index, leg in enumerate(legs):
                if not isinstance(leg, dict):
                    continue
                mode = _mode(leg.get("mode"))
                transit = bool(leg.get("transit_leg"))
                context = self._leg_context(
                    leg,
                    mode=mode,
                    transit=transit,
                    feed_mapping=feed_mapping,
                    agency_to_dataset=agency_to_dataset,
                )
                if transit and context.get("dataset") is None:
                    if self._alerts_may_touch_leg(alerts, context):
                        assessment.add_impact(
                            self._uncertain_impact(
                                leg_index,
                                context,
                                alerts[0] if alerts else None,
                                "dataset_non_determinabile",
                            )
                        )
                    continue
                for alert in alerts:
                    self._evaluate_gtfs_alert(assessment, leg_index, context, alert)
                if mode in SURFACE_MODES or (not transit and mode in WALK_LIKE):
                    self._evaluate_road_alerts(
                        assessment,
                        leg_index,
                        leg,
                        context,
                        alerts,
                        way_rows,
                    )
            assessment.finalize()
            assessments.append(assessment)
        return assessments

    # -- leg context ----------------------------------------------------
    def _agency_to_dataset(self, datasets_info: list[dict[str, Any]]) -> dict[str, str]:
        result: dict[str, str] = {}
        for info in datasets_info:
            key = str(info.get("dataset_key") or "")
            agencies = str(info.get("agency_ids") or "")
            for agency in agencies.split(","):
                agency = agency.strip()
                if key and agency:
                    result.setdefault(agency, key)
        return result

    def dataset_for_leg(
        self,
        leg: dict[str, Any],
        *,
        feed_mapping: dict[str, str],
        agency_to_dataset: dict[str, str],
    ) -> str | None:
        feed_id, _ = _strip_scope(leg.get("route_id"))
        if feed_id and feed_id in feed_mapping:
            return feed_mapping[feed_id]
        agency_id = leg.get("agency_id")
        if isinstance(agency_id, str):
            return agency_to_dataset.get(agency_id)
        return None

    def _leg_context(
        self,
        leg: dict[str, Any],
        *,
        mode: str,
        transit: bool,
        feed_mapping: dict[str, str],
        agency_to_dataset: dict[str, str],
    ) -> dict[str, Any]:
        feed_id, route_id = _strip_scope(leg.get("route_id"))
        _, trip_id = _strip_scope(leg.get("trip_id"))
        _, from_stop_id = _strip_scope(leg.get("from_stop_id"))
        _, to_stop_id = _strip_scope(leg.get("to_stop_id"))
        start = _parse_dt(leg.get("start_estimated")) or _parse_dt(leg.get("start_scheduled"))
        end = _parse_dt(leg.get("end_estimated")) or _parse_dt(leg.get("end_scheduled"))
        dataset = self.dataset_for_leg(
            leg, feed_mapping=feed_mapping, agency_to_dataset=agency_to_dataset
        )
        trip = None
        stop_times: list[dict[str, Any]] = []
        service_date: date | None = None
        direction: str | None = None
        stop_ids: list[str] = []
        stop_sequences: dict[str, int] = {}
        from_seq = to_seq = None
        service_day_verified = False
        if transit and dataset and trip_id:
            trip = self._gtfs.trip(dataset, trip_id)
            if trip is not None:
                stop_times = self._gtfs.stop_times(dataset, trip_id)
                stop_ids = [str(row["stop_id"]) for row in stop_times]
                stop_sequences = {
                    str(row["stop_id"]): int(row["stop_sequence"]) for row in stop_times
                }
                from_seq = stop_sequences.get(from_stop_id) if from_stop_id else None
                to_seq = stop_sequences.get(to_stop_id) if to_stop_id else None
                if trip.get("direction_id") in (0, 1):
                    direction = "forward" if int(trip["direction_id"]) == 0 else "backward"
                if from_seq is not None and to_seq is not None:
                    direction = "forward" if from_seq < to_seq else "backward"
                service_date, service_day_verified = self._resolve_service_date(
                    trip, stop_times, from_stop_id, to_stop_id, start, end
                )
        if from_stop_id and from_stop_id not in stop_ids:
            stop_ids.append(from_stop_id)
        if to_stop_id and to_stop_id not in stop_ids:
            stop_ids.append(to_stop_id)
        return {
            "feed_id": feed_id,
            "dataset": dataset,
            "route_id": route_id,
            "trip_id": trip_id,
            "from_stop_id": from_stop_id,
            "to_stop_id": to_stop_id,
            "stop_ids": stop_ids,
            "stop_sequences": stop_sequences,
            "from_sequence": from_seq,
            "to_sequence": to_seq,
            "start": start,
            "end": end,
            "mode": mode,
            "transit": transit,
            "direction": direction,
            "service_date": service_date,
            "service_day_verified": service_day_verified,
            "route": self._gtfs.route(dataset, route_id)
            if transit and dataset and route_id
            else None,
        }

    def _resolve_service_date(
        self,
        trip: dict[str, Any],
        stop_times: list[dict[str, Any]],
        from_stop_id: str | None,
        to_stop_id: str | None,
        leg_start: datetime | None,
        leg_end: datetime | None,
    ) -> tuple[date | None, bool]:
        if leg_start is None or leg_end is None or not stop_times:
            return None, False
        by_stop = {str(row["stop_id"]): row for row in stop_times}
        from_row = by_stop.get(from_stop_id) if from_stop_id else None
        to_row = by_stop.get(to_stop_id) if to_stop_id else None
        if from_row is None or to_row is None:
            return None, False
        from_s = from_row.get("departure_s") or from_row.get("arrival_s")
        to_s = to_row.get("arrival_s") or to_row.get("departure_s")
        if from_s is None or to_s is None:
            return None, False
        local_start = leg_start.astimezone(self._tz)
        local_end = leg_end.astimezone(self._tz)
        base = local_start.date()
        for delta in (0, -1, -2):
            candidate = base + timedelta(days=delta)
            candidate_start = datetime.combine(candidate, time.min, tzinfo=self._tz) + timedelta(
                seconds=int(from_s)
            )
            candidate_end = datetime.combine(candidate, time.min, tzinfo=self._tz) + timedelta(
                seconds=int(to_s)
            )
            if (
                abs((candidate_start - local_start).total_seconds()) <= 180
                and abs((candidate_end - local_end).total_seconds()) <= 180
            ):
                return candidate, True
        return None, False

    # -- GTFS alert matching -------------------------------------------
    def _alert_time_overlaps(
        self,
        alert: DisruptionRecord,
        start: datetime | None,
        end: datetime | None,
    ) -> bool:
        if start is None or end is None:
            return False
        if alert.published_at > end:
            return False
        if alert.valid_from > end:
            return False
        if alert.valid_to is not None and alert.valid_to < start:
            return False
        duration = max(0.0, (end - start).total_seconds())
        step = 180 if duration <= 4 * 3600 else 900
        samples = {start, end}
        for boundary in (alert.valid_from, alert.valid_to):
            if boundary is not None and start <= boundary <= end:
                samples.add(boundary)
        cursor = start
        while cursor <= end and len(samples) < 600:
            samples.add(cursor)
            cursor += timedelta(seconds=step)
        return any(alert.is_temporally_applicable(sample) for sample in samples)

    def _alert_overlaps(
        self,
        alert: DisruptionRecord,
        start: datetime | None,
        end: datetime | None,
        service_date: date | None,
    ) -> bool:
        if not self._alert_time_overlaps(alert, start, end):
            return False
        if start is None or end is None:
            return False
        duration = max(0.0, (end - start).total_seconds())
        step = 180 if duration <= 4 * 3600 else 900
        samples = {start, end}
        cursor = start
        while cursor <= end and len(samples) < 600:
            samples.add(cursor)
            cursor += timedelta(seconds=step)
        return any(alert.is_applicable_at(sample, service_date=service_date) for sample in samples)

    def _evaluate_gtfs_alert(
        self,
        assessment: ItineraryAssessment,
        leg_index: int,
        context: dict[str, Any],
        alert: DisruptionRecord,
    ) -> None:
        if alert.effect is DisruptionEffect.INFO:
            return
        if not self._alert_time_overlaps(alert, context.get("start"), context.get("end")):
            return
        for link in alert.links:
            if not link.is_current:
                continue
            if link.resolution_status is not ResolutionStatus.RESOLVED:
                continue
            if link.entity_type in (LinkEntityType.OSM_WAY, LinkEntityType.OSM_POI):
                continue
            matched, uncertainty = self._link_matches_leg(link, context)
            if not matched:
                continue
            if uncertainty:
                assessment.add_impact(
                    self._impact(
                        leg_index,
                        context,
                        alert,
                        "uncertain",
                        uncertainty,
                        link,
                    )
                )
                continue
            impact_type = "blocked" if alert.effect is DisruptionEffect.BLOCK else "penalized"
            assessment.add_impact(
                self._impact(
                    leg_index,
                    context,
                    alert,
                    impact_type,
                    f"{link.entity_type.value}_match",
                    link,
                )
            )

        # Unresolved/ambiguous links can be candidates when the raw reference
        # matches the leg's public labels. They are never promoted to a block.
        for link in alert.links:
            if not link.is_current or link.resolution_status is not ResolutionStatus.UNRESOLVED:
                continue
            if self._raw_reference_matches_leg(link.raw_reference, context):
                assessment.add_impact(
                    self._impact(
                        leg_index,
                        context,
                        alert,
                        "uncertain",
                        "riferimento_non_risolto_ma_compatibile",
                        link,
                    )
                )

    def _link_matches_leg(
        self, link: DisruptionLinkRecord, context: dict[str, Any]
    ) -> tuple[bool, str | None]:
        dataset = context.get("dataset")
        if link.dataset_key and dataset and link.dataset_key != dataset:
            return False, None
        if link.mode and context.get("mode"):
            link_mode = link.mode.strip().casefold()
            leg_mode = str(context["mode"]).strip().casefold()
            if link_mode not in {"road", "any"} and link_mode != leg_mode:
                return False, None
        if link.direction and link.direction.value in {"forward", "backward"}:
            if context.get("direction") is None:
                return True, "direzione_non_verificata"
            if link.direction.value != context.get("direction"):
                return False, None
        if link.service_date is not None:
            if context.get("service_date") is None:
                return True, "service_date_non_verificata"
            if link.service_date != context.get("service_date"):
                return False, None
        if link.entity_type is LinkEntityType.ROUTE:
            return str(link.entity_id) == context.get("route_id"), None
        if link.entity_type is LinkEntityType.TRIP:
            return str(link.entity_id) == context.get("trip_id"), None
        if link.entity_type is LinkEntityType.STOP:
            if str(link.entity_id) not in context.get("stop_ids", []):
                return False, None
            if link.from_stop_id or link.to_stop_id:
                leg_from = context.get("from_sequence")
                leg_to = context.get("to_sequence")
                link_from = link.from_stop_sequence
                link_to = link.to_stop_sequence
                sequences = context.get("stop_sequences", {})
                if link_from is None and link.from_stop_id:
                    link_from = sequences.get(str(link.from_stop_id))
                if link_to is None and link.to_stop_id:
                    link_to = sequences.get(str(link.to_stop_id))
                if (
                    leg_from is not None
                    and leg_to is not None
                    and link_from is not None
                    and link_to is not None
                ):
                    low, high = sorted((leg_from, leg_to))
                    link_low, link_high = sorted((link_from, link_to))
                    if link_high < low or link_low > high:
                        return False, None
            return True, None
        return False, None

    def _raw_reference_matches_leg(self, raw: str, context: dict[str, Any]) -> bool:
        if not raw:
            return False
        from app.services.ingestion.resolver import normalize_name, normalize_route_ref

        route_ref = normalize_route_ref(raw)
        route_label = normalize_route_ref(
            str(
                (context.get("route") or {}).get("route_short_name")
                or context.get("route_id")
                or ""
            )
        )
        if route_ref and route_label and route_ref == route_label:
            return True
        text = normalize_name(raw)
        for stop_id in context.get("stop_ids", []):
            dataset = context.get("dataset")
            if not dataset:
                continue
            stop = self._gtfs.stop(dataset, stop_id)
            if stop and text and text in normalize_name(str(stop.get("stop_name") or "")):
                return True
        return False

    def _impact(
        self,
        leg_index: int,
        context: dict[str, Any],
        alert: DisruptionRecord,
        impact_type: str,
        reason: str,
        link: DisruptionLinkRecord,
        *,
        overlap_m: float | None = None,
        distance_m: float | None = None,
    ) -> LegImpact:
        return LegImpact(
            leg_index=leg_index,
            mode=str(context.get("mode") or ""),
            transit_leg=bool(context.get("transit")),
            impact=impact_type,
            reason=reason,
            source_id=alert.source_id,
            alert_id=alert.alert_id,
            title=alert.title,
            effect=alert.effect.value,
            valid_from=alert.valid_from,
            valid_to=alert.valid_to,
            entity_type=link.entity_type.value,
            entity_id=str(link.entity_id),
            dataset_key=link.dataset_key or context.get("dataset"),
            route_id=context.get("route_id"),
            trip_id=context.get("trip_id"),
            from_stop_id=context.get("from_stop_id"),
            to_stop_id=context.get("to_stop_id"),
            service_date=context.get("service_date"),
            overlap_m=overlap_m,
            distance_m=distance_m,
            uncertainty=alert.uncertainty.value,
            details=dict(link.details or {}),
        )

    def _uncertain_impact(
        self,
        leg_index: int,
        context: dict[str, Any],
        alert: DisruptionRecord | None,
        reason: str,
    ) -> LegImpact:
        return LegImpact(
            leg_index=leg_index,
            mode=str(context.get("mode") or ""),
            transit_leg=bool(context.get("transit")),
            impact="uncertain",
            reason=reason,
            source_id=alert.source_id if alert else "incidents",
            alert_id=alert.alert_id if alert else "unknown",
            title=alert.title if alert else "",
            effect=alert.effect.value if alert else "unknown",
            valid_from=alert.valid_from if alert else datetime.now(timezone.utc),
            valid_to=alert.valid_to if alert else None,
            dataset_key=context.get("dataset"),
            route_id=context.get("route_id"),
            trip_id=context.get("trip_id"),
            from_stop_id=context.get("from_stop_id"),
            to_stop_id=context.get("to_stop_id"),
            service_date=context.get("service_date"),
            uncertainty=alert.uncertainty.value if alert else "high",
        )

    def _alerts_may_touch_leg(
        self, alerts: list[DisruptionRecord], context: dict[str, Any]
    ) -> bool:
        return any(
            self._alert_time_overlaps(
                alert,
                context.get("start"),
                context.get("end"),
            )
            for alert in alerts
        )

    # -- OSM road closure checks ---------------------------------------
    def _load_way_rows(self, alerts: list[DisruptionRecord]) -> dict[str, dict[str, Any]]:
        keys: set[str] = set()
        for alert in alerts:
            if alert.effect is DisruptionEffect.INFO:
                continue
            for link in alert.links:
                if (
                    link.entity_type is LinkEntityType.OSM_WAY
                    and link.resolution_status is ResolutionStatus.RESOLVED
                    and link.entity_id
                ):
                    keys.add(str(link.entity_id))
        if not keys:
            return {}
        rows = self._territory.get_ways_by_keys(sorted(keys))
        return {str(row["osm_key"]): row for row in rows}

    def _evaluate_road_alerts(
        self,
        assessment: ItineraryAssessment,
        leg_index: int,
        leg: dict[str, Any],
        context: dict[str, Any],
        alerts: list[DisruptionRecord],
        way_rows: dict[str, dict[str, Any]],
    ) -> None:
        if not alerts:
            return
        mode = _mode(leg.get("mode"))
        if mode in RAIL_MODES:
            return
        points, geometry_source = leg_polyline(leg)
        wkt = line_wkt(points)
        endpoints = (
            [
                (float(leg.get("from_lat")), float(leg.get("from_lon"))),
                (float(leg.get("to_lat")), float(leg.get("to_lon"))),
            ]
            if all(
                isinstance(leg.get(key), (int, float))
                for key in ("from_lat", "from_lon", "to_lat", "to_lon")
            )
            else []
        )
        for alert in alerts:
            if alert.effect is DisruptionEffect.INFO:
                continue
            if not self._alert_time_overlaps(alert, context.get("start"), context.get("end")):
                continue
            for link in alert.links:
                if not link.is_current or link.entity_type is not LinkEntityType.OSM_WAY:
                    continue
                if link.resolution_status is not ResolutionStatus.RESOLVED or not link.entity_id:
                    continue
                if link.mode and link.mode.casefold() not in {
                    "road",
                    "any",
                    mode.casefold(),
                }:
                    continue
                way_key = str(link.entity_id)
                way = way_rows.get(way_key)
                if way is None:
                    assessment.road_checks.append(
                        RoadCheck(
                            leg_index,
                            mode,
                            alert.alert_id,
                            alert.source_id,
                            way_key,
                            "ambiguous",
                            reason="way non presente nel catalogo corrente",
                        )
                    )
                    assessment.add_impact(
                        self._impact(
                            leg_index,
                            context,
                            alert,
                            "uncertain",
                            "osm_way_non_risolta",
                            link,
                        )
                    )
                    continue
                way_points = _wkt_points(way.get("geometry"))
                if not way_points:
                    assessment.road_checks.append(
                        RoadCheck(
                            leg_index,
                            mode,
                            alert.alert_id,
                            alert.source_id,
                            way_key,
                            "ambiguous",
                            reason="geometria OSM assente",
                        )
                    )
                    continue
                if geometry_source == "missing" or wkt is None:
                    near = any(
                        distance_to_polyline_m(lat, lon, way_points) <= 1000.0
                        for lat, lon in endpoints
                    )
                    if near:
                        assessment.road_checks.append(
                            RoadCheck(
                                leg_index,
                                mode,
                                alert.alert_id,
                                alert.source_id,
                                way_key,
                                "missing_geometry",
                                reason="leg senza geometria vicino alla way chiusa",
                            )
                        )
                        assessment.add_impact(
                            self._impact(
                                leg_index,
                                context,
                                alert,
                                "uncertain",
                                "geometria_leg_mancante",
                                link,
                            )
                        )
                    continue
                tunnel = str(way.get("tunnel") or "").casefold() in {
                    "yes",
                    "covered",
                    "building_passage",
                }
                bridge = str(way.get("bridge") or "").casefold() == "yes"
                layer = str(way.get("layer") or "0").strip()
                layered = layer not in {"", "0"}
                if tunnel or bridge or layered:
                    nearby = _polyline_distance_m(points, way_points) <= 60.0
                    if nearby:
                        assessment.road_checks.append(
                            RoadCheck(
                                leg_index,
                                mode,
                                alert.alert_id,
                                alert.source_id,
                                way_key,
                                "tunnel_bridge",
                                reason=(
                                    f"way con tunnel={way.get('tunnel')} "
                                    f"bridge={way.get('bridge')} layer={way.get('layer')}: "
                                    "non si presume un blocco in superficie"
                                ),
                            )
                        )
                    continue
                try:
                    measured = self._territory.measure_corridor_overlap(way_key, wkt, buffer_m=20.0)
                except Exception as exc:  # noqa: BLE001 - geometry failure is uncertainty
                    assessment.road_checks.append(
                        RoadCheck(
                            leg_index,
                            mode,
                            alert.alert_id,
                            alert.source_id,
                            way_key,
                            "ambiguous",
                            reason=f"misura geometria fallita: {type(exc).__name__}",
                        )
                    )
                    assessment.add_impact(
                        self._impact(
                            leg_index,
                            context,
                            alert,
                            "uncertain",
                            "geometria_non_verificabile",
                            link,
                        )
                    )
                    continue
                if measured is None:
                    continue
                overlap = measured["overlap_m"]
                distance = measured["distance_m"]
                threshold = 12.0 if mode in WALK_LIKE else 30.0
                if overlap >= threshold:
                    status = "along"
                    impact_type = (
                        "blocked" if alert.effect is DisruptionEffect.BLOCK else "penalized"
                    )
                    assessment.road_checks.append(
                        RoadCheck(
                            leg_index,
                            mode,
                            alert.alert_id,
                            alert.source_id,
                            way_key,
                            status,
                            overlap,
                            distance,
                            f"leg lungo la way chiusa per {overlap:.1f} m",
                        )
                    )
                    assessment.add_impact(
                        self._impact(
                            leg_index,
                            context,
                            alert,
                            impact_type,
                            "road_closure_along_leg",
                            link,
                            overlap_m=overlap,
                            distance_m=distance,
                        )
                    )
                elif distance <= 50.0:
                    status = "crossing"
                    assessment.road_checks.append(
                        RoadCheck(
                            leg_index,
                            mode,
                            alert.alert_id,
                            alert.source_id,
                            way_key,
                            status,
                            overlap,
                            distance,
                            "intersezione 2D: candidato, non prova di blocco",
                        )
                    )
                    if mode in WALK_LIKE or overlap > 3.0:
                        assessment.add_impact(
                            self._impact(
                                leg_index,
                                context,
                                alert,
                                "uncertain",
                                "road_closure_crossing",
                                link,
                                overlap_m=overlap,
                                distance_m=distance,
                            )
                        )
                else:
                    assessment.road_checks.append(
                        RoadCheck(
                            leg_index,
                            mode,
                            alert.alert_id,
                            alert.source_id,
                            way_key,
                            "clear",
                            overlap,
                            distance,
                            "leg distante dalla way chiusa",
                        )
                    )


__all__ = ["IncidentAgent", "SURFACE_MODES", "RAIL_MODES"]
