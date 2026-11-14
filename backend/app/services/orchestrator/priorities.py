"""Priority mapping P1 > P2 > P3 for orchestrator conflict resolution."""

from __future__ import annotations

from app.domain.logic.priorities import PRIORITY_ORDER, PurePriorityWinner, resolve_priority_pure
from app.domain.models.finding import AgentName


def resolve_priority(agents: list[AgentName]) -> PurePriorityWinner:
    """Resolve winning priority across a list of agents."""
    return resolve_priority_pure(agents)


def priority_label_for_agent(agent: AgentName) -> tuple[str, str]:
    """Return (P-code, Italian label) for an agent."""
    code, _, label = PRIORITY_ORDER[agent]
    return code, label

