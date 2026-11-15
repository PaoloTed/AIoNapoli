"""Input agent clarification, selection and unsupported-constraint behavior."""

from __future__ import annotations

from shared.schemas.journeys import (
    Coordinate,
    JourneyPlanResponse,
    JourneyPromptRequest,
    JourneySource,
    ResolvedPlace,
)

from app.services.input.agent import InputAgent
from app.services.input.geocoder import PlaceCandidate, PlaceResolution
from app.services.orchestrator.config import load_config


class FakeResolver:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, str | None]] = []

    def resolve(
        self,
        text: str,
        role: str,
        *,
        client_location: Coordinate | None = None,
        selected_candidate_id: str | None = None,
    ) -> PlaceResolution:
        self.calls.append((text, role, selected_candidate_id))
        if text.casefold() in {"qui", "qua"} and client_location is None:
            return PlaceResolution(
                "needs_client_location",
                message="Per 'da qui' servono le coordinate condivise dal client.",
            )
        if text == "ambiguo" and not selected_candidate_id:
            return PlaceResolution(
                "ambiguous",
                candidates=[
                    PlaceCandidate("gtfs:anm:stop:1", "Uno", 40.8, 14.2, "stop"),
                    PlaceCandidate("gtfs:anm:stop:2", "Due", 40.9, 14.3, "stop"),
                ],
            )
        if text == "inesistente":
            return PlaceResolution("not_found", message="non trovato")
        return PlaceResolution(
            "resolved",
            place=ResolvedPlace(
                role=role,  # type: ignore[arg-type]
                label=text,
                lat=40.85,
                lon=14.25,
                source="stop",
                entity_id=selected_candidate_id or f"{role}:id",
            ),
        )


class FakePlanner:
    def __init__(self) -> None:
        self.requests = []

    def plan(self, request: object) -> JourneyPlanResponse:
        self.requests.append(request)
        return JourneyPlanResponse(
            status="ok",
            timezone="Europe/Rome",
            itineraries=[],
            source=JourneySource(
                source_id="otp", data_reference="http://otp.test", is_simulated=False
            ),
        )


def _agent() -> tuple[InputAgent, FakeResolver, FakePlanner]:
    resolver = FakeResolver()
    planner = FakePlanner()
    config = load_config().model_copy(update={"llm_mode": "off"})
    agent = InputAgent(config, resolver, planner)  # type: ignore[arg-type]
    return agent, resolver, planner


def test_missing_origin_requires_clarification() -> None:
    agent, _, _ = _agent()
    result = agent.interpret(
        JourneyPromptRequest(prompt="Portami a Chiaiano", timezone="Europe/Rome")
    )
    assert result.status == "needs_clarification"
    assert result.clarification is not None
    assert result.clarification.role == "origin"


def test_ambiguous_place_returns_stable_candidates_and_selection_is_used() -> None:
    agent, resolver, planner = _agent()
    first = agent.interpret(
        JourneyPromptRequest(
            prompt="Da ambiguo a Chiaiano domani alle 8",
            timezone="Europe/Rome",
        )
    )
    assert first.status == "needs_clarification"
    assert first.clarification is not None
    candidate_id = first.clarification.candidates[0].candidate_id
    second = agent.interpret(
        JourneyPromptRequest(
            prompt="Da ambiguo a Chiaiano domani alle 8",
            timezone="Europe/Rome",
            context={"selected_candidates": {"origin": candidate_id}},
        )
    )
    assert second.status == "ok"
    assert resolver.calls[-2][2] == candidate_id
    assert planner.requests


def test_unsupported_constraint_asks_before_proceeding() -> None:
    agent, _, _ = _agent()
    first = agent.interpret(
        JourneyPromptRequest(
            prompt="Da Chiaiano al MANN senza scale domani alle 8",
            timezone="Europe/Rome",
        )
    )
    assert first.status == "needs_clarification"
    assert first.clarification is not None
    assert first.clarification.role == "preference"
    second = agent.interpret(
        JourneyPromptRequest(
            prompt="Da Chiaiano al MANN senza scale domani alle 8",
            timezone="Europe/Rome",
            context={"accept_unsupported_constraints": True},
        )
    )
    assert second.status == "ok"
    assert second.journey is not None


def test_place_not_found_is_distinct() -> None:
    agent, _, _ = _agent()
    result = agent.interpret(
        JourneyPromptRequest(
            prompt="Da inesistente a Chiaiano domani alle 8",
            timezone="Europe/Rome",
        )
    )
    assert result.status == "place_not_found"


def test_client_location_required_for_here() -> None:
    agent, _, _ = _agent()
    result = agent.interpret(
        JourneyPromptRequest(prompt="Da qui a Chiaiano domani alle 8", timezone="Europe/Rome")
    )
    assert result.status == "needs_clarification"
    assert result.clarification is not None
    assert "coordinate" in result.clarification.question.casefold()
