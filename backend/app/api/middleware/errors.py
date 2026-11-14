"""RFC 9457 application/problem+json error middleware and exception handlers."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from shared.schemas.api import ProblemDetail

from app.services.orchestrator.config import ConfigInvalidError
from app.services.validation.finding_validator import (
    ValidationProblem,
    extract_field_from_pydantic_error,
)

PROBLEM_BASE_URI = "https://napoli-agentic-city/errors"
PROBLEM_MEDIA_TYPE = "application/problem+json"


def build_problem_response(
    *,
    status: int,
    code: str,
    title: str,
    detail: str,
    instance: str,
    field: str | None = None,
    refusal: Any = None,
) -> JSONResponse:
    """Create a RFC 9457 Problem+JSON JSONResponse."""
    problem = ProblemDetail(
        type=f"{PROBLEM_BASE_URI}/{code}",
        title=title,
        status=status,
        code=code,
        field=field,
        detail=detail,
        instance=instance,
        refusal=refusal,
    )
    return JSONResponse(
        status_code=status,
        content=problem.model_dump(mode="json", exclude_none=True),
        media_type=PROBLEM_MEDIA_TYPE,
    )


def register_exception_handlers(app: FastAPI) -> None:
    """Attach problem+json exception handlers to the FastAPI application."""

    @app.exception_handler(ValidationProblem)
    async def handle_validation_problem(request: Request, exc: ValidationProblem) -> JSONResponse:
        return build_problem_response(
            status=exc.status,
            code=exc.code,
            title=exc.title,
            detail=exc.detail,
            instance=request.url.path,
            field=exc.field,
            refusal=exc.refusal,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_request_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        errors = exc.errors()
        first = errors[0] if errors else {}
        field_name = extract_field_from_pydantic_error(first)
        if first.get("type") == "json_invalid":
            field_name = "request"
            detail = "JSON malformato nel corpo della richiesta"
        else:
            detail = str(first.get("msg") or "input non conforme al contratto")
        return build_problem_response(
            status=422,
            code="invalid_finding",
            title="Richiesta non conforme",
            detail=detail,
            instance=request.url.path,
            field=field_name,
        )

    @app.exception_handler(ConfigInvalidError)
    async def handle_config_invalid(request: Request, exc: ConfigInvalidError) -> JSONResponse:
        return build_problem_response(
            status=500,
            code="config_invalid",
            title="Configurazione non valida",
            detail=exc.detail,
            instance=request.url.path,
            field=exc.field,
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        return build_problem_response(
            status=500,
            code="internal_error",
            title="Errore interno",
            detail=f"errore imprevisto: {type(exc).__name__}",
            instance=request.url.path,
        )
