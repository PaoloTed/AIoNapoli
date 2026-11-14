"""Orchestrator internal intermediate data models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field
from shared.schemas.api import Narrative, RelevanceScore

from app.domain.models.decision import Decision, RuleId
from app.domain.models.finding import AgentName
from app.domain.models.trace import Trace


class RuleResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule_id: RuleId
    agents: list[AgentName]
    fired: bool
    reason: str
    zone_id: str | None = None
    missing_fields: list[str] = Field(default_factory=list)
    finding_ref: str = "none"


class Conflict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    detected: bool
    description: str
    zone_id: str | None = None
    conflicting_agents: list[AgentName] = Field(default_factory=list)


class Resolution(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conflict: Conflict
    priority_code: str
    priority_label: str
    winner_agent: AgentName
    discarded_agents: list[AgentName] = Field(default_factory=list)
    discarded_action: str | None = None
    dominant_rule: RuleId
    agents_involved: list[AgentName]


class PipelineOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision_id: str
    decision: Decision
    relevance: RelevanceScore
    narrative: Narrative
    trace: Trace
