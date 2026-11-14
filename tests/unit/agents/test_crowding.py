"""Unit tests for CrowdingAgent refusals and density normalization."""

from __future__ import annotations

from app.domain.models.refusal import Refusal
from app.repositories.memory import InMemorySourceRepository
from app.services.agents.crowding.agent import CrowdingAgent
from app.services.connectors.occupancy.connector import OccupancyConnector


def test_rifiuto_senza_occupancy() -> None:
    """REQ-AGT-04: absent occupancy or simulated with allow_simulation=False triggers Refusal."""
    repo = InMemorySourceRepository(load_fixtures=True)
    agent = CrowdingAgent(repo)
    res = agent.evaluate(zone_id="Z_BAGNOLI")
    assert isinstance(res, Refusal)
    assert res.reason_code == "missing_occupancy"

    OccupancyConnector(repo).run()
    res_strict = agent.evaluate(zone_id="Z_BAGNOLI", allow_simulation=False)
    assert isinstance(res_strict, Refusal)
    assert res_strict.reason_code == "missing_occupancy"


def test_rifiuto_senza_geofence() -> None:
    """REQ-AGT-05: event missing geofence triggers Refusal(reason_code='missing_geofence')."""
    repo = InMemorySourceRepository(load_fixtures=True)
    OccupancyConnector(repo).run()
    repo.upsert_events(
        [
            {
                "event_id": "EVT-NO-GEO",
                "name": "Evento senza geofence",
                "zone_id": "Z_BAGNOLI",
                "geofence": "",
                "expected_attendance": 8000,
                "window_start": "2026-11-14T15:00:00+00:00",
                "window_end": "2026-11-14T20:00:00+00:00",
                "source_id": "events_dataset",
                "data_reference": "dataset:test",
                "is_simulated": True,
            }
        ]
    )
    res = CrowdingAgent(repo).evaluate(zone_id="Z_BAGNOLI")
    assert isinstance(res, Refusal)
    assert res.reason_code == "missing_geofence"
