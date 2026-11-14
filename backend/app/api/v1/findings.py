"""HTTP endpoint for submitting and validating agent findings."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Request
from shared.schemas.api import FindingResponse
from shared.schemas.enums import AgentName

from app.services.facade import BackendService
from app.services.validation.finding_validator import ValidationProblem

router = APIRouter(prefix="/api/v1", tags=["findings"])


def _get_service(request: Request) -> BackendService:
    return request.app.state.service


@router.post("/finding/{agent}", response_model=FindingResponse)
async def post_finding(agent: AgentName, request: Request) -> FindingResponse:
    """Validate and persist a Finding submitted by or on behalf of an agent."""
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
    return service.submit_finding(agent, payload)
