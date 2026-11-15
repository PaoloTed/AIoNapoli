"""Pure domain model for agent Refusal."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.domain.models.finding import AgentName

REFUSAL_CODES: frozenset[str] = frozenset(
    {
        "missing_gtfs",
        "unmapped_point",
        "out_of_horizon",
        "missing_realtime",
        "no_route",
        "otp_timeout",
        "otp_unavailable",
        "otp_error",
        "missing_occupancy",
        "missing_geofence",
        "invalid_density",
        "missing_alert_level",
        "missing_time_window",
        "unsourced_alert",
    }
)


class Refusal(BaseModel):
    """Structured refusal emitted by an agent when required input is missing or invalid."""

    model_config = ConfigDict(extra="forbid")

    agent: AgentName
    reason_code: str = Field(min_length=1)
    missing_input: list[str]
    detail: str = Field(min_length=1)

