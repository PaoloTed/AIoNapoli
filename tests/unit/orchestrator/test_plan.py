"""Unit tests for Plan generation across the three required targets and log isolation."""

from __future__ import annotations

from app.domain.logic.refs import compute_finding_ref
from app.domain.models.config import AppConfig
from app.domain.models.decision import PlanTarget, RuleId
from app.domain.models.finding import Finding
from app.services.orchestrator.pipeline import decide
from app.utils.clock import FixedClock


def test_tre_target(
    demo_findings: list[Finding],
    app_config: AppConfig,
    fixed_clock: FixedClock,
) -> None:
    """REQ-ORC-10: Decision.plan contains at least one item per target."""
    decision = decide(demo_findings, app_config, clock=fixed_clock)
    targets = {item.target for item in decision.plan}
    assert targets == {PlanTarget.OPERATOR, PlanTarget.TOURIST, PlanTarget.CITIZEN}


def test_nessun_log_ai_target(
    demo_findings: list[Finding],
    app_config: AppConfig,
    fixed_clock: FixedClock,
) -> None:
    """REQ-ORC-11: tourist and citizen plan items must not leak rule IDs, refs, or reasoning_log."""
    decision = decide(demo_findings, app_config, clock=fixed_clock)
    refs = {compute_finding_ref(f) for f in demo_findings}
    rule_ids = {r.value for r in RuleId}
    forbidden_tokens = refs | rule_ids | {"reasoning_log", "rule_evaluated"}

    for item in decision.plan:
        if item.target in (PlanTarget.TOURIST, PlanTarget.CITIZEN):
            combined = f"{item.action} {item.rationale}"
            for token in forbidden_tokens:
                assert token not in combined, (
                    f"Leaked '{token}' into {item.target.value}: {combined}"
                )
