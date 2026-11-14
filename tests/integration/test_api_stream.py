"""Integration tests for GET /api/v1/scenario/{id}/stream one-shot SSE protocol."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.domain.models.config import AppConfig
from app.main import create_app
from app.services.facade import BackendService
from app.utils.clock import FixedClock


def _parse_sse_frames(body_text: str) -> list[dict[str, str]]:
    frames: list[dict[str, str]] = []
    normalized = body_text.replace("\r\n", "\n")
    for block in normalized.split("\n\n"):
        lines = [line for line in block.split("\n") if line.strip() and not line.startswith(":")]
        if not lines:
            continue
        frame: dict[str, str] = {}
        for line in lines:
            if ":" in line:
                key, val = line.split(":", 1)
                frame[key.strip()] = val.strip()
        if frame:
            frames.append(frame)
    return frames


def test_ordine_eventi(app_config: AppConfig, fixed_clock: FixedClock) -> None:
    """REQ-API-06: SSE stream emits ordered trace events coherent with decision reasoning_log."""
    service = BackendService(config=app_config, clock=fixed_clock)
    app = create_app(service=service)
    with TestClient(app) as client:
        stream_resp = client.get("/api/v1/scenario/bagnoli/stream")
        assert stream_resp.status_code == 200
        assert stream_resp.headers["content-type"].startswith("text/event-stream")
        assert stream_resp.headers.get("cache-control") == "no-cache"
        assert stream_resp.headers.get("x-accel-buffering") == "no"

        dec_resp = client.post("/api/v1/decision", json={"scenario_id": "bagnoli"})
        assert dec_resp.status_code == 200
        dec_body = dec_resp.json()

    frames = _parse_sse_frames(stream_resp.text)
    events = [f.get("event") for f in frames]
    assert events[0] == "start"
    assert events[-1] == "decision"

    # Contiguous integer IDs starting from 1
    ids = [int(f["id"]) for f in frames]
    assert ids == list(range(1, len(frames) + 1))

    # Trace event sequence order
    assert "rule_evaluated" in events
    assert "conflict_detected" in events
    assert "priority_applied" in events
    assert "plan_item_created" in events

    idx_rule = events.index("rule_evaluated")
    idx_conflict = events.index("conflict_detected")
    idx_priority = events.index("priority_applied")
    idx_plan = events.index("plan_item_created")
    assert idx_rule < idx_conflict < idx_priority < idx_plan

    # Coherent decision_id and rule evaluation steps
    end_payload = json.loads(frames[-1]["data"])
    assert end_payload["decision_id"] == dec_body["decision_id"]

    rule_frames = [
        json.loads(f["data"])["rule_id"] for f in frames if f.get("event") == "rule_evaluated"
    ]
    reasoning_rules = [
        s["rule_applied"]
        for s in dec_body["decision"]["reasoning_log"]
        if s["rule_applied"].startswith("R")
    ]
    assert rule_frames[: len(reasoning_rules)] == reasoning_rules
