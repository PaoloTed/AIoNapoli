"""Pure domain models for routing, waypoints, constraints, and negotiation.

These structures represent the internal exchange between Mobility and Incidents
agents during the negotiation cycle. They do not modify frozen external contracts.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Waypoint(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    lat: float
    lon: float
    kind: Literal["zone", "stop", "poi", "address", "coordinate"]
    resolved_by: Literal["dictionary", "nominatim", "user"]


class RouteLeg(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["walk", "bus", "metro", "tram", "funicular", "rail"]
    route_id: str | None = None
    from_stop: str
    to_stop: str
    departure: datetime
    arrival: datetime
    duration_min: int
    zone_ids: tuple[str, ...] = ()
    from_stop_id: str | None = None
    to_stop_id: str | None = None
    headsign: str | None = None


class LineTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    route_id: str


class StopTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stop_id: str


class ZoneTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    zone_id: str


class SegmentTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    route_id: str
    from_stop: str
    to_stop: str


class TimeWindow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    from_at: datetime | None = None
    to_at: datetime | None = None

    def contains(self, dt: datetime) -> bool:
        """Return True if dt falls within the window boundaries."""
        if self.from_at is not None and dt < self.from_at:
            return False
        if self.to_at is not None and dt > self.to_at:
            return False
        return True

    def overlaps(self, start: datetime, end: datetime) -> bool:
        """Return True if [start, end] overlaps with [from_at, to_at]."""
        win_start = self.from_at
        win_end = self.to_at
        if win_start is not None and end < win_start:
            return False
        if win_end is not None and start > win_end:
            return False
        return True


class TravelConstraint(BaseModel):
    """Applicable constraint emitted by Incidents agent or preloaded from active sources."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["closure", "penalty", "uncertainty"]
    target: LineTarget | StopTarget | ZoneTarget | SegmentTarget
    direction: Literal["inbound", "outbound", "both"] | None = None
    window: TimeWindow = Field(default_factory=TimeWindow)
    applies_at: Literal["engine", "post_filter"] = "engine"
    evidence_ref: str
    source_id: str
    confidence: float = Field(ge=0.0, le=1.0)


class RouteProposal(BaseModel):
    """Itinerary proposal evaluated in the negotiation cycle."""

    model_config = ConfigDict(extra="forbid")

    proposal_id: str
    origin: Waypoint
    destination: Waypoint
    legs: tuple[RouteLeg, ...]
    total_duration_min: int
    transfers: int
    zone_ids: tuple[str, ...]
    route_ids: tuple[str, ...]
    is_simulated: bool
    source_id: str
    data_reference: str
    exclude_applied: tuple[str, ...] = ()
    penalty_applied: bool = False


class Rejection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    proposal_id: str
    iteration: int
    constraints: tuple[TravelConstraint, ...]


class NegotiationOutcome(BaseModel):
    """Final outcome of the negotiation loop between Mobility and Incidents."""

    model_config = ConfigDict(extra="forbid")

    final_proposal: RouteProposal
    iterations: int = Field(ge=1)
    rejected: tuple[Rejection, ...] = ()
    exhausted: bool = False
    uncertain: bool = False
    constraints_applied: tuple[str, ...] = ()
