"""End-to-end HTTP integration tests for /api/v1/scenario and /api/v1/decision."""

from __future__ import annotations

from fastapi.testclient import TestClient
from shared.schemas.decision import DECISION_FIELDS

from app.domain.models.config import AppConfig
from app.main import create_app
from app.services.facade import BackendService
from app.utils.clock import FixedClock


def test_end_to_end(app_config: AppConfig, fixed_clock: FixedClock) -> None:
    """REQ-API-04: scenario fetch + decision creation returns frozen Decision & deterministic ID."""
    service = BackendService(config=app_config, clock=fixed_clock)
    app = create_app(service=service)
    with TestClient(app) as client:
        scen_resp = client.get("/api/v1/scenario/bagnoli")
        assert scen_resp.status_code == 200
        scen_body = scen_resp.json()
        assert scen_body["contract_version"] == "1.0.0"
        assert scen_body["scenario_id"] == "bagnoli"
        assert len(scen_body["findings"]) == 3
        assert len(scen_body["vehicle_positions"]) >= 1

        dec_scen = client.post("/api/v1/decision", json={"scenario_id": "bagnoli"})
        assert dec_scen.status_code == 200
        assert dec_scen.headers.get("cache-control") == "no-store"
        body1 = dec_scen.json()
        assert body1["contract_version"] == "1.0.0"
        assert set(body1["decision"].keys()) == DECISION_FIELDS
        assert "relevance" in body1
        assert "narrative" in body1

        # Explicit findings from the scenario must produce the exact same decision_id
        dec_explicit = client.post(
            "/api/v1/decision",
            json={"findings": scen_body["findings"]},
        )
        assert dec_explicit.status_code == 200
        body2 = dec_explicit.json()
        assert body2["decision_id"] == body1["decision_id"]
