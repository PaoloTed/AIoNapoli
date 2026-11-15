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
        "route_proposed",
        "route_invalidated",
        "negotiation_finished",
        "worker_delegated",
        "worker_outcome",
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

    def route_proposed(
        self,
        proposal_id: str,
        iteration: int,
        route_ids: list[str] | tuple[str, ...],
        duration_min: int,
        agent: str = "mobility",
    ) -> TraceEvent:
        """Record an itinerary proposed by Mobility during negotiation."""
        ev = TraceEvent(
            seq=self._next_seq(),
            event_type="route_proposed",
            data={
                "proposal_id": proposal_id,
                "iteration": iteration,
                "route_ids": list(route_ids),
                "duration_min": duration_min,
            },
            agent=agent,
            outcome=f"proposta {proposal_id} al giro {iteration}",
        )
        self.events.append(ev)
        return ev

    def route_invalidated(
        self,
        proposal_id: str,
        iteration: int,
        constraint_kinds: list[str],
        evidence_refs: list[str],
        agent: str = "incidents",
    ) -> TraceEvent:
        """Record a route proposal blocked by one or more closure constraints."""
        ev = TraceEvent(
            seq=self._next_seq(),
            event_type="route_invalidated",
            data={
                "proposal_id": proposal_id,
                "iteration": iteration,
                "constraint_kinds": list(constraint_kinds),
                "evidence_refs": list(evidence_refs),
            },
            agent=agent,
            outcome=f"proposta {proposal_id} scartata al giro {iteration}",
        )
        self.events.append(ev)
        return ev

    def negotiation_finished(
        self,
        iterations: int,
        exhausted: bool,
        constraints_applied: list[str] | tuple[str, ...],
        agent: str = "orchestrator",
    ) -> TraceEvent:
        """Record end of negotiation cycle."""
        ev = TraceEvent(
            seq=self._next_seq(),
            event_type="negotiation_finished",
            data={
                "iterations": iterations,
                "exhausted": exhausted,
                "constraints_applied": list(constraints_applied),
            },
            agent=agent,
            outcome="negoziazione conclusa",
        )
        self.events.append(ev)
        return ev

    def worker_delegated(
        self,
        agent: str,
        capabilities: list[str] | tuple[str, ...],
        can_handle_reason: str = "",
    ) -> TraceEvent:
        """Record delegation to a specialized domain worker."""
        ev = TraceEvent(
            seq=self._next_seq(),
            event_type="worker_delegated",
            data={
                "agent": agent,
                "capabilities": list(capabilities),
                "can_handle_reason": can_handle_reason,
            },
            agent=agent,
            outcome="worker delegato",
        )
        self.events.append(ev)
        return ev

    def worker_outcome(
        self,
        agent: str,
        contributed: bool,
        reason: str = "",
        llm_used: str = "no",
        elapsed_ms: int = 0,
    ) -> TraceEvent:
        """Record outcome returned by a specialized domain worker."""
        ev = TraceEvent(
            seq=self._next_seq(),
            event_type="worker_outcome",
            data={
                "agent": agent,
                "contributed": contributed,
                "reason": reason,
                "llm_used": llm_used,
                "elapsed_ms": elapsed_ms,
            },
            agent=agent,
            outcome="contribuito" if contributed else f"rifiutato: {reason}",
        )
        self.events.append(ev)
        return ev
