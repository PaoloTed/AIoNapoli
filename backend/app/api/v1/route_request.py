"""Route Request endpoint accepting informal natural language prompts (05_agente_input.md §6)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, ConfigDict, Field

from app.services.input.parser import RequestParser

router = APIRouter(prefix="/api/v1", tags=["route-request"])


class RouteRequestIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, description="Frase informale di richiesta percorso")


class RouteRequestOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trip_request: dict[str, Any] | None = None
    unresolved: list[dict[str, str]] = Field(default_factory=list)
    parser_mode: str = "regex"
    needs_clarification: bool = False
    question: str | None = None


@router.post("/route-request", response_model=RouteRequestOut)
def parse_route_request(
    payload: RouteRequestIn,
    request: Request,
) -> RouteRequestOut:
    """Parse natural language route prompt into TripRequest or request clarification."""
    service = getattr(request.app.state, "service", None)
    clock = getattr(service, "_clock", None) if service else None
    now = clock.now() if clock else None

    parser = RequestParser()
    trip_req, parsed_req, unresolved, question = parser.parse_request(payload.text, now=now)

    if trip_req is None:
        return RouteRequestOut(
            trip_request=None,
            unresolved=unresolved,
            parser_mode="regex",
            needs_clarification=True,
            question=question,
        )

    trip_dict = {
        "origin": trip_req.origin.model_dump(mode="python"),
        "destination": trip_req.destination.model_dump(mode="python"),
        "when": trip_req.when.isoformat(),
        "constraints": trip_req.constraints,
    }

    return RouteRequestOut(
        trip_request=trip_dict,
        unresolved=[],
        parser_mode="regex",
        needs_clarification=False,
        question=None,
    )
