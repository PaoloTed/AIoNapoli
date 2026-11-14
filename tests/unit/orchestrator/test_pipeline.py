"""Unit tests for the orchestrator pipeline determinism and zero-rule baseline."""

from __future__ import annotations

from datetime import datetime, timezone

from app.domain.models.config import AppConfig
from app.domain.models.decision import PlanTarget
from app.domain.models.finding import AgentName, Finding, FindingType, Severity
from app.services.orchestrator.pipeline import run_pipeline
from app.utils.clock import FixedClock


def test_determinismo(
    demo_findings: list[Finding],
    app_config: AppConfig,
    fixed_clock: FixedClock,
) -> None:
    """REQ-ORC-12: identical input produces identical Decision and decision_id."""
    out1 = run_pipeline(demo_findings, app_config, clock=fixed_clock)
    out2 = run_pipeline(demo_findings, app_config, clock=fixed_clock)
    assert out1.decision_id == out2.decision_id
    assert out1.decision.model_dump() == out2.decision.model_dump()
    assert out1.relevance.model_dump() == out2.relevance.model_dump()


def test_nessuna_regola(app_config: AppConfig, fixed_clock: FixedClock) -> None:
    """REQ-ORC-13: zero triggered rules yields a valid Decision with monitoring plan items."""
    ts = datetime(2026, 11, 14, 9, 0, 0, tzinfo=timezone.utc)
    calm_findings = [
        Finding(
            agent=AgentName.MOBILITY,
            type=FindingType.ROUTE_ALTERNATIVE,
            content={"zone_id": "Z_GARIBALDI", "congestion": 0.25},
            confidence=0.90,
            severity=Severity.LOW,
            source_id="anm",
            data_reference="gtfs:1",
            is_simulated=False,
            timestamp=ts,
        ),
        Finding(
            agent=AgentName.CROWDING,
            type=FindingType.DENSITY_ALERT,
            content={"zone_id": "Z_MUNICIPIO", "density": 0.40},
            confidence=0.85,
            severity=Severity.LOW,
            source_id="ir_sensors",
            data_reference="occupancy:1",
            is_simulated=True,
            timestamp=ts,
        ),
        Finding(
            agent=AgentName.CONTEXT,
            type=FindingType.IMPACT_ASSESSMENT,
            content={"heavy_rain": False, "expected_attendance": 1200, "zone_id": "Z_MUNICIPIO"},
            confidence=0.88,
            severity=Severity.LOW,
            source_id="open_meteo",
            data_reference="weather:1",
            is_simulated=True,
            timestamp=ts,
        ),
    ]
    out = run_pipeline(calm_findings, app_config, clock=fixed_clock)
    assert out.decision.conflict.detected is False
    assert {item.target for item in out.decision.plan} == {
        PlanTarget.OPERATOR,
        PlanTarget.TOURIST,
        PlanTarget.CITIZEN,
    }
    assert any("non scattata" in step.outcome for step in out.decision.reasoning_log)

