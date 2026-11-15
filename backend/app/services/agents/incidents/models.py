"""Structured output of the Incidents specialist, independent of HTTP schema."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any


@dataclass(frozen=True)
class LegImpact:
    leg_index: int
    mode: str
    transit_leg: bool
    impact: str  # blocked | penalized | uncertain
    reason: str
    source_id: str
    alert_id: str
    title: str
    effect: str
    valid_from: datetime
    valid_to: datetime | None
    entity_type: str | None = None
    entity_id: str | None = None
    dataset_key: str | None = None
    route_id: str | None = None
    trip_id: str | None = None
    from_stop_id: str | None = None
    to_stop_id: str | None = None
    service_date: date | None = None
    overlap_m: float | None = None
    distance_m: float | None = None
    uncertainty: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class RoadCheck:
    leg_index: int
    mode: str
    alert_id: str
    source_id: str
    way_key: str
    status: str  # clear | along | crossing | tunnel_bridge | missing_geometry | ambiguous
    overlap_m: float | None = None
    distance_m: float | None = None
    reason: str = ""


@dataclass
class ItineraryAssessment:
    itinerary_index: int
    blocked: bool = False
    penalized: bool = False
    uncertain: bool = False
    material_uncertainty: bool = False
    impacts: list[LegImpact] = field(default_factory=list)
    road_checks: list[RoadCheck] = field(default_factory=list)
    excluded_route_ids: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def add_impact(self, impact: LegImpact) -> None:
        # Keep the strongest impact for the same alert and leg.
        for index, existing in enumerate(self.impacts):
            if (
                existing.leg_index == impact.leg_index
                and existing.source_id == impact.source_id
                and existing.alert_id == impact.alert_id
            ):
                rank = {"blocked": 3, "penalized": 2, "uncertain": 1}
                if rank[impact.impact] > rank[existing.impact]:
                    self.impacts[index] = impact
                return
        self.impacts.append(impact)

    def finalize(self) -> None:
        self.blocked = any(item.impact == "blocked" for item in self.impacts)
        self.penalized = any(item.impact == "penalized" for item in self.impacts)
        self.uncertain = any(item.impact == "uncertain" for item in self.impacts)
        self.material_uncertainty = self.uncertain or any(
            check.status in {"missing_geometry", "ambiguous"}
            or (check.status == "crossing" and check.mode in {"WALK", "BICYCLE"})
            for check in self.road_checks
        )
        self.excluded_route_ids = sorted(
            {
                route
                for impact in self.impacts
                if impact.impact == "blocked"
                for route in ([impact.route_id] if impact.route_id else [])
            }
        )


@dataclass(frozen=True)
class Constraint:
    route_id: str
    scoped_route_id: str
    dataset_key: str
    source_id: str
    alert_id: str
    reason: str
    scope: str


__all__ = ["Constraint", "ItineraryAssessment", "LegImpact", "RoadCheck"]
