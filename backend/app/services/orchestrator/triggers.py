"""Deterministic rule evaluation R1-R4 with trace integration."""

from __future__ import annotations

from app.domain.logic.refs import compute_finding_ref
from app.domain.logic.rules import (
    evaluate_r1_pure,
    evaluate_r2_pure,
    evaluate_r3_pure,
    evaluate_r4_pure,
    index_findings_by_agent,
)
from app.domain.models.config import RulesConfig
from app.domain.models.decision import RuleId
from app.domain.models.finding import AgentName, Finding
from app.domain.models.trace import Trace
from app.services.orchestrator.models import RuleResult


def _primary_ref(
    by_agent: dict[AgentName, Finding],
    preferred_order: tuple[AgentName, ...],
) -> str:
    for agent in preferred_order:
        if agent in by_agent:
            return compute_finding_ref(by_agent[agent])
    return "none"


def evaluate_r1(findings: list[Finding], config: RulesConfig) -> RuleResult:
    by_agent = index_findings_by_agent(findings)
    pure = evaluate_r1_pure(by_agent, config)
    ref = _primary_ref(by_agent, (AgentName.CROWDING, AgentName.MOBILITY))
    return RuleResult(
        rule_id=pure.rule_id,
        agents=list(pure.agents),
        fired=pure.fired,
        reason=pure.reason,
        zone_id=pure.zone_id,
        missing_fields=list(pure.missing_fields),
        finding_ref=ref,
    )


def evaluate_r2(findings: list[Finding], config: RulesConfig) -> RuleResult:
    by_agent = index_findings_by_agent(findings)
    pure = evaluate_r2_pure(by_agent, config)
    ref = _primary_ref(by_agent, (AgentName.MOBILITY, AgentName.CROWDING))
    return RuleResult(
        rule_id=pure.rule_id,
        agents=list(pure.agents),
        fired=pure.fired,
        reason=pure.reason,
        zone_id=pure.zone_id,
        missing_fields=list(pure.missing_fields),
        finding_ref=ref,
    )


def evaluate_r3(findings: list[Finding], config: RulesConfig) -> RuleResult:
    by_agent = index_findings_by_agent(findings)
    pure = evaluate_r3_pure(by_agent, config)
    ref = _primary_ref(by_agent, (AgentName.CONTEXT, AgentName.CROWDING))
    return RuleResult(
        rule_id=pure.rule_id,
        agents=list(pure.agents),
        fired=pure.fired,
        reason=pure.reason,
        zone_id=pure.zone_id,
        missing_fields=list(pure.missing_fields),
        finding_ref=ref,
    )


def evaluate_r4(findings: list[Finding], config: RulesConfig) -> RuleResult:
    by_agent = index_findings_by_agent(findings)
    pure = evaluate_r4_pure(by_agent, config)
    ref = _primary_ref(by_agent, (AgentName.CONTEXT, AgentName.MOBILITY))
    return RuleResult(
        rule_id=pure.rule_id,
        agents=list(pure.agents),
        fired=pure.fired,
        reason=pure.reason,
        zone_id=pure.zone_id,
        missing_fields=list(pure.missing_fields),
        finding_ref=ref,
    )


_EVALUATORS = {
    RuleId.R1_LINE2_CROWDING: (evaluate_r1, AgentName.CROWDING),
    RuleId.R2_CONFLICT_ROUTE_VS_DENSITY: (evaluate_r2, AgentName.MOBILITY),
    RuleId.R3_WEATHER_CAPACITY: (evaluate_r3, AgentName.CONTEXT),
    RuleId.R4_EVENT_SURGE: (evaluate_r4, AgentName.CONTEXT),
}


def evaluate_all_rules(
    findings: list[Finding],
    config: RulesConfig,
    trace: Trace | None = None,
) -> list[RuleResult]:
    """Evaluate R1-R4 in configured precedence order and emit trace events."""
    results: list[RuleResult] = []
    for rule_id in config.rule_precedence:
        evaluator, default_agent = _EVALUATORS[rule_id]
        res = evaluator(findings, config)
        results.append(res)
        if trace is not None:
            trace.rule_evaluated(
                rule_id=res.rule_id.value,
                agents=[a.value for a in res.agents],
                fired=res.fired,
                reason=res.reason,
                finding_ref=res.finding_ref,
                agent=default_agent.value,
            )
    return results
