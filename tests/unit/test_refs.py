"""Unit tests for content-addressed refs and unit conversions."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.domain.logic.refs import compute_decision_id, compute_finding_ref
from app.domain.logic.units import occupancy_to_density
from app.domain.models.config import AppConfig
from app.domain.models.finding import AgentName, Finding, FindingType, Severity
from app.services.orchestrator.pipeline import decide
from app.utils.clock import FixedClock


def test_finding_ref_stabile() -> None:
    """REQ-CONTR-08: finding_ref is deterministic regardless of content dict key order."""
    ts = datetime(2026, 11, 14, 16, 40, 0, tzinfo=timezone.utc)
    f1 = Finding(
        agent=AgentName.CROWDING,
        type=FindingType.DENSITY_ALERT,
        content={"density": 0.91, "zone_id": "Z_BAGNOLI", "extra": {"b": 2, "a": 1}},
        confidence=0.82,
        severity=Severity.HIGH,
        source_id="ir_sensors",
        data_reference="occupancy:2026-11-14T17:40:00+01:00",
        is_simulated=True,
        timestamp=ts,
    )
    f2 = Finding(
        agent=AgentName.CROWDING,
        type=FindingType.DENSITY_ALERT,
        content={"extra": {"a": 1, "b": 2}, "zone_id": "Z_BAGNOLI", "density": 0.91},
        confidence=0.8200001,
        severity=Severity.HIGH,
        source_id="ir_sensors",
        data_reference="occupancy:2026-11-14T17:40:00+01:00",
        is_simulated=True,
        timestamp=ts,
    )
    ref1 = compute_finding_ref(f1)
    ref2 = compute_finding_ref(f2)
    assert ref1 == ref2
    assert len(ref1) == 12
    assert all(c in "0123456789abcdef" for c in ref1)


def test_decision_id_esclude_timestamp(
    demo_findings: list[Finding],
    app_config: AppConfig,
) -> None:
    """decision_id must remain stable across different decision timestamps."""
    c1 = FixedClock(datetime(2026, 11, 14, 17, 41, 0, tzinfo=timezone.utc))
    c2 = FixedClock(datetime(2026, 11, 14, 17, 41, 0, tzinfo=timezone.utc) + timedelta(hours=2))
    d1 = decide(demo_findings, app_config, clock=c1)
    d2 = decide(demo_findings, app_config, clock=c2)
    assert compute_decision_id(d1) == compute_decision_id(d2)
    assert len(compute_decision_id(d1)) == 16


def test_occupancy_to_density() -> None:
    """D-15: single source of truth conversion from occupancy_pct [0..100] to [0..1]."""
    assert occupancy_to_density(91.0) == 0.91
    assert occupancy_to_density(0) == 0.0
    assert occupancy_to_density(100) == 1.0
    with pytest.raises(ValueError):
        occupancy_to_density(-1.0)
    with pytest.raises(ValueError):
        occupancy_to_density(101.0)
    with pytest.raises(ValueError):
        occupancy_to_density(True)  # type: ignore[arg-type]
