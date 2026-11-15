"""Startup latency tests enforcing the < 3 second boot budget (NFR-04)."""

from __future__ import annotations

import time

from fastapi.testclient import TestClient

from app.main import create_app


def test_entro_tre_secondi() -> None:
    """NFR-04: backend startup with valid configuration completes within 3.0 seconds."""
    t0 = time.perf_counter()
    app = create_app()
    with TestClient(app) as client:
        resp = client.get("/api/v1/scenario/bagnoli")
    elapsed = time.perf_counter() - t0
    assert resp.status_code == 200
    assert elapsed < 3.0, f"Startup took {elapsed:.3f}s (>= 3.0s budget)"
