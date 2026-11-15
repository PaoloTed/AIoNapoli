"""Agent Input: natural prompt -> validated places/times/preferences -> journey."""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field
from shared.schemas.journeys import (
    Clarification,
    Coordinate,
    JourneyPlanRequest,
    JourneyPreferences,
    JourneyPromptRequest,
    JourneyPromptResponse,
    PromptInterpretation,
)

from app.domain.models.config import AppConfig
from app.services.input.geocoder import PlaceResolution, PlaceResolver
from app.services.input.prompt_parser import parse_prompt
from app.services.journeys import JourneyPlanner
from app.services.llm.client import (
    LlmClient,
    LlmError,
    LlmInvalidResponseError,
    LlmUnavailableError,
    build_llm_client,
)
from app.services.llm.prompts import PROMPT_SYSTEM_PROMPT, build_prompt_user_prompt


class InputProviderUnavailable(RuntimeError):
    """The required input model is not available."""


class PromptLlmOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    origin_text: str | None = None
    destination_text: str | None = None
    depart_phrase: str | None = None
    arrive_phrase: str | None = None
    preferences: dict[str, Any] = Field(default_factory=dict)
    uses_client_location: bool = False
    clarification_questions: list[str] = Field(default_factory=list)
    contradictions: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


_MODE_MAP = {
    "walk": "WALK",
    "a piedi": "WALK",
    "bus": "BUS",
    "autobus": "BUS",
    "metro": "SUBWAY",
    "metropolitana": "SUBWAY",
    "subway": "SUBWAY",
    "treno": "RAIL",
    "rail": "RAIL",
    "tram": "TRAM",
    "funicolare": "FUNICULAR",
    "funicular": "FUNICULAR",
    "traghetto": "FERRY",
    "ferry": "FERRY",
}


def _clarification_id(prompt: str, role: str, candidate_ids: list[str]) -> str:
    raw = f"{prompt}\x00{role}\x00{'|'.join(candidate_ids)}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:20]


class InputAgent:
    """Invokes the model when available and a declared deterministic fallback."""

    def __init__(
        self,
        config: AppConfig,
        resolver: PlaceResolver,
        journey_planner: JourneyPlanner,
        *,
        llm_client: LlmClient | None = None,
    ) -> None:
        self.config = config
        self.resolver = resolver
        self.journey_planner = journey_planner
        self._llm = llm_client

    @property
    def llm(self) -> LlmClient:
        if self._llm is None:
            self._llm = build_llm_client(self.config)
        return self._llm

    def interpret(self, request: JourneyPromptRequest) -> JourneyPromptResponse:
        timezone = ZoneInfo(request.timezone)
        now = datetime.now(timezone)
        warnings: list[str] = []
        parser = "deterministic"
        llm_output: PromptLlmOutput | None = None
        try:
            llm_output = self._call_llm(request, now, timezone)
            parser = "llm"
        except LlmUnavailableError as exc:
            if self.config.input_agent_llm_required:
                raise InputProviderUnavailable(
                    f"Agente Input richiede il modello ma non e' disponibile: {exc}"
                ) from exc
            warnings.append(f"modello Input non disponibile: usato parser deterministico ({exc})")
        except (LlmInvalidResponseError, LlmError, ValueError) as exc:
            if self.config.input_agent_llm_required:
                raise InputProviderUnavailable(f"output Agente Input non valido: {exc}") from exc
            warnings.append(f"output modello Input non valido: usato parser deterministico ({exc})")

        if llm_output is not None:
            parsed = self._from_llm(request.prompt, llm_output, now=now, timezone=timezone)
            parsed.warnings = [*parsed.warnings, *warnings]
            warnings = parsed.warnings
        else:
            parsed = parse_prompt(request.prompt, now=now, timezone=timezone)
            warnings.extend(parsed.warnings)

        interpretation = PromptInterpretation(
            origin_text=parsed.origin_text,
            destination_text=parsed.destination_text,
            depart_at=parsed.depart_at,
            arrive_by=parsed.arrive_by,
            preferences=parsed.preferences,
            transit_only=parsed.transit_only,
            parser=parser,  # type: ignore[arg-type]
            warnings=list(dict.fromkeys(warnings)),
            contradictions=parsed.contradictions,
            uses_client_location=self._uses_client_location(
                parsed.origin_text, parsed.destination_text
            ),
            confidence=llm_output.confidence if llm_output else 0.8,
        )

        if interpretation.contradictions:
            return JourneyPromptResponse(
                status="invalid_request",
                timezone=request.timezone,
                prompt=request.prompt,
                interpretation=interpretation,
            )

        if parsed.preferences.unsupported_constraints and not self._accept_unsupported(
            request.context
        ):
            question = (
                "Non posso garantire questi vincoli con i dati disponibili: "
                + ", ".join(parsed.preferences.unsupported_constraints)
                + ". Vuoi procedere senza?"
            )
            return self._clarification_response(
                request,
                interpretation,
                role="preference",
                question=question,
                candidates=[],
            )

        if parsed.preferences.unsupported_constraints:
            interpretation.warnings.append(
                "vincoli non supportati ignorati su conferma esplicita: "
                + ", ".join(parsed.preferences.unsupported_constraints)
            )

        if not parsed.origin_text or not parsed.destination_text:
            role = (
                "origin_destination"
                if not parsed.origin_text and not parsed.destination_text
                else ("origin" if not parsed.origin_text else "destination")
            )
            question = {
                "origin": "Da quale luogo vuoi partire?",
                "destination": "Qual e' la destinazione?",
                "origin_destination": "Indica origine e destinazione del viaggio.",
            }[role]
            return self._clarification_response(
                request, interpretation, role=role, question=question, candidates=[]
            )

        selected = self._selected_candidates(request.context)
        origin = self.resolver.resolve(
            parsed.origin_text,
            "origin",
            client_location=request.client_location,
            selected_candidate_id=selected.get("origin"),
        )
        if origin.status != "resolved":
            return self._place_response(request, interpretation, "origin", origin)
        destination = self.resolver.resolve(
            parsed.destination_text,
            "destination",
            client_location=request.client_location,
            selected_candidate_id=selected.get("destination"),
        )
        if destination.status != "resolved":
            return self._place_response(request, interpretation, "destination", destination)
        assert origin.place is not None and destination.place is not None

        journey_request = JourneyPlanRequest(
            origin=Coordinate(lat=origin.place.lat, lon=origin.place.lon),
            destination=Coordinate(lat=destination.place.lat, lon=destination.place.lon),
            depart_at=parsed.depart_at if parsed.arrive_by is None else None,
            arrive_by=parsed.arrive_by,
            timezone=request.timezone,
            modes=parsed.preferences.modes,
            transit_only=parsed.transit_only,
            first=request.first or self.config.journey_default_first,
            preferences=parsed.preferences,
        )
        if parsed.depart_at is not None and parsed.arrive_by is not None:
            interpretation.warnings.append(
                "partenza e arrivo richiesti insieme: usato il vincolo di arrivo OTP"
            )
        if destination.place.approximate:
            interpretation.warnings.append(
                f"destinazione approssimata: {destination.place.label} "
                f"({destination.place.detail or 'punto rappresentativo'})"
            )
        if origin.place.approximate:
            interpretation.warnings.append(
                f"origine approssimata: {origin.place.label} "
                f"({origin.place.detail or 'punto rappresentativo'})"
            )
        journey = self.journey_planner.plan(journey_request)
        journey.resolved_places = [origin.place, destination.place]
        journey.request_interpretation = interpretation
        return JourneyPromptResponse(
            status=journey.status,
            timezone=request.timezone,
            prompt=request.prompt,
            interpretation=interpretation,
            resolved_places=[origin.place, destination.place],
            journey=journey,
        )

    def _call_llm(
        self, request: JourneyPromptRequest, now: datetime, timezone: ZoneInfo
    ) -> PromptLlmOutput:
        location = (
            f"{request.client_location.lat},{request.client_location.lon}"
            if request.client_location
            else None
        )
        response = self.llm.complete_json(
            PROMPT_SYSTEM_PROMPT,
            build_prompt_user_prompt(
                request.prompt,
                now_local=now.isoformat(),
                client_location=location,
            ),
            schema_name="journey_prompt",
        )
        from app.services.llm.client import parse_json_content

        return PromptLlmOutput.model_validate(parse_json_content(response.text))

    def _from_llm(
        self,
        prompt: str,
        output: PromptLlmOutput,
        *,
        now: datetime,
        timezone: ZoneInfo,
    ) -> Any:
        synthetic = f"da {output.origin_text or 'luogo'} a {output.destination_text or 'luogo'}"
        if output.depart_phrase:
            synthetic += f" {output.depart_phrase}"
        if output.arrive_phrase:
            synthetic += f" {output.arrive_phrase}"
        parsed = parse_prompt(synthetic, now=now, timezone=timezone)
        parsed.origin_text = output.origin_text
        parsed.destination_text = output.destination_text
        parsed.contradictions = list(
            dict.fromkeys([*parsed.contradictions, *output.contradictions])
        )
        preferences = output.preferences if isinstance(output.preferences, dict) else {}
        modes = []
        for item in (
            preferences.get("modes", []) if isinstance(preferences.get("modes"), list) else []
        ):
            mapped = _MODE_MAP.get(str(item).strip().casefold())
            if mapped:
                modes.append(mapped)
        if modes and "WALK" not in modes:
            modes.insert(0, "WALK")
        parsed.preferences = JourneyPreferences(
            minimize_walk=bool(preferences.get("minimize_walk", False)),
            minimize_transfers=bool(preferences.get("minimize_transfers", False)),
            modes=modes or parsed.preferences.modes,
            unsupported_constraints=[
                str(item)
                for item in preferences.get("unsupported_constraints", [])
                if str(item).strip()
            ]
            if isinstance(preferences.get("unsupported_constraints"), list)
            else parsed.preferences.unsupported_constraints,
        )
        parsed.transit_only = bool(preferences.get("transit_only", parsed.transit_only))
        parsed.warnings.extend(output.clarification_questions)
        return parsed

    def _selected_candidates(self, context: dict[str, Any]) -> dict[str, str]:
        result: dict[str, str] = {}
        if not isinstance(context, dict):
            return result
        selected = context.get("selected_candidates")
        if isinstance(selected, dict):
            for role in ("origin", "destination"):
                value = selected.get(role)
                if isinstance(value, str) and value.strip():
                    result[role] = value.strip()
        for role in ("origin", "destination"):
            value = context.get(f"{role}_candidate_id")
            if isinstance(value, str) and value.strip():
                result[role] = value.strip()
        single = context.get("selected_candidate_id")
        if isinstance(single, str) and single.strip():
            for role in ("origin", "destination"):
                result.setdefault(role, single.strip())
        return result

    def _accept_unsupported(self, context: dict[str, Any]) -> bool:
        if not isinstance(context, dict):
            return False
        value = context.get("accept_unsupported_constraints")
        return value is True or str(value).lower() in {"1", "true", "yes", "si", "sì"}

    @staticmethod
    def _uses_client_location(origin: str | None, destination: str | None) -> bool:
        text = f"{origin or ''} {destination or ''}".casefold()
        return any(token in text for token in ("qui", "qua", "posizione attuale", "dove sono"))

    def _clarification_response(
        self,
        request: JourneyPromptRequest,
        interpretation: PromptInterpretation,
        *,
        role: str,
        question: str,
        candidates: list[Any],
    ) -> JourneyPromptResponse:
        candidate_ids = [candidate.candidate_id for candidate in candidates]
        return JourneyPromptResponse(
            status="needs_clarification",
            timezone=request.timezone,
            prompt=request.prompt,
            interpretation=interpretation,
            clarification=Clarification(
                clarification_id=_clarification_id(request.prompt, role, candidate_ids),
                role=role,  # type: ignore[arg-type]
                question=question,
                candidates=[candidate.to_schema() for candidate in candidates],
            ),
        )

    def _place_response(
        self,
        request: JourneyPromptRequest,
        interpretation: PromptInterpretation,
        role: str,
        resolution: PlaceResolution,
    ) -> JourneyPromptResponse:
        if resolution.status == "not_found":
            return JourneyPromptResponse(
                status="place_not_found",
                timezone=request.timezone,
                prompt=request.prompt,
                interpretation=interpretation,
                clarification=Clarification(
                    clarification_id=_clarification_id(request.prompt, role, []),
                    role=role,  # type: ignore[arg-type]
                    question=resolution.message
                    or f"Non trovo il luogo per {role}. Puoi indicarlo diversamente?",
                    candidates=[],
                ),
            )
        if resolution.status == "needs_client_location":
            return JourneyPromptResponse(
                status="needs_clarification",
                timezone=request.timezone,
                prompt=request.prompt,
                interpretation=interpretation,
                clarification=Clarification(
                    clarification_id=_clarification_id(request.prompt, role, []),
                    role=role,  # type: ignore[arg-type]
                    question=resolution.message
                    or "Per 'da qui' servono le coordinate condivise dal client.",
                    candidates=[],
                ),
            )
        question = (
            "Ho trovato piu' luoghi per l' origine. Quale intendi?"
            if role == "origin"
            else "Ho trovato piu' luoghi per la destinazione. Quale intendi?"
        )
        return JourneyPromptResponse(
            status="needs_clarification",
            timezone=request.timezone,
            prompt=request.prompt,
            interpretation=interpretation,
            clarification=Clarification(
                clarification_id=_clarification_id(
                    request.prompt, role, [c.candidate_id for c in resolution.candidates]
                ),
                role=role,  # type: ignore[arg-type]
                question=question,
                candidates=[candidate.to_schema() for candidate in resolution.candidates],
            ),
        )


__all__ = ["InputAgent", "InputProviderUnavailable", "PromptLlmOutput"]
