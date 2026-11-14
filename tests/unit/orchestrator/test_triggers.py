"""Unit tests for orchestrator triggers R1-R4 and partial finding handling."""

from __future__ import annotations

from datetime import datetime, timezone

from app.domain.models.config import AppConfig
from app.domain.models.finding import AgentName, Finding, FindingType, Severity
from app.services.orchestrator.triggers import (
    evaluate_all_rules,
    evaluate_r1,
    evaluate_r2,
    evaluate_r3,
    evaluate_r4,
)


def _mk_finding(
    agent: AgentName,
    ftype: FindingType,
    content: dict[str, object],
    severity: Severity = Severity.HIGH,
) -> Finding:
    return Finding(
        agent=agent,
        type=ftype,
        content=content,
        confidence=0.85,
        severity=severity,
        source_id="test_src",
        data_reference="test:1",
        is_simulated=True,
        timestamp=datetime(2026, 11, 14, 16, 0, 0, tzinfo=timezone.utc),
    )


def test_r1(app_config: AppConfig) -> None:
    """REQ-ORC-01: R1 triggers when mobility severity >= high and crowding density > 0.85."""
    mob_high = _mk_finding(
        AgentName.MOBILITY, FindingType.ROUTE_DISRUPTION, {"zone_id": "Z_BAGNOLI"}, Severity.HIGH
    )
    crd_high = _mk_finding(
        AgentName.CROWDING, FindingType.DENSITY_ALERT, {"density": 0.91, "zone_id": "Z_BAGNOLI"}
    )
    assert evaluate_r1([mob_high, crd_high], app_config.rules).fired is True

    crd_low = _mk_finding(
        AgentName.CROWDING, FindingType.DENSITY_ALERT, {"density": 0.60, "zone_id": "Z_BAGNOLI"}
    )
    assert evaluate_r1([mob_high, crd_low], app_config.rules).fired is False

    mob_low = _mk_finding(
        AgentName.MOBILITY, FindingType.ROUTE_ALTERNATIVE, {"zone_id": "Z_BAGNOLI"}, Severity.LOW
    )
    assert evaluate_r1([mob_low, crd_high], app_config.rules).fired is False


def test_r2(app_config: AppConfig) -> None:
    """REQ-ORC-02: R2 detects conflict when mobility and crowding target same saturated zone."""
    mob = _mk_finding(AgentName.MOBILITY, FindingType.ROUTE_DISRUPTION, {"zone_id": "Z_BAGNOLI"})
    crd = _mk_finding(
        AgentName.CROWDING, FindingType.DENSITY_ALERT, {"density": 0.91, "zone_id": "Z_BAGNOLI"}
    )
    res = evaluate_r2([mob, crd], app_config.rules)
    assert res.fired is True
    assert res.zone_id == "Z_BAGNOLI"

    crd_other = _mk_finding(
        AgentName.CROWDING, FindingType.DENSITY_ALERT, {"density": 0.91, "zone_id": "Z_GARIBALDI"}
    )
    assert evaluate_r2([mob, crd_other], app_config.rules).fired is False


def test_r3(app_config: AppConfig) -> None:
    """REQ-ORC-03: R3 reduces capacity when heavy_rain is True and density > 0.70."""
    ctx_rain = _mk_finding(
        AgentName.CONTEXT, FindingType.IMPACT_ASSESSMENT, {"heavy_rain": True}, Severity.MEDIUM
    )
    crd_ok = _mk_finding(AgentName.CROWDING, FindingType.DENSITY_ALERT, {"density": 0.75})
    assert evaluate_r3([ctx_rain, crd_ok], app_config.rules).fired is True

    ctx_dry = _mk_finding(
        AgentName.CONTEXT, FindingType.IMPACT_ASSESSMENT, {"heavy_rain": False}, Severity.LOW
    )
    assert evaluate_r3([ctx_dry, crd_ok], app_config.rules).fired is False


def test_r4(app_config: AppConfig) -> None:
    """REQ-ORC-04: R4 fires when expected_attendance > threshold and mobility shows saturation."""
    ctx_big = _mk_finding(
        AgentName.CONTEXT,
        FindingType.IMPACT_ASSESSMENT,
        {"expected_attendance": 12000},
        Severity.MEDIUM,
    )
    mob_sat = _mk_finding(
        AgentName.MOBILITY, FindingType.ROUTE_DISRUPTION, {"congestion": 0.88}, Severity.HIGH
    )
    assert evaluate_r4([ctx_big, mob_sat], app_config.rules).fired is True

    ctx_small = _mk_finding(
        AgentName.CONTEXT,
        FindingType.IMPACT_ASSESSMENT,
        {"expected_attendance": 2000},
        Severity.LOW,
    )
    assert evaluate_r4([ctx_small, mob_sat], app_config.rules).fired is False


def test_finding_parziali(app_config: AppConfig) -> None:
    """REQ-ORC-05: partial or empty content findings never raise; rules return fired=False."""
    partial = [
        _mk_finding(AgentName.MOBILITY, FindingType.ROUTE_DISRUPTION, {}, Severity.HIGH),
    ]
    results = evaluate_all_rules(partial, app_config.rules)
    assert len(results) == 4
    assert all(r.fired is False for r in results)
    assert all(r.missing_fields for r in results)
