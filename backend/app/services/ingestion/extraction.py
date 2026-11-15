"""Validated semantic extraction of one document into a proposed event."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.config.sources import SourceDefinition
from app.domain.models.config import AppConfig
from app.services.ingestion.repository import IngestionRepository
from app.services.llm.client import (
    LlmClient,
    LlmError,
    LlmInvalidResponseError,
    LlmUnavailableError,
    build_llm_client,
    parse_json_content,
)
from app.services.llm.prompts import NEWS_SYSTEM_PROMPT, build_news_user_prompt


class ExtractionError(RuntimeError):
    """The model answered but the proposed extraction cannot be used."""


class EvidenceQuote(BaseModel):
    model_config = ConfigDict(extra="forbid")

    quote: str = Field(min_length=1)
    supports: str = ""


class RecurrenceWindow(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["daily"] = "daily"
    start: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    end: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    days: list[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4, 5, 6])

    @field_validator("days")
    @classmethod
    def _days(cls, value: list[int]) -> list[int]:
        if not value or any(day < 0 or day > 6 for day in value):
            raise ValueError("days deve contenere 0..6")
        return sorted(set(value))


class NewsExtraction(BaseModel):
    """Strict JSON contract proposed by the model and validated locally."""

    model_config = ConfigDict(extra="forbid")

    relevant: bool
    relevance_reason: str = ""
    category: Literal[
        "strike",
        "closure",
        "diversion",
        "delay",
        "service_change",
        "elevator_outage",
        "weather_alert",
        "accident",
        "roadworks",
        "event",
        "seismic",
        "airport",
        "port",
        "other",
    ] = "other"
    problem_type: str | None = None
    operator_names: list[str] = Field(default_factory=list)
    route_refs: list[str] = Field(default_factory=list)
    trip_refs: list[str] = Field(default_factory=list)
    stop_refs: list[str] = Field(default_factory=list)
    place_names: list[str] = Field(default_factory=list)
    road_refs: list[str] = Field(default_factory=list)
    modes: list[str] = Field(default_factory=list)
    directions: list[str] = Field(default_factory=list)
    effect: Literal["block", "penalize", "info", "unknown"] = "unknown"
    severity: Literal["low", "medium", "high", "critical"] = "medium"
    lifecycle: Literal["active", "resolved", "cancelled", "unknown"] = "unknown"
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    recurrence: RecurrenceWindow | None = None
    published_is_event_start: bool = False
    location_scope: Literal["local", "regional", "national", "unknown"] = "unknown"
    affects_public_transport: bool = False
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    uncertainty: Literal["low", "medium", "high"] = "high"
    evidence: list[EvidenceQuote] = Field(default_factory=list)
    unresolved_details: list[str] = Field(default_factory=list)
    notes: str = ""

    @field_validator(
        "operator_names",
        "route_refs",
        "trip_refs",
        "stop_refs",
        "place_names",
        "road_refs",
        "modes",
        "directions",
        "unresolved_details",
    )
    @classmethod
    def _clean_list(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(item.strip() for item in value if item.strip()))

    def localized(self, timezone: str) -> NewsExtraction:
        try:
            tz = ZoneInfo(timezone)
        except ZoneInfoNotFoundError:
            tz = ZoneInfo("Europe/Rome")
        updates: dict[str, Any] = {}
        for field in ("valid_from", "valid_to"):
            value = getattr(self, field)
            if value is not None and value.tzinfo is None:
                updates[field] = value.replace(tzinfo=tz)
        return self.model_copy(update=updates) if updates else self


class ExtractionOutcome(BaseModel):
    extraction: NewsExtraction
    model: str
    cached: bool
    latency_ms: int | None = None


class NewsExtractor:
    """Cache-aware, schema-validated model call for a single new document."""

    def __init__(
        self,
        repository: IngestionRepository,
        config: AppConfig,
        *,
        client: LlmClient | None = None,
    ) -> None:
        self._repo = repository
        self._config = config
        self._client = client

    @property
    def client(self) -> LlmClient:
        if self._client is None:
            self._client = build_llm_client(self._config)
        return self._client

    def interpret(self, document: dict[str, Any], source: SourceDefinition) -> ExtractionOutcome:
        document_id = int(document["document_id"])
        content_hash = str(document["content_hash"])
        prompt_version = self._config.llm_prompt_version
        schema_version = self._config.llm_schema_version
        model = self._config.llm_model or (
            getattr(self._client, "model", None) if self._client is not None else None
        )
        model = str(model or "unconfigured")
        language = str(document.get("language") or source.language)

        cached = self._repo.cached_interpretation(
            document_id,
            content_hash=content_hash,
            prompt_version=prompt_version,
            schema_version=schema_version,
            model=model,
            language=language,
        )
        if cached and cached.get("status") in {"ok", "irrelevant"}:
            output = cached.get("output")
            if isinstance(output, dict):
                try:
                    return ExtractionOutcome(
                        extraction=NewsExtraction.model_validate(output),
                        model=model,
                        cached=True,
                        latency_ms=cached.get("latency_ms"),
                    )
                except Exception:
                    pass

        user_prompt = build_news_user_prompt(
            source_id=source.source_id,
            source_class=source.source_class,
            source_name=source.name,
            title=str(document.get("title") or ""),
            body=str(document.get("body_text") or ""),
            published_at=(
                document["published_at"].isoformat()
                if isinstance(document.get("published_at"), datetime)
                else str(document.get("published_at") or "")
            ),
            url=document.get("canonical_url"),
            language=language,
        )
        try:
            response = self.client.complete_json(
                NEWS_SYSTEM_PROMPT, user_prompt, schema_name="news_extraction"
            )
        except LlmUnavailableError as exc:
            self._repo.save_interpretation(
                document_id,
                content_hash=content_hash,
                prompt_version=prompt_version,
                schema_version=schema_version,
                model=model,
                language=language,
                status="error",
                output=None,
                error=f"provider_unavailable: {exc}",
                latency_ms=None,
            )
            raise
        except LlmError as exc:
            self._repo.save_interpretation(
                document_id,
                content_hash=content_hash,
                prompt_version=prompt_version,
                schema_version=schema_version,
                model=model,
                language=language,
                status="error",
                output=None,
                error=str(exc),
                latency_ms=None,
            )
            raise

        try:
            payload = parse_json_content(response.text)
            extraction = NewsExtraction.model_validate(payload).localized(source.timezone)
        except (LlmInvalidResponseError, ValueError) as exc:
            self._repo.save_interpretation(
                document_id,
                content_hash=content_hash,
                prompt_version=prompt_version,
                schema_version=schema_version,
                model=model,
                language=language,
                status="invalid",
                output=None,
                error=str(exc),
                latency_ms=response.latency_ms,
            )
            raise ExtractionError(f"estrazione non conforme allo schema: {exc}") from exc

        status = "ok" if extraction.relevant else "irrelevant"
        self._repo.save_interpretation(
            document_id,
            content_hash=content_hash,
            prompt_version=prompt_version,
            schema_version=schema_version,
            model=model,
            language=language,
            status=status,
            output=extraction.model_dump(mode="json"),
            error=None,
            latency_ms=response.latency_ms,
        )
        return ExtractionOutcome(
            extraction=extraction,
            model=response.model or model,
            cached=False,
            latency_ms=response.latency_ms,
        )


__all__ = [
    "EvidenceQuote",
    "ExtractionError",
    "ExtractionOutcome",
    "NewsExtraction",
    "NewsExtractor",
    "RecurrenceWindow",
]
