"""Pure Trace model: single source of truth for reasoning_log and SSE stream."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class TraceEvent(BaseModel):
    """Single deterministic event emitted during the decision pipeline."""

    model_config = ConfigDict(extra="forbid")

    seq: int = Field(ge=1)
    event_type: Literal[
        "phase",
        "rule_evaluated",
        "conflict_detected",
        "priority_applied",
        "plan_item_created",
    ]
    data: dict[str, Any]
    agent: str | None = None
    finding_ref: str | None = None
    rule_applied: str | None = None
    outcome: str | None = None


class Trace(BaseModel):
    """Ordered trace accumulator for a single decision run."""

    model_config = ConfigDict(extra="forbid")

    events: list[TraceEvent] = Field(default_factory=list)

    def _next_seq(self) -> int:
        return len(self.events) + 1

    def phase(self, phase: str, index: int) -> TraceEvent:
        """Record start of a pipeline phase."""
        ev = TraceEvent(
            seq=self._next_seq(),
            event_type="phase",
            data={"phase": phase, "index": index},
        )
        self.events.append(ev)
        return ev

    def rule_evaluated(
        self,
        rule_id: str,
        agents: list[str],
        fired: bool,
        reason: str,
        finding_ref: str = "none",
        agent: str = "orchestrator",
    ) -> TraceEvent:
        """Record evaluation outcome of a rule (fired or not)."""
        ev = TraceEvent(
            seq=self._next_seq(),
            event_type="rule_evaluated",
            data={
                "rule_id": rule_id,
                "agents": list(agents),
                "fired": fired,
                "reason": reason,
            },
            agent=agent,
            finding_ref=finding_ref,
            rule_applied=rule_id,
            outcome=reason,
        )
        self.events.append(ev)
        return ev

    def conflict_detected(
        self,
        description: str,
        zone_id: str,
        finding_ref: str = "none",
        agent: str = "orchestrator",
        rule_applied: str = "R2_conflict_route_vs_density",
    ) -> TraceEvent:
        """Record a detected conflict."""
        ev = TraceEvent(
            seq=self._next_seq(),
            event_type="conflict_detected",
            data={"description": description, "zone_id": zone_id},
            agent=agent,
            finding_ref=finding_ref,
            rule_applied=rule_applied,
            outcome=description,
        )
        self.events.append(ev)
        return ev

    def priority_applied(
        self,
        priority: str,
        winner: str,
        finding_ref: str = "none",
        outcome: str = "",
    ) -> TraceEvent:
        """Record priority resolution P1-P3."""
        resolved_outcome = outcome or f"priorita' {priority} applicata, prevale {winner}"
        ev = TraceEvent(
            seq=self._next_seq(),
            event_type="priority_applied",
            data={"priority": priority, "winner": winner},
            agent="orchestrator",
            finding_ref=finding_ref,
            rule_applied=priority,
            outcome=resolved_outcome,
        )
        self.events.append(ev)
        return ev

    def plan_item_created(self, target: str, action_ref: str) -> TraceEvent:
        """Record creation of a plan item for a target."""
        ev = TraceEvent(
            seq=self._next_seq(),
            event_type="plan_item_created",
            data={"target": target, "action_ref": action_ref},
        )
        self.events.append(ev)
        return ev

