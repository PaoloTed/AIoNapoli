"""Unit tests confirming narrative LLM degradation does not alter Decision or decision_id."""

from __future__ import annotations

from app.domain.models.config import AppConfig
from app.domain.models.finding import Finding
from app.services.orchestrator.pipeline import run_pipeline
from app.utils.clock import FixedClock


def test_llm_off(
    demo_findings: list[Finding],
    app_config: AppConfig,
    fixed_clock: FixedClock,
) -> None:
    """REQ-DEG-02: switching llm_mode between off, replay, and live preserves exact Decision."""
    cfg_replay = app_config.model_copy(update={"llm_mode": "replay"})
    cfg_off = app_config.model_copy(update={"llm_mode": "off"})
    cfg_live = app_config.model_copy(update={"llm_mode": "live"})

    out_replay = run_pipeline(demo_findings, cfg_replay, clock=fixed_clock)
    out_off = run_pipeline(demo_findings, cfg_off, clock=fixed_clock)
    out_live = run_pipeline(demo_findings, cfg_live, clock=fixed_clock)

    assert out_replay.decision_id == out_off.decision_id == out_live.decision_id
    assert out_replay.decision.model_dump() == out_off.decision.model_dump()
    assert out_off.narrative.mode == "off"
    assert out_off.narrative.items == []
    assert out_replay.narrative.items
