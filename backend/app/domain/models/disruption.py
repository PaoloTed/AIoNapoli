"""Validated models for persistent disruptions and their entity links."""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, time, timezone
from enum import Enum
from typing import Any, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.models.finding import Severity


class DisruptionEffect(str, Enum):
    BLOCK = "block"
    PENALIZE = "penalize"
    INFO = "info"


class LifecycleStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    RESOLVED = "resolved"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class VerificationStatus(str, Enum):
    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    NEEDS_REVIEW = "needs_review"
    STALE = "stale"


class Uncertainty(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class LinkEntityType(str, Enum):
    ROUTE = "route"
    TRIP = "trip"
    STOP = "stop"
    OSM_WAY = "osm_way"
    OSM_POI = "osm_poi"


class ResolutionStatus(str, Enum):
    RESOLVED = "resolved"
    HISTORICAL = "historical"
    UNRESOLVED = "unresolved"


class Direction(str, Enum):
    BOTH = "both"
    FORWARD = "forward"
    BACKWARD = "backward"


def _aware(value: datetime, field: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} deve essere timezone-aware")
    return value


class DailyRecurrence(BaseModel):
    """A daily local-time window, not a continuous block."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["daily"] = "daily"
    start: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    end: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    days: list[int] = Field(default_factory=lambda: [0, 1, 2, 3, 4, 5, 6], min_length=1)

    @field_validator("days")
    @classmethod
    def _valid_days(cls, value: list[int]) -> list[int]:
        if any(day < 0 or day > 6 for day in value):
            raise ValueError("days deve contenere valori 0..6 (lunedì=0)")
        if len(set(value)) != len(value):
            raise ValueError("days non può contenere duplicati")
        return value

    @staticmethod
    def _clock(value: str) -> time:
        hour, minute = value.split(":")
        return time(hour=int(hour), minute=int(minute))

    def applies(self, local: datetime) -> bool:
        start = self._clock(self.start)
        end = self._clock(self.end)
        weekday = local.weekday()
        current = local.time().replace(second=0, microsecond=0)
        if start <= end:
            return weekday in self.days and start <= current <= end
        # Window across midnight: the start day owns the first part.
        return (current >= start and weekday in self.days) or (
            current <= end and ((weekday - 1) % 7) in self.days
        )


class DisruptionLinkInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity_type: LinkEntityType
    entity_id: str = Field(min_length=1)
    dataset_key: str | None = Field(default=None, min_length=1)
    dataset_version: str | None = Field(default=None, min_length=1)
    raw_reference: str | None = None
    direction: Direction | None = None
    mode: str | None = None
    from_stop_id: str | None = None
    to_stop_id: str | None = None
    from_stop_sequence: int | None = Field(default=None, ge=0)
    to_stop_sequence: int | None = Field(default=None, ge=0)
    service_date: date | None = None
    details: dict[str, Any] = Field(default_factory=dict)

    @field_validator("entity_id", "raw_reference", "dataset_key", "dataset_version")
    @classmethod
    def _strip_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @model_validator(mode="after")
    def _consistent_segment(self) -> DisruptionLinkInput:
        if (
            self.from_stop_sequence is not None
            and self.to_stop_sequence is not None
            and self.from_stop_sequence > self.to_stop_sequence
        ):
            raise ValueError("from_stop_sequence non può superare to_stop_sequence")
        if self.service_date is not None and self.entity_type is not LinkEntityType.TRIP:
            raise ValueError("service_date è ammessa solo per collegamenti trip")
        return self


class DisruptionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(min_length=1)
    alert_id: str = Field(min_length=1)
    source_url: str | None = None
    data_reference: str = Field(min_length=1)
    title: str = Field(min_length=1)
    description: str | None = None
    alert_type: str = Field(min_length=1)
    effect: DisruptionEffect
    severity: Severity
    confidence: float = Field(ge=0.0, le=1.0)
    published_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    observed_at: datetime | None = None
    ingested_at: datetime | None = None
    valid_from: datetime
    valid_to: datetime | None = None
    timezone: str = "Europe/Rome"
    lifecycle_status: LifecycleStatus = LifecycleStatus.ACTIVE
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
    uncertainty: Uncertainty = Uncertainty.MEDIUM
    is_simulated: bool
    next_review_at: datetime | None = None
    recurrence: DailyRecurrence | None = None
    links: list[DisruptionLinkInput] = Field(default_factory=list)

    @field_validator("source_id", "alert_id", "data_reference", "title", "alert_type")
    @classmethod
    def _non_empty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("campo obbligatorio vuoto")
        return stripped

    @field_validator("timezone")
    @classmethod
    def _valid_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"timezone sconosciuta: {value}") from exc
        return value

    @field_validator(
        "published_at",
        "observed_at",
        "ingested_at",
        "valid_from",
        "valid_to",
        "next_review_at",
    )
    @classmethod
    def _aware_times(cls, value: datetime | None, info: Any) -> datetime | None:
        if value is None:
            return None
        return _aware(value, info.field_name)

    @model_validator(mode="after")
    def _temporal_consistency(self) -> DisruptionInput:
        if self.valid_to is not None and self.valid_to < self.valid_from:
            raise ValueError("valid_to non può precedere valid_from")
        if self.lifecycle_status is LifecycleStatus.ACTIVE and self.valid_to is None:
            if self.verification_status is VerificationStatus.VERIFIED:
                raise ValueError(
                    "valid_to assente: uno stato verified senza scadenza non è ammesso"
                )
            if self.next_review_at is None:
                raise ValueError(
                    "valid_to assente: next_review_at è richiesto per la verifica periodica"
                )
        if self.effect in (DisruptionEffect.BLOCK, DisruptionEffect.PENALIZE) and not self.links:
            raise ValueError("blocco/penalizzazione richiede almeno un collegamento verificabile")
        return self

    def content_hash(self) -> str:
        payload = self.model_dump(mode="json")
        payload.pop("ingested_at", None)
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def is_temporally_applicable(self, at: datetime) -> bool:
        """Lifecycle/publication/validity/recurrence check; links add entity scope."""
        ref = _aware(at, "at")
        if self.lifecycle_status is not LifecycleStatus.ACTIVE:
            return False
        if self.published_at > ref:
            return False
        if self.valid_from > ref:
            return False
        if self.valid_to is not None and self.valid_to < ref:
            return False
        if self.recurrence is not None:
            local = ref.astimezone(ZoneInfo(self.timezone))
            return self.recurrence.applies(local)
        return True


class DisruptionLinkRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")

    link_ref: str
    entity_type: LinkEntityType
    entity_key: str | None = None
    entity_id: str | None = None
    raw_reference: str
    resolution_status: ResolutionStatus
    resolution_note: str | None = None
    dataset_key: str | None = None
    dataset_version: str | None = None
    direction: Direction | None = None
    mode: str | None = None
    from_stop_id: str | None = None
    to_stop_id: str | None = None
    from_stop_sequence: int | None = None
    to_stop_sequence: int | None = None
    service_date: date | None = None
    service_active: bool | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    is_current: bool = True


class DisruptionRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")

    source_id: str
    alert_id: str
    source_url: str | None = None
    data_reference: str
    title: str
    description: str | None = None
    alert_type: str
    effect: DisruptionEffect
    severity: Severity
    confidence: float
    published_at: datetime
    observed_at: datetime | None = None
    ingested_at: datetime
    valid_from: datetime
    valid_to: datetime | None = None
    timezone: str
    lifecycle_status: LifecycleStatus
    verification_status: VerificationStatus
    uncertainty: Uncertainty
    is_simulated: bool
    next_review_at: datetime | None = None
    recurrence: DailyRecurrence | None = None
    revision: int
    content_hash: str | None = None
    resolved_at: datetime | None = None
    cancelled_at: datetime | None = None
    updated_at: datetime | None = None
    links: list[DisruptionLinkRecord] = Field(default_factory=list)

    def is_temporally_applicable(self, at: datetime) -> bool:
        """Lifecycle/publication/validity/recurrence check, without link scope."""
        ref = _aware(at, "at")
        if self.lifecycle_status is not LifecycleStatus.ACTIVE:
            return False
        if self.published_at > ref:
            return False
        if self.valid_from > ref:
            return False
        if self.valid_to is not None and self.valid_to < ref:
            return False
        if self.recurrence is not None:
            local = ref.astimezone(ZoneInfo(self.timezone))
            if not self.recurrence.applies(local):
                return False
        return True

    def is_applicable_at(self, at: datetime, service_date: date | None = None) -> bool:
        ref = _aware(at, "at")
        if not self.is_temporally_applicable(ref):
            return False
        current_links = [
            link
            for link in self.links
            if link.is_current and link.resolution_status is ResolutionStatus.RESOLVED
        ]
        if not current_links:
            return False
        if service_date is not None and not any(
            link.service_date is None or link.service_date == service_date for link in current_links
        ):
            return False
        return True
