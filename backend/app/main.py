"""FastAPI application factory for Napoli Agentic City backend."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.middleware.errors import register_exception_handlers
from app.api.v1.decisions import router as decisions_router
from app.api.v1.findings import router as findings_router
from app.api.v1.journeys import router as journeys_router
from app.api.v1.operations import router as operations_router
from app.api.v1.scenarios import router as scenarios_router
from app.services.facade import BackendService
from app.services.orchestrator.config import load_config


def create_app(service: BackendService | None = None) -> FastAPI:
    """Create and configure the FastAPI application with fail-fast config loading."""
    if service is None:
        config = load_config()
        resolved_service = BackendService(config=config)
    else:
        resolved_service = service

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        yield
        resolved_service.close()

    application = FastAPI(
        title="Napoli Agentic City Backend",
        version="1.0.0",
        lifespan=lifespan,
    )
    application.state.service = resolved_service

    application.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_service.config.cors_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type"],
    )

    register_exception_handlers(application)
    application.include_router(findings_router)
    application.include_router(decisions_router)
    application.include_router(scenarios_router)
    application.include_router(journeys_router)
    application.include_router(operations_router)
    return application


app = create_app()
