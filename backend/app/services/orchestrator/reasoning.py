"""Build Decision.reasoning_log directly from the single-source Trace (D-11)."""

from __future__ import annotations

from app.domain.models.decision import ReasoningStep
from app.domain.models.trace import Trace


def build_reasoning_log(trace: Trace) -> list[ReasoningStep]:
    """Project trace events into contiguous 1-based ReasoningSteps (max 5 steps)."""
    steps: list[ReasoningStep] = []
    relevant_events = [
        ev for ev in trace.events if ev.event_type in ("rule_evaluated", "priority_applied")
    ]
    for idx, ev in enumerate(relevant_events[:5], start=1):
        steps.append(
            ReasoningStep(
                step=idx,
                agent=ev.agent or "orchestrator",
                finding_ref=ev.finding_ref or "none",
                rule_applied=ev.rule_applied or "NONE",
                outcome=ev.outcome or ev.event_type,
            )
        )
    if not steps:
        steps.append(
            ReasoningStep(
                step=1,
                agent="orchestrator",
                finding_ref="none",
                rule_applied="MONITORING",
                outcome="nessun evento di regola registrato, monitoraggio attivo",
            )
        )
    return steps
