"""Contract tests for shared enumerations."""

from __future__ import annotations

import pytest
from shared.schemas.enums import PlanTarget, RuleId, Severity


def test_severity() -> None:
    assert {s.value for s in Severity} == {"low", "medium", "high", "critical"}
    with pytest.raises(ValueError):
        Severity("urgent")


def test_rule_id() -> None:
    assert {r.value for r in RuleId} == {
        "R1_line2_crowding",
        "R2_conflict_route_vs_density",
        "R3_weather_capacity",
        "R4_event_surge",
    }
    with pytest.raises(ValueError):
        RuleId("R5_custom")


def test_target() -> None:
    assert {t.value for t in PlanTarget} == {"operator", "tourist", "citizen"}
    with pytest.raises(ValueError):
        PlanTarget("admin")
