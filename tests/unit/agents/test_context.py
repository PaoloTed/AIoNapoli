"""Unit tests for ContextAgent refusals on missing weather alert or event window."""

from __future__ import annotations

from app.domain.models.refusal import Refusal
from app.repositories.memory import InMemorySourceRepository
from app.services.agents.context.agent import ContextAgent


def test_rifiuto_senza_allerta() -> None:
    """REQ-AGT-06: absent weather snapshot or missing alert_level triggers Refusal."""
    repo = InMemorySourceRepository(load_fixtures=True)
    agent = ContextAgent(repo)
    res_empty = agent.evaluate(zone_id="Z_BAGNOLI")
    assert isinstance(res_empty, Refusal)
    assert res_empty.reason_code == "missing_alert_level"

    repo.upsert_weather_snapshots(
        [
            {
                "snapshot_at": "2026-11-14T16:00:00+00:00",
                "forecast_at": "2026-11-14T17:00:00+00:00",
                "zone_id": "Z_BAGNOLI",
                "precipitation_mm": 12.0,
                "alert_level": None,
                "heavy_rain": False,
                "source_id": "open_meteo",
                "data_reference": "weather:test",
                "is_simulated": True,
            }
        ]
    )
    res_none_level = agent.evaluate(zone_id="Z_BAGNOLI")
    assert isinstance(res_none_level, Refusal)
    assert res_none_level.reason_code == "missing_alert_level"
