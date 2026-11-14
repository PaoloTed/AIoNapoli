"""Integration tests for APP_PROFILE selection and DB-free memory degradation."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.repositories.audit import InMemoryAuditStore
from app.repositories.memory import InMemorySourceRepository
from app.services.facade import BackendService
from app.services.orchestrator.config import load_config


def test_memory_senza_db(monkeypatch: pytest.MonkeyPatch) -> None:
    """REQ-DEG-04: APP_PROFILE=memory runs end-to-end without PostgreSQL or SQLite."""
    monkeypatch.setenv("APP_PROFILE", "memory")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    cfg = load_config()
    assert cfg.app_profile == "memory"

    service = BackendService(config=cfg)
    assert isinstance(service.repository, InMemorySourceRepository)
    assert isinstance(service.audit_store, InMemoryAuditStore)

    app = create_app(service=service)
    with TestClient(app) as client:
        r_scen = client.get("/api/v1/scenario/bagnoli")
        assert r_scen.status_code == 200
        r_dec = client.post("/api/v1/decision", json={"scenario_id": "bagnoli"})
        assert r_dec.status_code == 200
        assert service.audit_store.get_decision(r_dec.json()["decision_id"]) is not None

