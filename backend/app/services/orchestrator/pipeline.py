"""Pure orchestrator pipeline composing all deterministic phases."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone

from app.domain.logic.refs import compute_decision_id
from app.domain.models.config import AppConfig
from app.domain.models.decision import Conflict as DomainConflict
from app.domain.models.decision import Decision, Trigger
from app.domain.models.finding import AgentName, Finding
from app.domain.models.refusal import Refusal
from app.domain.models.trace import Trace
from app.services.orchestrator.conflicts import detect_conflict, resolve_conflict
from app.services.orchestrator.models import PipelineOutput
from app.services.orchestrator.narrative import render_narrative
from app.services.orchestrator.plan import build_plan
from app.services.orchestrator.reasoning import build_reasoning_log
from app.services.orchestrator.relevance import score_relevance
from app.services.orchestrator.triggers import evaluate_all_rules
from app.utils.clock import Clock, SystemClock


def _compute_decision_confidence(findings: list[Finding], config: AppConfig) -> float:
    weights = {
        AgentName.MOBILITY: config.rules.confidence_weights.mobility,
        AgentName.CROWDING: config.rules.confidence_weights.crowding,
        AgentName.CONTEXT: config.rules.confidence_weights.context,
    }
    num = sum(f.confidence * weights[f.agent] for f in findings)
    den = sum(weights[f.agent] for f in findings)
    if den <= 0.0:
        return 0.0
    return round(min(1.0, max(0.0, num / den)), 2)


def run_pipeline(
    findings: Sequence[Finding | Refusal],
    config: AppConfig,
    clock: Clock | None = None,
) -> PipelineOutput:
    """Execute the full deterministic decision pipeline and return Decision + envelope artifacts."""
    active_clock = clock or SystemClock()
    now = active_clock.now()
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    else:
        now = now.astimezone(timezone.utc)

    trace = Trace()

    # Phase 1: Validation
    trace.phase("validazione", 1)
    valid_findings: list[Finding] = [f for f in findings if isinstance(f, Finding)]
    if not valid_findings:
        raise ValueError("missing_finding: nessun finding valido disponibile per decidere")

    # Sort deterministically by agent order and coerce uniqueness (last wins if duplicates passed)
    by_agent: dict[AgentName, Finding] = {}
    for finding in valid_findings:
        by_agent[finding.agent] = finding
    ordered_findings = [by_agent[agent] for agent in AgentName if agent in by_agent]

    # Phase 2: Trace initialization
    trace.phase("trace", 2)

    # Phase 3: Rule evaluation R1-R4
    trace.phase("regole", 3)
    rule_results = evaluate_all_rules(ordered_findings, config.rules, trace=trace)

    # Phase 4: Conflict detection
    trace.phase("conflitto", 4)
    conflict = detect_conflict(ordered_findings, rule_results, trace=trace)

    # Phase 5: Priority resolution
    trace.phase("priorita", 5)
    resolution = resolve_conflict(
        conflict=conflict,
        findings=ordered_findings,
        rule_results=rule_results,
        config=config.rules,
        trace=trace,
    )

    # Phase 6: Plan generation (3 targets)
    trace.phase("piano", 6)
    plan_items = build_plan(
        findings=ordered_findings,
        rule_results=rule_results,
        resolution=resolution,
        config=config.rules,
        trace=trace,
    )

    reasoning_log = build_reasoning_log(trace)
    confidence = _compute_decision_confidence(ordered_findings, config)
    agents_involved = resolution.agents_involved or [f.agent for f in ordered_findings]

    decision = Decision(
        trigger=Trigger(
            rule_id=resolution.dominant_rule,
            agents_involved=agents_involved,
        ),
        conflict=DomainConflict(
            detected=conflict.detected,
            description=conflict.description,
        ),
        plan=plan_items,
        reasoning_log=reasoning_log,
        confidence=confidence,
        timestamp=now if isinstance(now, datetime) else datetime.now(timezone.utc),
    )

    # Phase 7: Relevance scoring
    trace.phase("rilevanza", 7)
    relevance = score_relevance(decision, ordered_findings, config.relevance)

    # Phase 8: Canonical hash
    trace.phase("hash", 8)
    decision_id = compute_decision_id(decision)

    narrative = render_narrative(
        decision,
        mode=config.llm_mode,
        decision_id=decision_id,
        cache_dir=config.llm_cache_dir,
    )

    return PipelineOutput(
        decision_id=decision_id,
        decision=decision,
        relevance=relevance,
        narrative=narrative,
        trace=trace,
    )


def decide(
    findings: Sequence[Finding | Refusal],
    config: AppConfig,
    clock: Clock | None = None,
) -> Decision:
    """Pure core entry point: decide(findings, config, clock) -> Decision."""
    return run_pipeline(findings=findings, config=config, clock=clock).decision
