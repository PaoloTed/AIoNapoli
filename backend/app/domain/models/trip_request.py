"""Pure domain models for trip requests and natural language input parsing."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ParsedLocation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    raw_text: str
    kind_guess: Literal["zone", "poi", "address", "coordinate", "unknown"] = "unknown"


class ParsedRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    origin: ParsedLocation | None = None
    destination: ParsedLocation | None = None
    when_iso: datetime | None = None
    when_was_relative: bool = False
    when_source_text: str | None = None
    constraints: dict[str, Any] = Field(default_factory=dict)
    unresolved_hints: tuple[str, ...] = ()
    parser_confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class TripLocation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    label: str
    lat: float
    lon: float
    kind: Literal["zone", "stop", "poi", "address", "coordinate"]
    resolved_by: Literal["dictionary", "nominatim", "user"]


class TripRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    origin: TripLocation
    destination: TripLocation
    when: datetime
    constraints: dict[str, Any] = Field(default_factory=dict)
