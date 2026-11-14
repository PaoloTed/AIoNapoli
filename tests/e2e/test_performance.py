"""Performance tests enforcing the < 2 second end-to-end decision budget (NFR-03)."""

from __future__ import annotations

import time

from fastapi.testclient import TestClient

from app.main import create_app
from app.services.facade import BackendService


def test_entro_due_secondi() -> None:
    """NFR-03: end-to-end decision on demo fixtures completes within 2.0 seconds."""
    app = create_app(service=BackendService())
    with TestClient(app) as client:
        t0 = time.perf_counter()
        resp = client.post("/api/v1/decision", json={"scenario_id": "bagnoli"})
        elapsed = time.perf_counter() - t0
    assert resp.status_code == 200
    assert elapsed < 2.0, f"Decision took {elapsed:.3f}s (>= 2.0s budget)"

