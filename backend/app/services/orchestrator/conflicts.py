"""Conflict detection and resolution between competing agent findings."""

from __future__ import annotations

from app.domain.logic.accessors import zone_id
from app.domain.logic.refs import compute_finding_ref
from app.domain.logic.rules import index_findings_by_agent
from app.domain.models.config import RulesConfig
from app.domain.models.decision import RuleId
from app.domain.models.finding import AgentName, Finding
from app.domain.models.trace import Trace
from app.services.orchestrator.models import Conflict, Resolution, RuleResult
from app.services.orchestrator.priorities import resolve_priority


def detect_conflict(
    findings: list[Finding],
    rule_results: list[RuleResult],
    trace: Trace | None = None,
) -> Conflict:
    """Detect whether mobility route and crowding saturation conflict on the same zone."""
    by_agent = index_findings_by_agent(findings)
    r2 = next(
        (r for r in rule_results if r.rule_id == RuleId.R2_CONFLICT_ROUTE_VS_DENSITY),
        None,
    )
    if r2 is not None and r2.fired:
        zone = r2.zone_id or "Z_NAPOLI"
        description = (
            f"Il percorso verso {zone} attraversa la zona satura rilevata da crowding; "
            f"deviazione diretta scartata per sicurezza"
        )
        if trace is not None:
            trace.conflict_detected(
                description=description,
                zone_id=zone,
                finding_ref=r2.finding_ref,
            )
        return Conflict(
            detected=True,
            description=description,
            zone_id=zone,
            conflicting_agents=[AgentName.MOBILITY, AgentName.CROWDING],
        )

    mob = by_agent.get(AgentName.MOBILITY)
    crd = by_agent.get(AgentName.CROWDING)
    mob_zone = zone_id(mob) if mob else None
    crd_zone = zone_id(crd) if crd else None
    zone_note = mob_zone or crd_zone or "area urbana"
    return Conflict(
        detected=False,
        description=f"Nessun conflitto attivo tra percorso e densita' su {zone_note}",
        zone_id=mob_zone or crd_zone,
        conflicting_agents=[],
    )


def resolve_conflict(
    conflict: Conflict,
    findings: list[Finding],
    rule_results: list[RuleResult],
    config: RulesConfig,
    trace: Trace | None = None,
) -> Resolution:
    """Resolve active rules and conflicts using rule_precedence and P1 > P2 > P3."""
    by_agent = index_findings_by_agent(findings)
    fired_rules = [r for r in rule_results if r.fired]

    # C2: dominant rule by configured rule_precedence
    dominant_rule = config.rule_precedence[0]
    for candidate_rule in config.rule_precedence:
        if any(r.rule_id == candidate_rule and r.fired for r in rule_results):
            dominant_rule = candidate_rule
            break

    active_agents: list[AgentName] = []
    for r in fired_rules:
        for a in r.agents:
            if a in by_agent and a not in active_agents:
                active_agents.append(a)
    if not active_agents:
        active_agents = [a for a in AgentName if a in by_agent]

    if conflict.detected:
        prio = resolve_priority([AgentName.CROWDING, AgentName.MOBILITY])
        discarded_action = "percorso diretto attraverso zona satura scartato"
    elif fired_rules:
        prio = resolve_priority(active_agents)
        discarded_action = None
    else:
        prio = resolve_priority(active_agents)
        discarded_action = None

    winner_finding = by_agent.get(prio.winner_agent)
    winner_ref = compute_finding_ref(winner_finding) if winner_finding else "none"

    if trace is not None:
        if conflict.detected:
            outcome = (
                f"priorita' {prio.priority_code} ({prio.label}) applicata, "
                f"percorso diretto scartato su {conflict.zone_id or 'zona satura'}"
            )
            trace.priority_applied(
                priority=prio.priority_code,
                winner=prio.winner_agent.value,
                finding_ref=winner_ref,
                outcome=outcome,
            )
        elif fired_rules:
            outcome = (
                f"priorita' {prio.priority_code} ({prio.label}) applicata "
                f"sulla regola dominante {dominant_rule.value}"
            )
            trace.priority_applied(
                priority=prio.priority_code,
                winner=prio.winner_agent.value,
                finding_ref=winner_ref,
                outcome=outcome,
            )
        else:
            outcome = "nessuna regola scattata, attivato piano di monitoraggio ordinario"
            trace.priority_applied(
                priority="MONITORING",
                winner=prio.winner_agent.value,
                finding_ref=winner_ref,
                outcome=outcome,
            )

    return Resolution(
        conflict=conflict,
        priority_code=prio.priority_code if fired_rules or conflict.detected else "MONITORING",
        priority_label=prio.label,
        winner_agent=prio.winner_agent,
        discarded_agents=list(prio.discarded_agents),
        discarded_action=discarded_action,
        dominant_rule=dominant_rule,
        agents_involved=active_agents,
    )

