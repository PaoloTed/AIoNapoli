"""Unit determinism tests across every pure domain logic module (NFR-09)."""

from __future__ import annotations

from app.domain.logic import accessors, priorities, refs, rules, scoring, units
from app.domain.models.config import AppConfig
from app.domain.models.decision import PlanTarget
from app.domain.models.finding import AgentName, Finding
from app.services.orchestrator.pipeline import decide
from app.utils.clock import FixedClock


def test_ogni_modulo(
    demo_findings: list[Finding],
    app_config: AppConfig,
    fixed_clock: FixedClock,
) -> None:
    """NFR-09: verify every module in domain/logic/ produces identical results on repeat calls."""
    # 1. units
    assert units.occupancy_to_density(91.0) == units.occupancy_to_density(91.0)

    # 2. accessors
    mob, crd, ctx = demo_findings
    assert accessors.congestion(mob) == accessors.congestion(mob) == 0.88
    assert accessors.density(crd) == accessors.density(crd) == 0.91
    assert accessors.heavy_rain(ctx) == accessors.heavy_rain(ctx) is True
    assert accessors.expected_attendance(ctx) == accessors.expected_attendance(ctx) == 12000
    assert accessors.zone_id(crd) == accessors.zone_id(crd) == "Z_BAGNOLI"

    # 3. rules
    by_agent_1 = rules.index_findings_by_agent(demo_findings)
    by_agent_2 = rules.index_findings_by_agent(list(reversed(demo_findings)))
    assert list(by_agent_1.keys()) == list(by_agent_2.keys())
    for fn in (
        rules.evaluate_r1_pure,
        rules.evaluate_r2_pure,
        rules.evaluate_r3_pure,
        rules.evaluate_r4_pure,
    ):
        assert fn(by_agent_1, app_config.rules) == fn(by_agent_2, app_config.rules)

    # 4. priorities
    p1 = priorities.resolve_priority_pure(
        [AgentName.CONTEXT, AgentName.MOBILITY, AgentName.CROWDING]
    )
    p2 = priorities.resolve_priority_pure(
        [AgentName.MOBILITY, AgentName.CROWDING, AgentName.CONTEXT]
    )
    assert p1 == p2
    assert p1.priority_code == "P1"

    # 5. scoring
    decision = decide(demo_findings, app_config, clock=fixed_clock)
    for target in PlanTarget:
        s1 = scoring.score_item_for_target(
            0, decision.plan[0], target, decision, demo_findings, app_config.relevance
        )
        s2 = scoring.score_item_for_target(
            0, decision.plan[0], target, decision, demo_findings, app_config.relevance
        )
        assert s1 == s2

    # 6. refs
    assert refs.compute_finding_ref(mob) == refs.compute_finding_ref(mob)
    assert refs.compute_decision_id(decision) == refs.compute_decision_id(decision)
