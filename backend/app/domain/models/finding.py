"""Pure domain models for Finding and contract enums."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class AgentName(StrEnum):
    """Supported specialized agents."""

    MOBILITY = "mobility"
    CROWDING = "crowding"
    CONTEXT = "context"


class FindingType(StrEnum):
    """Allowed finding types across the three agents."""

    ROUTE_DISRUPTION = "route_disruption"
    ROUTE_ALTERNATIVE = "route_alternative"
    DENSITY_ALERT = "density_alert"
    IMPACT_ASSESSMENT = "impact_assessment"


class Severity(StrEnum):
    """Normalized severity levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


SEVERITY_ORDER: dict[Severity, int] = {
    Severity.LOW: 1,
    Severity.MEDIUM: 2,
    Severity.HIGH: 3,
    Severity.CRITICAL: 4,
}

AGENT_ALLOWED_TYPES: dict[AgentName, frozenset[FindingType]] = {
    AgentName.MOBILITY: frozenset({FindingType.ROUTE_DISRUPTION, FindingType.ROUTE_ALTERNATIVE}),
    AgentName.CROWDING: frozenset({FindingType.DENSITY_ALERT}),
    AgentName.CONTEXT: frozenset({FindingType.IMPACT_ASSESSMENT}),
}


class Finding(BaseModel):
    """Frozen 9-field Finding contract model."""

    model_config = ConfigDict(extra="forbid")

    agent: AgentName
    type: FindingType
    content: dict[str, Any]
    confidence: float = Field(ge=0.0, le=1.0)
    severity: Severity
    source_id: str = Field(min_length=1)
    data_reference: str = Field(min_length=1)
    is_simulated: bool
    timestamp: datetime

    @field_validator("source_id", "data_reference")
    @classmethod
    def _non_blank_str(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("il campo non puo' essere vuoto")
        return value

    @field_validator("content")
    @classmethod
    def _validate_known_content_fields(cls, value: dict[str, Any]) -> dict[str, Any]:
        if "density" in value and value["density"] is not None:
            density_val = value["density"]
            if (
                isinstance(density_val, bool)
                or not isinstance(density_val, (int, float))
                or not (0.0 <= float(density_val) <= 1.0)
            ):
                raise ValueError("content.density: density deve essere compresa tra 0 e 1")

        if "congestion" in value and value["congestion"] is not None:
            cong_val = value["congestion"]
            if (
                isinstance(cong_val, bool)
                or not isinstance(cong_val, (int, float))
                or not (0.0 <= float(cong_val) <= 1.0)
            ):
                raise ValueError("content.congestion: congestion deve essere compresa tra 0 e 1")

        if "expected_attendance" in value and value["expected_attendance"] is not None:
            att_val = value["expected_attendance"]
            if isinstance(att_val, bool) or not isinstance(att_val, int) or att_val < 0:
                raise ValueError(
                    "content.expected_attendance: expected_attendance deve essere un intero >= 0"
                )

        if "heavy_rain" in value and value["heavy_rain"] is not None:
            if not isinstance(value["heavy_rain"], bool):
                raise ValueError("content.heavy_rain: heavy_rain deve essere booleano")

        return value

    @field_validator("timestamp", mode="after")
    @classmethod
    def _coerce_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @model_validator(mode="after")
    def _validate_agent_type_coherence(self) -> Finding:
        allowed = AGENT_ALLOWED_TYPES[self.agent]
        if self.type not in allowed:
            allowed_str = ", ".join(sorted(t.value for t in allowed))
            raise ValueError(
                f"type '{self.type.value}' non coerente con agente '{self.agent.value}' "
                f"(ammessi: {allowed_str})"
            )
        return self

