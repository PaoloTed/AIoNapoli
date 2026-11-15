"""Base models, protocols, and outcomes for the multi-agent architecture.

Defined in implementations/01_agenti_negoziazione/02_architettura_agentica.md.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field

from app.domain.models.finding import Finding
from app.domain.models.refusal import Refusal


class AgentCapability(StrEnum):
    READ_GTFS = "read_gtfs"
    READ_REALTIME = "read_realtime"
    PLAN_ROUTES = "plan_routes"
    COMPARE_ROUTES = "compare_routes"
    STREET_MAPPER = "street_mapper"
    READ_OCCUPANCY = "read_occupancy"
    FORECAST_EVENTS = "forecast_events"
    ESTIMATE_DENSITY = "estimate_density"
    AGGREGATE_ZONES = "aggregate_zones"
    READ_ALERTS = "read_alerts"
    MAP_WEATHER = "map_weather"
    CHECK_EVENT_WINDOW = "check_event_window"
    ASSESS_IMPACT = "assess_impact"
    VALIDATE_ROUTES = "validate_routes"
    PARSE_REQUEST = "parse_request"


class AgentOutcome(BaseModel):
    """Structured contribution or refusal returned by a specialized worker."""

    model_config = ConfigDict(extra="forbid")

    agent: str
    contributed: bool
    data: dict[str, Any] = Field(default_factory=dict)
    reason: str = ""
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    llm_used: Literal["no", "replay", "live", "fallback"] = "no"
    prompt_version: str = "n/a"
    elapsed_ms: int = 0


class RunContext(BaseModel):
    """Immutable execution context for a single run."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    zone_id: str = "Z_BAGNOLI"
    now: datetime | None = None
    trip_request: Any = None


class WorkerProtocol(Protocol):
    name: str
    capabilities: set[AgentCapability]

    def can_handle(self, ctx: RunContext) -> bool: ...

    def run(self, ctx: RunContext, blackboard: Any) -> AgentOutcome: ...


class SupervisorProtocol(Protocol):
    name: str
    capabilities: set[AgentCapability]

    def can_handle(self, ctx: RunContext) -> bool: ...

    def run(self, ctx: RunContext, blackboard: Any) -> Finding | Refusal: ...
