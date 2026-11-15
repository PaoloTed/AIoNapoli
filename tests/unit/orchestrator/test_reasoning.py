"""Unit tests for orchestrator reasoning_log derivation from Trace."""

from __future__ import annotations

from datetime import datetime, timezone

from app.domain.models.config import AppConfig
from app.domain.models.decision import RuleId
from app.domain.models.finding import AgentName, Finding, FindingType, Severity
from app.domain.models.trace import Trace
from app.services.orchestrator.pipeline import decide
from app.services.orchestrator.reasoning import build_reasoning_log
from app.services.orchestrator.triggers import evaluate_all_rules
from app.utils.clock import FixedClock


def test_regola_non_scattata(app_config: AppConfig) -> None:
    """REQ-ORC-06: unfired rules record the reason and missing field/threshold in trace & log."""
    partial = [
        Finding(
            agent=AgentName.MOBILITY,
            type=FindingType.ROUTE_DISRUPTION,
            content={"zone_id": "Z_BAGNOLI"},
            confidence=0.9,
            severity=Severity.HIGH,
            source_id="anm",
            data_reference="rss:1",
            is_simulated=False,
            timestamp=datetime(2026, 11, 14, 16, 0, 0, tzinfo=timezone.utc),
        )
    ]
    trace = Trace()
    results = evaluate_all_rules(partial, app_config.rules, trace=trace)
    assert all(not r.fired for r in results)

    eval_events = [ev for ev in trace.events if ev.event_type == "rule_evaluated"]
    assert len(eval_events) == 4
    r1_ev = next(ev for ev in eval_events if ev.rule_applied == RuleId.R1_LINE2_CROWDING.value)
    assert r1_ev.data["fired"] is False
    assert "density" in r1_ev.data["reason"] or "crowding" in r1_ev.data["reason"]

    log = build_reasoning_log(trace)
    assert any(step.rule_applied == RuleId.R1_LINE2_CROWDING.value for step in log)


def test_contiguo_e_corto(
    demo_findings: list[Finding],
    app_config: AppConfig,
    fixed_clock: FixedClock,
) -> None:
    """REQ-ORC-09: reasoning_log has contiguous 1-based steps and <= 5 lines on demo scenario."""
    decision = decide(demo_findings, app_config, clock=fixed_clock)
    steps = decision.reasoning_log
    assert 1 <= len(steps) <= 5
    assert [s.step for s in steps] == list(range(1, len(steps) + 1))
    assert all(len(s.outcome) <= 280 for s in steps)
