"""Integration tests for POST /api/v1/finding/{agent}."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from app.domain.models.finding import Finding
from app.main import create_app
from app.services.facade import BackendService


def test_valido_200(demo_findings: list[Finding]) -> None:
    """REQ-API-01: valid findings for mobility, crowding, and context return 200 and finding_ref."""
    app = create_app(service=BackendService())
    with TestClient(app) as client:
        for f in demo_findings:
            payload = f.model_dump(mode="json")
            resp = client.post(f"/api/v1/finding/{f.agent.value}", json=payload)
            assert resp.status_code == 200
            body = resp.json()
            assert body["contract_version"] == "1.0.0"
            assert body["finding"]["agent"] == f.agent.value
            assert body["finding"]["content"] == payload["content"]
            assert len(body["finding_ref"]) == 12


def test_density_422() -> None:
    """REQ-API-02: density outside [0, 1] returns 422 problem+json pointing to content.density."""
    app = create_app(service=BackendService())
    bad_payload: dict[str, Any] = {
        "agent": "crowding",
        "type": "density_alert",
        "content": {"density": 1.4, "zone_id": "Z_BAGNOLI"},
        "confidence": 0.82,
        "severity": "high",
        "source_id": "ir_sensors",
        "data_reference": "occupancy:2026-11-14T17:40:00+01:00",
        "is_simulated": True,
        "timestamp": "2026-11-14T17:40:00+01:00",
    }
    with TestClient(app) as client:
        resp = client.post("/api/v1/finding/crowding", json=bad_payload)
    assert resp.status_code == 422
    assert resp.headers["content-type"].startswith("application/problem+json")
    body = resp.json()
    assert body["code"] == "invalid_finding"
    assert body["status"] == 422
    assert "density" in body["field"]


def test_agent_mismatch() -> None:
    """REQ-API-03: agent in body differing from endpoint path returns 422 agent_mismatch."""
    app = create_app(service=BackendService())
    payload: dict[str, Any] = {
        "agent": "crowding",
        "type": "density_alert",
        "content": {"density": 0.91, "zone_id": "Z_BAGNOLI"},
        "confidence": 0.82,
        "severity": "high",
        "source_id": "ir_sensors",
        "data_reference": "occupancy:1",
        "is_simulated": True,
        "timestamp": "2026-11-14T17:40:00+01:00",
    }
    with TestClient(app) as client:
        resp = client.post("/api/v1/finding/mobility", json=payload)
    assert resp.status_code == 422
    assert resp.headers["content-type"].startswith("application/problem+json")
    body = resp.json()
    assert body["code"] == "agent_mismatch"
    assert body["field"] == "agent"


def test_rifiuto_non_500() -> None:
    """REQ-API-08: structured agent Refusal is an expected outcome (422 problem+json), never 500."""
    app = create_app(service=BackendService())
    refusal_payload = {
        "agent": "crowding",
        "reason_code": "missing_occupancy",
        "missing_input": ["occupancy_estimates"],
        "detail": "nessuna stima di occupazione disponibile",
    }
    with TestClient(app) as client:
        resp = client.post("/api/v1/finding/crowding", json=refusal_payload)
    assert resp.status_code == 422
    assert resp.headers["content-type"].startswith("application/problem+json")
    body = resp.json()
    assert body["code"] == "agent_refusal"
    assert body["refusal"]["reason_code"] == "missing_occupancy"

