"""HTTP endpoints for scenario snapshots and one-shot SSE trace streams."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from fastapi import APIRouter, Request
from shared.schemas.api import ScenarioResponse
from sse_starlette.sse import AppStatus, EventSourceResponse, ServerSentEvent

from app.services.facade import BackendService

router = APIRouter(prefix="/api/v1", tags=["scenarios"])


def _get_service(request: Request) -> BackendService:
    return request.app.state.service


@router.get("/scenario/{scenario_id}", response_model=ScenarioResponse)
async def get_scenario(scenario_id: str, request: Request) -> ScenarioResponse:
    """Return initial snapshot of scenario findings and optional real-time positions."""
    service = _get_service(request)
    return service.get_scenario_data(scenario_id)


@router.get("/scenario/{scenario_id}/stream")
async def stream_scenario(scenario_id: str, request: Request) -> EventSourceResponse:
    """Stream deterministic trace events as one-shot SSE ending with decision."""
    evt = AppStatus.should_exit_event
    if evt is not None and not AppStatus.should_exit:
        raw_evt = getattr(evt, "_event", evt)
        bound_loop = getattr(raw_evt, "_loop", None)
        if bound_loop is not None and bound_loop is not asyncio.get_running_loop():
            AppStatus.should_exit_event = None

    service = _get_service(request)
    frames = service.build_sse_events(scenario_id)

    async def event_generator() -> AsyncIterator[ServerSentEvent]:
        for frame in frames:
            yield ServerSentEvent(
                data=frame["data"],
                event=frame["event"],
                id=frame["id"],
                retry=frame.get("retry"),
            )

    return EventSourceResponse(
        event_generator(),
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
        media_type="text/event-stream; charset=utf-8",
        ping=3600,
    )
