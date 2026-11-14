"""Pure domain models for Decision, Trigger, Conflict, PlanItem, and ReasoningStep."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.models.finding import AgentName


class RuleId(StrEnum):
    """Declared deterministic orchestrator rule identifiers."""

    R1_LINE2_CROWDING = "R1_line2_crowding"
    R2_CONFLICT_ROUTE_VS_DENSITY = "R2_conflict_route_vs_density"
    R3_WEATHER_CAPACITY = "R3_weather_capacity"
    R4_EVENT_SURGE = "R4_event_surge"


class PlanTarget(StrEnum):
    """Allowed plan recipient targets."""

    OPERATOR = "operator"
    TOURIST = "tourist"
    CITIZEN = "citizen"


DECLARED_RULE_CONSTANTS: frozenset[str] = frozenset(
    {
        *(r.value for r in RuleId),
        "P1",
        "P2",
        "P3",
        "NONE",
        "NO_CONFLICT",
        "MONITORING",
        "PLAN_SYNTHESIS",
        "INITIAL_INGESTION",
    }
)


class Trigger(BaseModel):
    """Dominant trigger rule and involved agents."""

    model_config = ConfigDict(extra="forbid")

    rule_id: RuleId
    agents_involved: list[AgentName] = Field(min_length=1)


class Conflict(BaseModel):
    """Conflict status and explanation."""

    model_config = ConfigDict(extra="forbid")

    detected: bool
    description: str = Field(min_length=1)


class PlanItem(BaseModel):
    """Action item addressed to one of the three plan targets."""

    model_config = ConfigDict(extra="forbid")

    priority: int = Field(ge=1)
    action: str = Field(min_length=1)
    target: PlanTarget
    rationale: str = Field(min_length=1)


class ReasoningStep(BaseModel):
    """Single step in Decision.reasoning_log."""

    model_config = ConfigDict(extra="forbid")

    step: int = Field(ge=1)
    agent: str = Field(min_length=1)
    finding_ref: str = Field(min_length=1)
    rule_applied: str = Field(min_length=1)
    outcome: str = Field(min_length=1)

    @field_validator("rule_applied")
    @classmethod
    def _validate_rule_applied(cls, value: str) -> str:
        if value not in DECLARED_RULE_CONSTANTS:
            raise ValueError(f"rule_applied '{value}' non e' un ID regola o costante dichiarata")
        return value


class Decision(BaseModel):
    """Frozen 6-field Decision contract model."""

    model_config = ConfigDict(extra="forbid")

    trigger: Trigger
    conflict: Conflict
    plan: list[PlanItem] = Field(min_length=1)
    reasoning_log: list[ReasoningStep] = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    timestamp: datetime

    @field_validator("timestamp", mode="after")
    @classmethod
    def _coerce_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
