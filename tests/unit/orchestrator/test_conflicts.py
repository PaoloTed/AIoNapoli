"""Unit tests for conflict detection and P1 > P2 > P3 priority resolution."""

from __future__ import annotations

from app.domain.models.config import AppConfig
from app.domain.models.finding import AgentName, Finding
from app.services.orchestrator.conflicts import detect_conflict, resolve_conflict
from app.services.orchestrator.priorities import resolve_priority
from app.services.orchestrator.triggers import evaluate_all_rules


def test_priorita(demo_findings: list[Finding], app_config: AppConfig) -> None:
    """REQ-ORC-08: crowding (P1) > mobility (P2) > context (P3) on conflicts."""
    p1 = resolve_priority([AgentName.MOBILITY, AgentName.CROWDING])
    assert p1.priority_code == "P1"
    assert p1.winner_agent == AgentName.CROWDING

    p2 = resolve_priority([AgentName.CONTEXT, AgentName.MOBILITY])
    assert p2.priority_code == "P2"
    assert p2.winner_agent == AgentName.MOBILITY

    rule_results = evaluate_all_rules(demo_findings, app_config.rules)
    conflict = detect_conflict(demo_findings, rule_results)
    assert conflict.detected is True
    resolution = resolve_conflict(conflict, demo_findings, rule_results, app_config.rules)
    assert resolution.priority_code == "P1"
    assert resolution.winner_agent == AgentName.CROWDING
    assert AgentName.MOBILITY in resolution.discarded_agents
