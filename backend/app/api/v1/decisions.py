"""HTTP endpoint for producing deterministic orchestrator decisions."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Request, Response
from shared.schemas.api import DecisionResponse

from app.services.facade import BackendService
from app.services.validation.finding_validator import ValidationProblem

router = APIRouter(prefix="/api/v1", tags=["decisions"])


def _get_service(request: Request) -> BackendService:
    return request.app.state.service


@router.post("/decision", response_model=DecisionResponse)
async def post_decision(request: Request, response: Response) -> DecisionResponse:
    """Produce a deterministic Decision envelope from scenario_id or explicit findings."""
    raw_bytes = await request.body()
    try:
        payload: Any = json.loads(raw_bytes.decode("utf-8")) if raw_bytes else None
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValidationProblem(
            status=422,
            code="invalid_finding",
            title="JSON non valido",
            field="request",
            detail="corpo della richiesta non interpretabile come JSON UTF-8",
        ) from exc

    service = _get_service(request)
    decision_resp, _ = service.decide_from_request(payload)
    response.headers["Cache-Control"] = "no-store"
    return decision_resp
