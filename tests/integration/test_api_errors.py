"""Integration tests for RFC 9457 error handling and machine-readable error codes."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app
from app.services.facade import BackendService


def test_mai_500() -> None:
    """REQ-API-05: malformed or invalid payloads never produce HTTP 500."""
    app = create_app(service=BackendService())
    with TestClient(app) as client:
        responses = [
            client.post(
                "/api/v1/finding/crowding",
                content=b"{not-valid-json",
                headers={"Content-Type": "application/json"},
            ),
            client.post("/api/v1/finding/crowding", content=b""),
            client.post("/api/v1/finding/crowding", json=["unexpected", "list"]),
            client.post(
                "/api/v1/decision",
                content=b"{broken",
                headers={"Content-Type": "application/json"},
            ),
            client.post("/api/v1/decision", json={}),
            client.post("/api/v1/decision", json={"findings": []}),
            client.post("/api/v1/decision", json={"scenario_id": "bagnoli", "findings": []}),
            client.get("/api/v1/scenario/non_esiste"),
        ]

    for resp in responses:
        assert resp.status_code != 500
        assert resp.status_code in (404, 422)
        assert resp.headers["content-type"].startswith("application/problem+json")


def test_codici() -> None:
    """NFR-06: every exposed HTTP error carries a stable code and field when applicable."""
    app = create_app(service=BackendService())
    with TestClient(app) as client:
        # 1. missing_finding
        r_missing = client.post("/api/v1/decision", json={"findings": []})
        assert r_missing.status_code == 422
        b_missing = r_missing.json()
        assert b_missing["code"] == "missing_finding"
        assert b_missing["field"] == "findings"

        # 2. invalid_finding (duplicate agent)
        dup_finding = {
            "agent": "mobility",
            "type": "route_disruption",
            "content": {"zone_id": "Z_BAGNOLI"},
            "confidence": 0.9,
            "severity": "high",
            "source_id": "anm",
            "data_reference": "rss:1",
            "is_simulated": False,
            "timestamp": "2026-11-14T16:12:00+01:00",
        }
        r_dup = client.post("/api/v1/decision", json={"findings": [dup_finding, dup_finding]})
        assert r_dup.status_code == 422
        b_dup = r_dup.json()
        assert b_dup["code"] == "invalid_finding"
        assert b_dup["field"] == "findings.agent"

        # 3. scenario_not_found
        r_scen = client.get("/api/v1/scenario/unknown_zone")
        assert r_scen.status_code == 404
        b_scen = r_scen.json()
        assert b_scen["code"] == "scenario_not_found"
        assert b_scen["field"] == "scenario_id"

        # 4. agent_mismatch
        r_mismatch = client.post("/api/v1/finding/context", json=dup_finding)
        assert r_mismatch.status_code == 422
        b_mismatch = r_mismatch.json()
        assert b_mismatch["code"] == "agent_mismatch"
        assert b_mismatch["field"] == "agent"
