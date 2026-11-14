"""Shared Decision contract schema."""

from __future__ import annotations

from app.domain.models.decision import (
    DECLARED_RULE_CONSTANTS,
    Conflict,
    Decision,
    PlanItem,
    PlanTarget,
    ReasoningStep,
    RuleId,
    Trigger,
)

DECISION_FIELDS: frozenset[str] = frozenset(
    {
        "trigger",
        "conflict",
        "plan",
        "reasoning_log",
        "confidence",
        "timestamp",
    }
)

__all__ = [
    "Conflict",
    "DECISION_FIELDS",
    "DECLARED_RULE_CONSTANTS",
    "Decision",
    "PlanItem",
    "PlanTarget",
    "ReasoningStep",
    "RuleId",
    "Trigger",
]

