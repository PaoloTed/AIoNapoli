"""Shared Finding contract schema."""

from __future__ import annotations

from app.domain.models.finding import AGENT_ALLOWED_TYPES, AgentName, Finding, FindingType, Severity

FINDING_FIELDS: frozenset[str] = frozenset(
    {
        "agent",
        "type",
        "content",
        "confidence",
        "severity",
        "source_id",
        "data_reference",
        "is_simulated",
        "timestamp",
    }
)

__all__ = [
    "AGENT_ALLOWED_TYPES",
    "AgentName",
    "FINDING_FIELDS",
    "Finding",
    "FindingType",
    "Severity",
]
