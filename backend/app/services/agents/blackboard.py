"""Shared blackboard state for multi-agent run (02_architettura_agentica.md §5)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.services.agents.base import AgentCapability, AgentOutcome


class Blackboard(BaseModel):
    """Execution scratchpad tracking worker contributions deterministically."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    contributions: dict[str, AgentOutcome] = Field(default_factory=dict)

    def put(self, outcome: AgentOutcome) -> None:
        """Store an outcome. Overwrites only if the new confidence is strictly higher."""
        existing = self.contributions.get(outcome.agent)
        if existing is None:
            self.contributions[outcome.agent] = outcome
        elif outcome.confidence > existing.confidence:
            self.contributions[outcome.agent] = outcome

    def get(self, agent: str) -> AgentOutcome | None:
        """Return outcome for an agent, or None."""
        return self.contributions.get(agent)

    def value(self, agent: str, key: str, default: Any = None) -> Any:
        """Return a nested value from a worker's data dictionary."""
        outcome = self.contributions.get(agent)
        if outcome is None or not outcome.contributed:
            return default
        return outcome.data.get(key, default)

    def missing(self, capabilities: set[AgentCapability]) -> list[str]:
        """Return human-readable names of required capabilities not met."""
        met: set[AgentCapability] = set()
        for outcome in self.contributions.values():
            if outcome.contributed:
                caps = outcome.data.get("capabilities", [])
                for c in caps:
                    try:
                        met.add(AgentCapability(c))
                    except ValueError:
                        pass
        missing_caps = capabilities - met
        return sorted(str(c.value) for c in missing_caps)

    def rejected(self) -> list[AgentOutcome]:
        """Return all refusal/non-contribution outcomes in arrival order."""
        return [o for o in self.contributions.values() if not o.contributed]
