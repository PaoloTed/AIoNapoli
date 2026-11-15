"""Shared pytest fixtures for backend unit, integration, DB, and e2e tests."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.domain.models.config import AppConfig
from app.domain.models.finding import AgentName, Finding, FindingType, Severity
from app.services.orchestrator.config import load_config
from app.utils.clock import FixedClock


@pytest.fixture
def app_config() -> AppConfig:
    return load_config()


@pytest.fixture
def fixed_clock() -> FixedClock:
    return FixedClock(datetime(2026, 11, 14, 17, 41, 12, tzinfo=timezone.utc))


@pytest.fixture
def demo_findings() -> list[Finding]:
    return [
        Finding(
            agent=AgentName.MOBILITY,
            type=FindingType.ROUTE_DISRUPTION,
            content={"zone_id": "Z_BAGNOLI", "congestion": 0.88},
            confidence=0.90,
            severity=Severity.HIGH,
            source_id="anm",
            data_reference="rss:2026-11-14T16:12:00+01:00",
            is_simulated=False,
            timestamp=datetime(2026, 11, 14, 15, 12, 0, tzinfo=timezone.utc),
        ),
        Finding(
            agent=AgentName.CROWDING,
            type=FindingType.DENSITY_ALERT,
            content={"density": 0.91, "zone_id": "Z_BAGNOLI"},
            confidence=0.82,
            severity=Severity.HIGH,
            source_id="ir_sensors",
            data_reference="occupancy:2026-11-14T17:40:00+01:00",
            is_simulated=True,
            timestamp=datetime(2026, 11, 14, 16, 40, 0, tzinfo=timezone.utc),
        ),
        Finding(
            agent=AgentName.CONTEXT,
            type=FindingType.IMPACT_ASSESSMENT,
            content={"heavy_rain": True, "expected_attendance": 12000, "zone_id": "Z_BAGNOLI"},
            confidence=0.75,
            severity=Severity.MEDIUM,
            source_id="open_meteo",
            data_reference="weather:2026-11-14T17:00:00+01:00",
            is_simulated=True,
            timestamp=datetime(2026, 11, 14, 16, 0, 0, tzinfo=timezone.utc),
        ),
    ]
