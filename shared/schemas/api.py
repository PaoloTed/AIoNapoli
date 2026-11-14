"""Shared API envelope schemas, RelevanceScore, Narrative, Refusal, and ProblemDetail."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_serializer

from app.domain.models.decision import Decision, PlanTarget
from app.domain.models.finding import Finding
from app.domain.models.refusal import REFUSAL_CODES, Refusal

CONTRACT_VERSION = "1.0.0"


class Contribution(BaseModel):
    model_config = ConfigDict(extra="forbid")

    feature: str
    value: float
    weight: float
    contribution: float


class ScoredItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_index: int = Field(ge=0)
    score: float = Field(ge=0.0, le=1.0)
    contributions: list[Contribution]


class TargetRelevance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    order: list[int]
    items: list[ScoredItem]


class RelevanceScore(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rounding: int = Field(default=4, ge=0, le=8)
    targets: dict[PlanTarget, TargetRelevance]


class NarrativeTexts(BaseModel):
    model_config = ConfigDict(extra="forbid")

    it: str = Field(min_length=1)
    en: str | None = None

    @model_serializer
    def _serialize(self) -> dict[str, str]:
        data = {"it": self.it}
        if self.en is not None:
            data["en"] = self.en
        return data


class NarrativeItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_index: int = Field(ge=0)
    texts: NarrativeTexts


class Narrative(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: Literal["replay", "live", "off"]
    items: list[NarrativeItem] = Field(default_factory=list)


class VehiclePosition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    vehicle_id: str = Field(min_length=1)
    route_id: str | None = None
    latitude: float
    longitude: float
    bearing: float | None = None
    observed_at: datetime
    source_id: str = Field(min_length=1)
    is_simulated: bool


class FindingResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_version: str = CONTRACT_VERSION
    finding: Finding
    finding_ref: str = Field(min_length=1)


class DecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scenario_id: str | None = None
    findings: list[dict[str, Any]] | None = None


class DecisionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_version: str = CONTRACT_VERSION
    decision_id: str = Field(min_length=1)
    decision: Decision
    relevance: RelevanceScore
    narrative: Narrative


class ScenarioResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_version: str = CONTRACT_VERSION
    scenario_id: str
    title: str
    findings: list[Finding]
    vehicle_positions: list[VehiclePosition] = Field(default_factory=list)


class ProblemDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    title: str
    status: int
    code: str
    field: str | None = None
    detail: str
    instance: str
    refusal: Refusal | None = None


__all__ = [
    "CONTRACT_VERSION",
    "Contribution",
    "DecisionRequest",
    "DecisionResponse",
    "FindingResponse",
    "Narrative",
    "NarrativeItem",
    "NarrativeTexts",
    "ProblemDetail",
    "REFUSAL_CODES",
    "Refusal",
    "RelevanceScore",
    "ScenarioResponse",
    "ScoredItem",
    "TargetRelevance",
    "VehiclePosition",
]
