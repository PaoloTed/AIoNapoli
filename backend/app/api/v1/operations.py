"""Backend inspection endpoints for disruptions and ingestion state."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query, Request

from app.services.facade import BackendService

router = APIRouter(prefix="/api/v1", tags=["operations"])


def _service(request: Request) -> BackendService:
    return request.app.state.service


@router.get("/disruptions")
def list_disruptions(
    request: Request,
    include_simulated: bool = Query(default=False),
    window_hours: int = Query(default=168, ge=1, le=24 * 31),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[dict[str, Any]]:
    return _service(request).list_disruptions(
        include_simulated=include_simulated,
        window_hours=window_hours,
        limit=limit,
    )


@router.get("/disruptions/{source_id}/{alert_id}")
def get_disruption(request: Request, source_id: str, alert_id: str) -> dict[str, Any]:
    return _service(request).get_disruption(source_id, alert_id)


@router.get("/ingestion/sources")
def ingestion_sources(request: Request) -> list[dict[str, Any]]:
    return _service(request).ingestion_sources()


@router.get("/ingestion/documents")
def ingestion_documents(
    request: Request,
    status: str | None = Query(default=None),
    source_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[dict[str, Any]]:
    return _service(request).ingestion_documents(status=status, source_id=source_id, limit=limit)


@router.get("/ingestion/status")
def ingestion_status(request: Request) -> dict[str, Any]:
    return _service(request).ingestion_status()


@router.get("/ingestion/fetches")
def ingestion_fetches(
    request: Request,
    source_id: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[dict[str, Any]]:
    return _service(request).ingestion_fetches(source_id=source_id, limit=limit)
