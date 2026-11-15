"""Pure priority mapping P1 > P2 > P3 for conflict resolution."""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.models.finding import AgentName

PRIORITY_ORDER: dict[AgentName, tuple[str, int, str]] = {
    AgentName.CROWDING: ("P1", 1, "sicurezza delle persone"),
    AgentName.MOBILITY: ("P2", 2, "tempo di percorrenza"),
    AgentName.CONTEXT: ("P3", 3, "esperienza e alternative"),
}


@dataclass(frozen=True)
class PurePriorityWinner:
    """Winner of a deterministic priority comparison across active agents."""

    priority_code: str
    rank: int
    label: str
    winner_agent: AgentName
    discarded_agents: tuple[AgentName, ...]


def resolve_priority_pure(agents: list[AgentName]) -> PurePriorityWinner:
    """Select the highest-priority agent according to P1 > P2 > P3."""
    if not agents:
        return PurePriorityWinner(
            priority_code="P3",
            rank=3,
            label="esperienza e alternative",
            winner_agent=AgentName.CONTEXT,
            discarded_agents=(),
        )
    unique_sorted = sorted(set(agents), key=lambda a: PRIORITY_ORDER[a][1])
    winner = unique_sorted[0]
    code, rank, label = PRIORITY_ORDER[winner]
    return PurePriorityWinner(
        priority_code=code,
        rank=rank,
        label=label,
        winner_agent=winner,
        discarded_agents=tuple(unique_sorted[1:]),
    )
