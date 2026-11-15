"""HTTP endpoints for coordinate and natural-language journey planning."""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Request, Response
from pydantic import ValidationError
from shared.schemas.journeys import (
    JourneyPlanRequest,
    JourneyPlanResponse,
    JourneyPromptRequest,
    JourneyPromptResponse,
)
from starlette.concurrency import run_in_threadpool

from app.services.facade import BackendService
from app.services.input.agent import InputProviderUnavailable
from app.services.validation.finding_validator import (
    ValidationProblem,
    extract_field_from_pydantic_error,
)

router = APIRouter(prefix="/api/v1", tags=["journeys"])


def _get_service(request: Request) -> BackendService:
    return request.app.state.service


async def _json_object(request: Request, code: str, title: str) -> dict[str, Any]:
    raw_bytes = await request.body()
    try:
        payload: Any = json.loads(raw_bytes.decode("utf-8")) if raw_bytes else None
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValidationProblem(
            status=422,
            code=code,
            title=title,
            field="request",
            detail="corpo della richiesta non interpretabile come JSON UTF-8",
        ) from exc
    if not isinstance(payload, dict):
        raise ValidationProblem(
            status=422,
            code=code,
            title=title,
            field="request",
            detail="il corpo della richiesta deve essere un oggetto JSON",
        )
    return payload


@router.post("/journeys/plan", response_model=JourneyPlanResponse)
async def post_journey_plan(request: Request, response: Response) -> JourneyPlanResponse:
    """Plan a journey from origin/destination coordinates."""
    payload = await _json_object(
        request, "invalid_journey_request", "Richiesta di viaggio non valida"
    )
    try:
        journey_request = JourneyPlanRequest.model_validate(payload)
    except ValidationError as exc:
        first = exc.errors()[0] if exc.errors() else {}
        raise ValidationProblem(
            status=422,
            code="invalid_journey_request",
            title="Richiesta di viaggio non valida",
            field=extract_field_from_pydantic_error(first),
            detail=str(first.get("msg") or "input non conforme al contratto"),
        ) from exc

    service = _get_service(request)
    response.headers["Cache-Control"] = "no-store"
    return await run_in_threadpool(service.plan_journey, journey_request)


@router.post("/journeys", response_model=JourneyPromptResponse)
async def post_journey_prompt(request: Request, response: Response) -> JourneyPromptResponse:
    """Interpret a natural-language prompt and plan the same journey flow."""
    payload = await _json_object(
        request, "invalid_journey_prompt", "Richiesta di viaggio non valida"
    )
    try:
        prompt_request = JourneyPromptRequest.model_validate(payload)
    except ValidationError as exc:
        first = exc.errors()[0] if exc.errors() else {}
        raise ValidationProblem(
            status=422,
            code="invalid_journey_prompt",
            title="Prompt di viaggio non valido",
            field=extract_field_from_pydantic_error(first),
            detail=str(first.get("msg") or "input non conforme al contratto"),
        ) from exc

    service = _get_service(request)
    response.headers["Cache-Control"] = "no-store"
    try:
        return await run_in_threadpool(service.plan_journey_prompt, prompt_request)
    except InputProviderUnavailable as exc:
        raise ValidationProblem(
            status=503,
            code="input_provider_unavailable",
            title="Provider dell'Agente Input non disponibile",
            detail=str(exc),
        ) from exc
