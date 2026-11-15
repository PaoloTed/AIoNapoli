"""HTTP contract for coordinate-based travel planning through OTP."""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.services.agents.mobility.otp_client import (
    DEFAULT_MODES,
    DIRECT_MODES,
    TRANSIT_MODES,
)

CONTRACT_VERSION = "1.0.0"


class Coordinate(BaseModel):
    """WGS84 coordinate with explicit finite ranges."""

    model_config = ConfigDict(extra="forbid")

    lat: float = Field(ge=-90.0, le=90.0, allow_inf_nan=False)
    lon: float = Field(ge=-180.0, le=180.0, allow_inf_nan=False)

    @field_validator("lat", "lon")
    @classmethod
    def _finite(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("coordinata non finita")
        return value


class JourneyPreferences(BaseModel):
    """Preferences that are actually verifiable on OTP results."""

    model_config = ConfigDict(extra="forbid")

    minimize_walk: bool = False
    minimize_transfers: bool = False
    modes: list[str] = Field(default_factory=lambda: list(DEFAULT_MODES))
    unsupported_constraints: list[str] = Field(default_factory=list)

    @field_validator("modes")
    @classmethod
    def _known_modes(cls, value: list[str]) -> list[str]:
        normalized = [str(mode).strip().upper() for mode in value if str(mode).strip()]
        if not normalized:
            raise ValueError("modes non puo' essere vuoto")
        unknown = sorted({mode for mode in normalized if mode not in DIRECT_MODES | TRANSIT_MODES})
        if unknown:
            raise ValueError(f"modalita OTP non supportate: {unknown}")
        if not any(mode in TRANSIT_MODES for mode in normalized):
            raise ValueError("serve almeno una modalita di trasporto pubblico")
        return normalized


class JourneyPlanRequest(BaseModel):
    """Validated travel-planning input.

    Exactly one of ``depart_at`` and ``arrive_by`` is required. A naive
    datetime is interpreted in ``timezone``; an offset-aware datetime keeps its
    own offset.
    """

    model_config = ConfigDict(extra="forbid")

    origin: Coordinate
    destination: Coordinate
    depart_at: datetime | None = None
    arrive_by: datetime | None = None
    timezone: str = "Europe/Rome"
    modes: list[str] = Field(default_factory=lambda: list(DEFAULT_MODES))
    transit_only: bool = False
    first: int = Field(default=5, ge=1, le=20)
    preferences: JourneyPreferences | None = None

    @field_validator("timezone")
    @classmethod
    def _known_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"timezone sconosciuta: {value}") from exc
        return value

    @field_validator("modes")
    @classmethod
    def _known_modes(cls, value: list[str]) -> list[str]:
        if isinstance(value, str):
            raise ValueError("modes deve essere una lista")
        normalized = [str(mode).strip().upper() for mode in value if str(mode).strip()]
        if not normalized:
            raise ValueError("modes non puo' essere vuoto")
        unknown = sorted({mode for mode in normalized if mode not in DIRECT_MODES | TRANSIT_MODES})
        if unknown:
            raise ValueError(f"modalita OTP non supportate: {unknown}")
        if not any(mode in TRANSIT_MODES for mode in normalized):
            raise ValueError("serve almeno una modalita di trasporto pubblico")
        return normalized

    @model_validator(mode="after")
    def _exactly_one_time(self) -> JourneyPlanRequest:
        if (self.depart_at is None) == (self.arrive_by is None):
            raise ValueError("specificare depart_at oppure arrive_by, non entrambi")
        return self


class JourneySource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(min_length=1)
    data_reference: str = Field(min_length=1)
    is_simulated: bool


class JourneyLeg(BaseModel):
    """One normalized OTP leg, including feed-scoped and original IDs."""

    model_config = ConfigDict(extra="forbid")

    mode: str
    transit_leg: bool
    duration_s: float | None = None
    start_scheduled: str | None = None
    start_estimated: str | None = None
    start_delay_s: int | float | None = None
    end_scheduled: str | None = None
    end_estimated: str | None = None
    end_delay_s: int | float | None = None
    route: str | None = None
    route_id: str | None = None
    route_short_name: str | None = None
    route_long_name: str | None = None
    route_mode: str | None = None
    agency_id: str | None = None
    agency_gtfs_id: str | None = None
    agency_name: str | None = None
    operator: str | None = None
    trip_id: str | None = None
    from_stop_id: str | None = None
    to_stop_id: str | None = None
    from_name: str | None = None
    to_name: str | None = None
    from_lat: float | None = None
    from_lon: float | None = None
    to_lat: float | None = None
    to_lon: float | None = None
    geometry: str | None = None
    geometry_length: int | None = None


class ClarificationCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    candidate_id: str = Field(min_length=1)
    label: str = Field(min_length=1)
    lat: float | None = None
    lon: float | None = None
    source: str = Field(min_length=1)
    approximate: bool = False
    detail: str | None = None


class Clarification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    clarification_id: str = Field(min_length=1)
    role: Literal["origin", "destination", "origin_destination", "time", "preference"]
    question: str = Field(min_length=1)
    candidates: list[ClarificationCandidate] = Field(default_factory=list)


class ResolvedPlace(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["origin", "destination", "client_location"]
    label: str = Field(min_length=1)
    lat: float
    lon: float
    source: str = Field(min_length=1)
    entity_id: str | None = None
    approximate: bool = False
    detail: str | None = None


class PromptInterpretation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    origin_text: str | None = None
    destination_text: str | None = None
    depart_at: datetime | None = None
    arrive_by: datetime | None = None
    preferences: JourneyPreferences = Field(default_factory=JourneyPreferences)
    transit_only: bool = False
    parser: Literal["llm", "deterministic"] = "deterministic"
    warnings: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    uses_client_location: bool = False
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class LegImpact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    leg_index: int = Field(ge=0)
    mode: str
    transit_leg: bool
    impact: Literal["blocked", "penalized", "uncertain"]
    reason: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    alert_id: str = Field(min_length=1)
    title: str = ""
    effect: str = "block"
    valid_from: str | None = None
    valid_to: str | None = None
    entity_type: str | None = None
    entity_id: str | None = None
    dataset_key: str | None = None
    route_id: str | None = None
    trip_id: str | None = None
    from_stop_id: str | None = None
    to_stop_id: str | None = None
    service_date: str | None = None
    overlap_m: float | None = None
    distance_m: float | None = None
    uncertainty: str | None = None


class ItineraryImpact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    itinerary_index: int = Field(ge=0)
    blocked: bool = False
    penalized: bool = False
    uncertain: bool = False
    material_uncertainty: bool = False
    impacts: list[LegImpact] = Field(default_factory=list)
    excluded_route_ids: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class AvoidedProblem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str
    alert_id: str
    title: str
    effect: str
    valid_from: str | None = None
    valid_to: str | None = None
    reason: str


class JourneySourceInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str
    alert_id: str
    data_reference: str
    title: str
    is_simulated: bool
    lifecycle_status: str
    verification_status: str
    uncertainty: str
    effect: str
    valid_from: str
    valid_to: str | None = None
    published_at: str
    ingested_at: str
    age_s: int | None = None


class AgentTraceEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    agent: str
    status: str
    detail: str
    data: dict[str, Any] = Field(default_factory=dict)


class JourneyCoverage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    routing_calls: int = 0
    max_plans: int = 3
    budget_s: float = 15.0
    budget_exceeded: bool = False
    disruptions_considered: int = 0
    simulated_excluded: bool = True
    road_closures_checked: int = 0
    unresolved_alerts: int = 0
    reason: str | None = None
    warnings: list[str] = Field(default_factory=list)


class JourneyItinerary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    index: int = Field(ge=0)
    start: str | None = None
    end: str | None = None
    duration_s: int | None = None
    walk_time_s: int | None = None
    walk_distance_m: float | None = None
    transfers: int | None = None
    generalized_cost: int | None = None
    legs: list[JourneyLeg] = Field(default_factory=list)
    verified: bool = True
    penalized: bool = False
    impacts: list[LegImpact] = Field(default_factory=list)


class JourneyPlanResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_version: str = CONTRACT_VERSION
    status: Literal[
        "ok",
        "no_route",
        "no_verified_route",
        "insufficient_data",
    ] = "ok"
    timezone: str
    itineraries: list[JourneyItinerary] = Field(default_factory=list)
    unverified_itineraries: list[JourneyItinerary] = Field(default_factory=list)
    best_itinerary_index: int | None = None
    routing_errors: list[dict[str, Any]] = Field(default_factory=list)
    source: JourneySource
    impacts: list[ItineraryImpact] = Field(default_factory=list)
    avoided_problems: list[AvoidedProblem] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    sources: list[JourneySourceInfo] = Field(default_factory=list)
    agent_trace: list[AgentTraceEntry] = Field(default_factory=list)
    coverage: JourneyCoverage = Field(default_factory=JourneyCoverage)
    resolved_places: list[ResolvedPlace] = Field(default_factory=list)
    clarification: Clarification | None = None
    request_interpretation: PromptInterpretation | None = None


class JourneyPromptRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt: str = Field(min_length=3, max_length=4000)
    client_location: Coordinate | None = None
    timezone: str = "Europe/Rome"
    first: int | None = Field(default=None, ge=1, le=20)
    context: dict[str, Any] = Field(default_factory=dict)

    @field_validator("timezone")
    @classmethod
    def _known_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"timezone sconosciuta: {value}") from exc
        return value


class JourneyPromptResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_version: str = CONTRACT_VERSION
    status: Literal[
        "ok",
        "no_route",
        "no_verified_route",
        "insufficient_data",
        "needs_clarification",
        "place_not_found",
        "invalid_request",
    ]
    timezone: str
    prompt: str
    interpretation: PromptInterpretation
    clarification: Clarification | None = None
    resolved_places: list[ResolvedPlace] = Field(default_factory=list)
    journey: JourneyPlanResponse | None = None


__all__ = [
    "CONTRACT_VERSION",
    "AgentTraceEntry",
    "AvoidedProblem",
    "Clarification",
    "ClarificationCandidate",
    "Coordinate",
    "ItineraryImpact",
    "JourneyCoverage",
    "JourneyItinerary",
    "JourneyLeg",
    "JourneyPlanRequest",
    "JourneyPlanResponse",
    "JourneyPreferences",
    "JourneyPromptRequest",
    "JourneyPromptResponse",
    "JourneySource",
    "JourneySourceInfo",
    "LegImpact",
    "PromptInterpretation",
    "ResolvedPlace",
]
