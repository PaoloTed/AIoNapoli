"""Journey planning: OTP candidates, persistent disruptions and explicit status."""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import ValidationError
from shared.schemas.journeys import (
    AgentTraceEntry,
    AvoidedProblem,
    ItineraryImpact,
    JourneyCoverage,
    JourneyItinerary,
    JourneyLeg,
    JourneyPlanRequest,
    JourneyPlanResponse,
    JourneyPreferences,
    JourneySource,
    JourneySourceInfo,
    LegImpact,
)

from app.domain.models.config import AppConfig
from app.domain.models.disruption import DisruptionRecord, ResolutionStatus
from app.repositories.disruptions import DisruptionRepository
from app.repositories.territory import OSMTerritoryRepository
from app.services.agents.incidents.evaluator import IncidentAgent
from app.services.agents.incidents.gtfs_queries import GtfsQueries
from app.services.agents.incidents.models import ItineraryAssessment
from app.services.agents.mobility.otp_client import (
    ItineraryPlan,
    ItineraryResult,
    OtpClient,
    OtpGraphQLError,
    OtpHttpError,
    OtpInvalidResponseError,
    OtpNoRouteError,
    OtpTimeoutError,
    OtpUnavailableError,
)
from app.services.agents.mobility.otp_graph import map_feeds_to_datasets
from app.services.validation.finding_validator import ValidationProblem


def _localize(value: datetime, timezone: ZoneInfo) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone)
    return value


def _source(plan: ItineraryPlan) -> JourneySource:
    return JourneySource(
        source_id=plan.source_id,
        data_reference=plan.data_reference,
        is_simulated=plan.is_simulated,
    )


def _map_error(exc: Exception) -> ValidationProblem:
    if isinstance(exc, OtpTimeoutError):
        return ValidationProblem(
            status=504,
            code="otp_timeout",
            title="Routing OTP in timeout",
            detail=str(exc),
        )
    if isinstance(exc, OtpUnavailableError):
        return ValidationProblem(
            status=503,
            code="otp_unavailable",
            title="Routing OTP non disponibile",
            detail=str(exc),
        )
    if isinstance(exc, OtpHttpError):
        return ValidationProblem(
            status=502,
            code="otp_http_error",
            title="Errore HTTP da OTP",
            detail=str(exc),
        )
    if isinstance(exc, OtpGraphQLError):
        return ValidationProblem(
            status=502,
            code="otp_graphql_error",
            title="Errore GraphQL da OTP",
            detail=str(exc),
        )
    if isinstance(exc, OtpInvalidResponseError):
        return ValidationProblem(
            status=502,
            code="otp_invalid_response",
            title="Risposta OTP non valida",
            detail=str(exc),
        )
    if isinstance(exc, (ValueError, TypeError)):
        return ValidationProblem(
            status=422,
            code="invalid_journey_request",
            title="Richiesta di viaggio non valida",
            detail=str(exc),
        )
    return ValidationProblem(
        status=500,
        code="internal_error",
        title="Errore interno",
        detail=f"errore imprevisto: {type(exc).__name__}",
    )


def _itinerary_fingerprint(result: ItineraryResult) -> str:
    parts = [result.start or "", result.end or ""]
    for leg in result.legs:
        parts.extend(
            [
                str(leg.get("mode") or ""),
                str(leg.get("route_id") or ""),
                str(leg.get("trip_id") or ""),
                str(leg.get("from_stop_id") or ""),
                str(leg.get("to_stop_id") or ""),
                str(leg.get("start_scheduled") or ""),
                str(leg.get("end_scheduled") or ""),
            ]
        )
    return "|".join(parts)


def _itinerary_dict(result: ItineraryResult) -> dict[str, Any]:
    return {
        "start": result.start,
        "end": result.end,
        "duration_s": result.duration_s,
        "walk_time_s": result.walk_time_s,
        "walk_distance_m": result.walk_distance_m,
        "transfers": result.transfers,
        "generalized_cost": result.generalized_cost,
        "legs": result.legs,
    }


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _to_leg_impacts(assessment: ItineraryAssessment) -> list[LegImpact]:
    return [
        LegImpact(
            leg_index=impact.leg_index,
            mode=impact.mode,
            transit_leg=impact.transit_leg,
            impact=impact.impact,  # type: ignore[arg-type]
            reason=impact.reason,
            source_id=impact.source_id,
            alert_id=impact.alert_id,
            title=impact.title,
            effect=impact.effect,
            valid_from=impact.valid_from.isoformat(),
            valid_to=impact.valid_to.isoformat() if impact.valid_to else None,
            entity_type=impact.entity_type,
            entity_id=impact.entity_id,
            dataset_key=impact.dataset_key,
            route_id=impact.route_id,
            trip_id=impact.trip_id,
            from_stop_id=impact.from_stop_id,
            to_stop_id=impact.to_stop_id,
            service_date=impact.service_date.isoformat() if impact.service_date else None,
            overlap_m=impact.overlap_m,
            distance_m=impact.distance_m,
            uncertainty=impact.uncertainty,
        )
        for impact in assessment.impacts
    ]


def _to_itinerary_impact(assessment: ItineraryAssessment, new_index: int) -> ItineraryImpact:
    return ItineraryImpact(
        itinerary_index=new_index,
        blocked=assessment.blocked,
        penalized=assessment.penalized,
        uncertain=assessment.uncertain,
        material_uncertainty=assessment.material_uncertainty,
        impacts=_to_leg_impacts(assessment),
        excluded_route_ids=assessment.excluded_route_ids,
        notes=assessment.notes,
    )


class JourneyPlanner:
    """Executes one plan; the orchestrated path also applies persisted alerts."""

    def __init__(
        self,
        config: AppConfig,
        *,
        otp_client: OtpClient | None = None,
        disruption_repository: DisruptionRepository | None = None,
        territory_repository: OSMTerritoryRepository | None = None,
        source_repository: Any | None = None,
        include_simulated: bool = False,
        incident_source_ids: set[str] | None = None,
    ) -> None:
        self.config = config
        self._otp = otp_client or OtpClient(
            base_url=config.otp_base_url,
            timeout_s=config.otp_timeout_s,
            mode=config.routing_mode,
            timezone=config.routing_timezone,
        )
        self._source_repo = source_repository
        self._include_simulated = include_simulated
        self._incidents: IncidentAgent | None = None
        if disruption_repository is not None and territory_repository is not None:
            gtfs = GtfsQueries(disruption_repository.conn, config.gtfs_datasets)
            self._incidents = IncidentAgent(
                disruption_repository,
                gtfs,
                territory_repository,
                config,
                otp_client=self._otp,
                source_ids=incident_source_ids,
            )

    # -- compatibility path used by offline contracts and demo mode ------
    def _plan_simple(
        self,
        request: JourneyPlanRequest,
        depart_at: datetime | None,
        arrive_by: datetime | None,
    ) -> JourneyPlanResponse:
        try:
            plan = self._otp.plan_itineraries(
                from_lat=request.origin.lat,
                from_lon=request.origin.lon,
                to_lat=request.destination.lat,
                to_lon=request.destination.lon,
                depart_at=depart_at,
                arrive_by=arrive_by,
                first=request.first,
                modes=request.modes,
                transit_only=request.transit_only,
            )
        except OtpNoRouteError as exc:
            return JourneyPlanResponse(
                status="no_route",
                timezone=request.timezone,
                itineraries=[],
                routing_errors=exc.routing_errors,
                source=JourneySource(
                    source_id="otp",
                    data_reference=self._otp.endpoint,
                    is_simulated=self._otp.mode == "demo",
                ),
            )
        except (
            OtpTimeoutError,
            OtpUnavailableError,
            OtpHttpError,
            OtpGraphQLError,
            OtpInvalidResponseError,
            ValueError,
            TypeError,
        ) as exc:
            raise _map_error(exc) from exc

        try:
            itineraries = [
                JourneyItinerary(
                    index=index,
                    start=itinerary.start,
                    end=itinerary.end,
                    duration_s=itinerary.duration_s,
                    walk_time_s=itinerary.walk_time_s,
                    walk_distance_m=itinerary.walk_distance_m,
                    transfers=itinerary.transfers,
                    generalized_cost=itinerary.generalized_cost,
                    legs=[JourneyLeg.model_validate(leg) for leg in itinerary.legs],
                )
                for index, itinerary in enumerate(plan.itineraries)
            ]
        except ValidationError as exc:
            raise ValidationProblem(
                status=502,
                code="otp_invalid_response",
                title="Risposta OTP non valida",
                detail=f"itinerario non conforme al contratto: {exc.error_count()} errori",
            ) from exc
        return JourneyPlanResponse(
            status="ok",
            timezone=request.timezone,
            itineraries=itineraries,
            best_itinerary_index=0 if itineraries else None,
            routing_errors=plan.routing_errors,
            source=_source(plan),
            agent_trace=[
                AgentTraceEntry(
                    agent="mobility",
                    status="ok",
                    detail="OTP plan senza applicazione perturbazioni",
                    data={"routing_calls": 1},
                )
            ],
        )

    # -- orchestrated real path -----------------------------------------
    def plan(self, request: JourneyPlanRequest) -> JourneyPlanResponse:
        if self._incidents is None or self._otp.mode == "demo":
            tz = ZoneInfo(request.timezone)
            depart_at = _localize(request.depart_at, tz) if request.depart_at is not None else None
            arrive_by = _localize(request.arrive_by, tz) if request.arrive_by is not None else None
            return self._plan_simple(request, depart_at, arrive_by)

        tz = ZoneInfo(request.timezone)
        depart_at = _localize(request.depart_at, tz) if request.depart_at is not None else None
        arrive_by = _localize(request.arrive_by, tz) if request.arrive_by is not None else None
        now = datetime.now(timezone.utc)
        if depart_at is not None:
            window_start = depart_at.astimezone(tz)
            window_end = window_start + timedelta(hours=6)
        else:
            window_end = (arrive_by or now).astimezone(tz)
            window_start = window_end - timedelta(hours=6)

        preferences = request.preferences or JourneyPreferences(modes=request.modes)
        coverage = JourneyCoverage(
            max_plans=self.config.journey_max_plans,
            budget_s=self.config.journey_budget_s,
            simulated_excluded=not self._include_simulated,
        )
        started = time.monotonic()
        warnings: list[str] = []
        try:
            alerts = self._incidents.load_alerts(
                window_start,
                window_end,
                include_simulated=self._include_simulated,
            )
            datasets_info = self._datasets_info()
            feed_mapping = self._feed_mapping(datasets_info, warnings)
            route_scope_map = self._incidents.route_scope_map(
                feed_mapping=feed_mapping, datasets_info=datasets_info
            )
            constraints, constraint_warnings = self._incidents.initial_constraints(
                alerts,
                start=window_start,
                end=window_end,
                feed_mapping=feed_mapping,
                datasets_info=datasets_info,
                route_scope_map=route_scope_map,
            )
            warnings.extend(constraint_warnings)
        except Exception as exc:  # noqa: BLE001 - explicit insufficient data
            raise ValidationProblem(
                status=503,
                code="disruptions_unavailable",
                title="Perturbazioni non disponibili",
                detail=f"impossibile leggere le perturbazioni persistite: {type(exc).__name__}",
            ) from exc

        exclusions = {constraint.scoped_route_id for constraint in constraints}
        candidates: list[tuple[dict[str, Any], ItineraryAssessment]] = []
        seen: set[str] = set()
        calls = 0
        last_plan: ItineraryPlan | None = None
        routing_errors: list[dict[str, Any]] = []
        while calls < self.config.journey_max_plans and len(candidates) < 100:
            if calls > 0 and time.monotonic() - started > self.config.journey_budget_s:
                coverage.budget_exceeded = True
                warnings.append("budget temporale del routing esaurito")
                break
            try:
                plan = self._otp.plan_itineraries(
                    from_lat=request.origin.lat,
                    from_lon=request.origin.lon,
                    to_lat=request.destination.lat,
                    to_lon=request.destination.lon,
                    depart_at=depart_at,
                    arrive_by=arrive_by,
                    first=request.first or self.config.journey_default_first,
                    modes=request.modes,
                    transit_only=request.transit_only,
                    exclude_route_ids=tuple(sorted(exclusions)),
                )
            except OtpNoRouteError as exc:
                if not candidates:
                    return JourneyPlanResponse(
                        status="no_route",
                        timezone=request.timezone,
                        itineraries=[],
                        routing_errors=exc.routing_errors,
                        source=JourneySource(
                            source_id="otp",
                            data_reference=self._otp.endpoint,
                            is_simulated=False,
                        ),
                        coverage=coverage,
                        agent_trace=[
                            AgentTraceEntry(
                                agent="mobility",
                                status="no_route",
                                detail="OTP non ha restituito itinerari",
                                data={"routing_calls": calls + 1},
                            )
                        ],
                    )
                routing_errors = exc.routing_errors
                break
            except (
                OtpTimeoutError,
                OtpUnavailableError,
                OtpHttpError,
                OtpGraphQLError,
                OtpInvalidResponseError,
            ) as exc:
                raise _map_error(exc) from exc
            calls += 1
            last_plan = plan
            routing_errors = plan.routing_errors
            new_candidates: list[dict[str, Any]] = []
            new_results: list[ItineraryResult] = []
            for result in plan.itineraries:
                fingerprint = _itinerary_fingerprint(result)
                if fingerprint in seen:
                    continue
                seen.add(fingerprint)
                new_candidates.append(_itinerary_dict(result))
                new_results.append(result)
            if not new_candidates:
                break
            try:
                assessments = self._incidents.assess_itineraries(
                    new_candidates,
                    alerts=alerts,
                    feed_mapping=feed_mapping,
                    datasets_info=datasets_info,
                    start=window_start,
                    end=window_end,
                )
            except Exception as exc:  # noqa: BLE001 - explicit data insufficiency
                raise ValidationProblem(
                    status=503,
                    code="incidents_unavailable",
                    title="Verifica imprevisti non disponibile",
                    detail=f"valutazione impatti fallita: {type(exc).__name__}",
                ) from exc
            for candidate, assessment in zip(new_candidates, assessments, strict=False):
                candidates.append((candidate, assessment))
            blocked_routes: set[str] = set()
            for candidate, assessment in zip(new_candidates, assessments, strict=False):
                for impact in assessment.impacts:
                    if impact.impact != "blocked" or not impact.route_id:
                        continue
                    for leg in candidate.get("legs", []):
                        if not isinstance(leg, dict) or not leg.get("transit_leg"):
                            continue
                        scoped_route = leg.get("route_id")
                        if not isinstance(scoped_route, str) or not scoped_route:
                            continue
                        if self._leg_matches_impact_route(leg, impact):
                            blocked_routes.add(scoped_route)
            new_exclusions = blocked_routes - exclusions
            if new_exclusions and calls < self.config.journey_max_plans:
                exclusions |= new_exclusions
                continue
            break

        if not candidates:
            return JourneyPlanResponse(
                status="no_route",
                timezone=request.timezone,
                itineraries=[],
                routing_errors=routing_errors,
                source=JourneySource(
                    source_id="otp",
                    data_reference=self._otp.endpoint,
                    is_simulated=False,
                ),
                coverage=coverage,
                agent_trace=[
                    AgentTraceEntry(
                        agent="mobility",
                        status="no_route",
                        detail="nessun candidato OTP",
                        data={"routing_calls": calls},
                    )
                ],
            )

        verified = [
            (candidate, assessment)
            for candidate, assessment in candidates
            if not assessment.blocked and not assessment.material_uncertainty
        ]
        unverified = [
            (candidate, assessment)
            for candidate, assessment in candidates
            if not assessment.blocked and assessment.material_uncertainty
        ]
        blocked = [
            (candidate, assessment) for candidate, assessment in candidates if assessment.blocked
        ]
        verified.sort(key=lambda item: self._sort_key(item[0], item[1], preferences, arrive_by))
        unverified.sort(key=lambda item: self._sort_key(item[0], item[1], preferences, arrive_by))

        response_itineraries: list[JourneyItinerary] = []
        response_unverified: list[JourneyItinerary] = []
        impacts: list[ItineraryImpact] = []
        for index, (candidate, assessment) in enumerate(verified):
            response_itineraries.append(
                self._to_itinerary(candidate, assessment, index, verified=True)
            )
            impacts.append(_to_itinerary_impact(assessment, index))
        offset = len(response_itineraries)
        for index, (candidate, assessment) in enumerate(unverified, start=offset):
            response_unverified.append(
                self._to_itinerary(candidate, assessment, index, verified=False)
            )
            impacts.append(_to_itinerary_impact(assessment, index))

        status = "ok" if verified else "no_verified_route"
        blocked_reasons: list[str] = []
        for _, assessment in blocked:
            for impact in assessment.impacts:
                if impact.impact == "blocked":
                    blocked_reasons.append(
                        f"{impact.source_id}/{impact.alert_id}: {impact.title or impact.reason} "
                        f"(leg {impact.leg_index}, {impact.reason})"
                    )
        if not verified:
            warnings.append(
                "nessun itinerario verificato: i candidati residui attraversano "
                "o non consentono di escludere un problema attivo"
            )
            warnings.extend(dict.fromkeys(blocked_reasons))

        avoided = self._avoided_problems(blocked, verified, alerts)
        uncertainties = list(warnings)
        for candidate, assessment in unverified:
            for impact in assessment.impacts:
                if impact.impact == "uncertain":
                    uncertainties.append(f"{impact.source_id}/{impact.alert_id}: {impact.reason}")
            for check in assessment.road_checks:
                if check.status in {"crossing", "missing_geometry", "ambiguous", "tunnel_bridge"}:
                    uncertainties.append(
                        f"{check.source_id}/{check.alert_id}: {check.status} su {check.way_key}"
                    )
        uncertainties = list(dict.fromkeys(uncertainties))

        sources = self._source_infos(alerts)
        coverage.routing_calls = calls
        coverage.disruptions_considered = len(alerts)
        coverage.road_closures_checked = sum(
            len(assessment.road_checks) for _, assessment in candidates
        )
        coverage.unresolved_alerts = sum(
            1
            for alert in alerts
            if any(link.resolution_status is not ResolutionStatus.RESOLVED for link in alert.links)
        )
        coverage.reason = (
            None
            if status == "ok"
            else (
                blocked_reasons[0]
                if blocked_reasons
                else "tutti i candidati sono bloccati o non verificabili"
            )
        )
        coverage.warnings = list(dict.fromkeys(warnings))

        source = (
            _source(last_plan)
            if last_plan is not None
            else JourneySource(
                source_id="otp",
                data_reference=self._otp.endpoint,
                is_simulated=False,
            )
        )
        return JourneyPlanResponse(
            status=status,
            timezone=request.timezone,
            itineraries=response_itineraries,
            unverified_itineraries=response_unverified,
            best_itinerary_index=0 if response_itineraries else None,
            routing_errors=routing_errors,
            source=source,
            impacts=impacts,
            avoided_problems=avoided,
            uncertainties=uncertainties,
            sources=sources,
            agent_trace=[
                AgentTraceEntry(
                    agent="mobility",
                    status="ok",
                    detail="itinerari calcolati dal motore OTP",
                    data={"routing_calls": calls, "candidates": len(candidates)},
                ),
                AgentTraceEntry(
                    agent="incidents",
                    status="ok",
                    detail="impatti valutati su GTFS, date di servizio e geometrie OSM",
                    data={
                        "alerts": len(alerts),
                        "blocked_candidates": len(blocked),
                        "unverified_candidates": len(unverified),
                        "road_closures": coverage.road_closures_checked,
                    },
                ),
                AgentTraceEntry(
                    agent="orchestrator",
                    status=status,
                    detail="selezione deterministica dei candidati verificati",
                    data={
                        "selected": 0 if verified else None,
                        "excluded_routes": sorted(exclusions),
                        "avoided": len(avoided),
                    },
                ),
            ],
            coverage=coverage,
        )

    @staticmethod
    def _leg_matches_impact_route(leg: dict[str, Any], impact: Any) -> bool:
        from app.services.agents.mobility.gtfs_ids import parse_otp_id

        route_id = leg.get("route_id")
        trip_id = leg.get("trip_id")
        try:
            _, original_route = parse_otp_id(str(route_id))
        except ValueError:
            original_route = str(route_id)
        try:
            _, original_trip = parse_otp_id(str(trip_id or ""))
        except ValueError:
            original_trip = str(trip_id or "")
        if impact.trip_id:
            return original_trip == impact.trip_id
        return original_route == impact.route_id

    def _datasets_info(self) -> list[dict[str, Any]]:
        if self._source_repo is None:
            return []
        getter = getattr(self._source_repo, "get_datasets_info", None)
        if getter is None:
            return []
        return list(getter())

    def _feed_mapping(
        self, datasets_info: list[dict[str, Any]], warnings: list[str]
    ) -> dict[str, str]:
        if not datasets_info:
            return {}
        try:
            return map_feeds_to_datasets(self._otp.discover_feed_agencies(), datasets_info)
        except Exception as exc:  # noqa: BLE001 - explicit fallback to agency IDs
            warnings.append(
                f"mapping feed OTP non disponibile ({type(exc).__name__}); "
                "uso l'agenzia GTFS dei leg"
            )
            return {}

    def _sort_key(
        self,
        candidate: dict[str, Any],
        assessment: ItineraryAssessment,
        preferences: JourneyPreferences,
        arrive_by: datetime | None,
    ) -> tuple[Any, ...]:
        penalty = 1 if assessment.penalized else 0
        duration = candidate.get("duration_s")
        duration_value = float(duration) if isinstance(duration, (int, float)) else 1e12
        transfers = candidate.get("transfers")
        transfers_value = int(transfers) if isinstance(transfers, int) else 999
        walk = candidate.get("walk_time_s")
        walk_value = int(walk) if isinstance(walk, int) else 10**9
        end = _parse_dt(candidate.get("end"))
        end_value = end.timestamp() if end else 1e18
        if preferences.minimize_walk:
            return (penalty, walk_value, end_value, duration_value, transfers_value)
        if preferences.minimize_transfers:
            return (penalty, transfers_value, end_value, duration_value, walk_value)
        if arrive_by is not None:
            return (penalty, end_value, duration_value, transfers_value, walk_value)
        return (penalty, duration_value, end_value, transfers_value, walk_value)

    def _to_itinerary(
        self,
        candidate: dict[str, Any],
        assessment: ItineraryAssessment,
        index: int,
        *,
        verified: bool,
    ) -> JourneyItinerary:
        try:
            itinerary = JourneyItinerary(
                index=index,
                start=candidate.get("start"),
                end=candidate.get("end"),
                duration_s=candidate.get("duration_s"),
                walk_time_s=candidate.get("walk_time_s"),
                walk_distance_m=candidate.get("walk_distance_m"),
                transfers=candidate.get("transfers"),
                generalized_cost=candidate.get("generalized_cost"),
                legs=[
                    JourneyLeg.model_validate(leg)
                    for leg in candidate.get("legs", [])
                    if isinstance(leg, dict)
                ],
                verified=verified,
                penalized=assessment.penalized,
                impacts=_to_leg_impacts(assessment),
            )
        except ValidationError as exc:
            raise ValidationProblem(
                status=502,
                code="otp_invalid_response",
                title="Risposta OTP non valida",
                detail=f"itinerario non conforme al contratto: {exc.error_count()} errori",
            ) from exc
        return itinerary

    def _avoided_problems(
        self,
        blocked: list[tuple[dict[str, Any], ItineraryAssessment]],
        verified: list[tuple[dict[str, Any], ItineraryAssessment]],
        alerts: list[DisruptionRecord],
    ) -> list[AvoidedProblem]:
        blocked_ids: dict[tuple[str, str], str] = {}
        for _, assessment in blocked:
            for impact in assessment.impacts:
                if impact.impact == "blocked":
                    blocked_ids[(impact.source_id, impact.alert_id)] = impact.title
        chosen_ids = {
            (impact.source_id, impact.alert_id)
            for _, assessment in verified
            for impact in assessment.impacts
            if impact.impact == "blocked"
        }
        result: list[AvoidedProblem] = []
        for alert in alerts:
            key = (alert.source_id, alert.alert_id)
            if key in blocked_ids and key not in chosen_ids:
                result.append(
                    AvoidedProblem(
                        source_id=alert.source_id,
                        alert_id=alert.alert_id,
                        title=alert.title,
                        effect=alert.effect.value,
                        valid_from=alert.valid_from.isoformat(),
                        valid_to=alert.valid_to.isoformat() if alert.valid_to else None,
                        reason="blocco evitato da un itinerario verificato",
                    )
                )
        return result

    def _source_infos(self, alerts: list[DisruptionRecord]) -> list[JourneySourceInfo]:
        now = datetime.now(timezone.utc)
        result: list[JourneySourceInfo] = []
        for alert in alerts[:100]:
            age = (
                int(max(0.0, (now - alert.ingested_at).total_seconds()))
                if alert.ingested_at
                else None
            )
            result.append(
                JourneySourceInfo(
                    source_id=alert.source_id,
                    alert_id=alert.alert_id,
                    data_reference=alert.data_reference,
                    title=alert.title,
                    is_simulated=alert.is_simulated,
                    lifecycle_status=alert.lifecycle_status.value,
                    verification_status=alert.verification_status.value,
                    uncertainty=alert.uncertainty.value,
                    effect=alert.effect.value,
                    valid_from=alert.valid_from.isoformat(),
                    valid_to=alert.valid_to.isoformat() if alert.valid_to else None,
                    published_at=alert.published_at.isoformat(),
                    ingested_at=alert.ingested_at.isoformat(),
                    age_s=age,
                )
            )
        return result


__all__ = ["JourneyPlanner"]
