"""Validate a proposed extraction and write it through DisruptionRepository."""

from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any

from app.config.sources import SourceDefinition
from app.domain.models.config import AppConfig
from app.domain.models.disruption import (
    DailyRecurrence,
    DisruptionEffect,
    DisruptionInput,
    DisruptionLinkInput,
    LifecycleStatus,
    LinkEntityType,
    Uncertainty,
    VerificationStatus,
)
from app.domain.models.finding import Severity
from app.repositories.disruptions import DisruptionRepository
from app.services.ingestion.extraction import NewsExtraction
from app.services.ingestion.resolver import ResolutionResult

_CATEGORY_ALERT_TYPE = {
    "strike": "strike",
    "closure": "closure",
    "diversion": "diversion",
    "delay": "delay",
    "service_change": "service_change",
    "elevator_outage": "elevator_outage",
    "weather_alert": "weather_alert",
    "accident": "accident",
    "roadworks": "roadworks",
    "event": "event",
    "seismic": "seismic",
    "airport": "airport",
    "port": "port",
    "other": "info",
}


class CatalogueError(RuntimeError):
    """The validated extraction could not be written safely."""


class DisruptionCataloguer:
    def __init__(
        self,
        disruption_repo: DisruptionRepository,
        config: AppConfig,
        *,
        is_simulated: bool = False,
    ) -> None:
        self._repo = disruption_repo
        self._config = config
        self._is_simulated = is_simulated

    @staticmethod
    def _alert_id(source_id: str, external_id: str) -> str:
        digest = hashlib.sha1(f"{source_id}\x00{external_id}".encode("utf-8")).hexdigest()
        return f"doc:{digest[:24]}"

    @staticmethod
    def _direction(extraction: NewsExtraction) -> str | None:
        if len(extraction.directions) != 1:
            return None
        value = extraction.directions[0].casefold()
        if any(token in value for token in ("andata", "forward", "pari", "dispari")):
            return "forward"
        if any(token in value for token in ("ritorno", "backward", "reverse")):
            return "backward"
        return None

    def _temporal_state(
        self,
        extraction: NewsExtraction,
        published_at: datetime,
        now: datetime,
    ) -> tuple[datetime, datetime | None, LifecycleStatus, datetime | None]:
        valid_from = extraction.valid_from
        explicit_start = valid_from is not None
        if valid_from is None:
            valid_from = published_at
        valid_to = extraction.valid_to
        if valid_to is not None and valid_to < valid_from:
            valid_to = None

        if extraction.lifecycle == "resolved":
            lifecycle = LifecycleStatus.RESOLVED
        elif extraction.lifecycle == "cancelled":
            lifecycle = LifecycleStatus.CANCELLED
        elif explicit_start or extraction.published_is_event_start:
            lifecycle = LifecycleStatus.ACTIVE
        else:
            # A publication date is not an event start. Keep the proposal but do
            # not let it block a journey until the uncertainty is resolved.
            lifecycle = LifecycleStatus.DRAFT

        if valid_to is None:
            next_review = max(now, valid_from) + timedelta(
                seconds=self._config.ingestion_review_ttl_s
            )
            # The maintenance job expires a still-unbounded active alert after
            # this TTL; this is explicit freshness, not eternal validity.
            ttl_expiry = max(now, valid_from) + timedelta(
                seconds=self._config.ingestion_unknown_expiry_ttl_s
            )
            next_review = min(next_review, ttl_expiry)
        else:
            next_review = valid_to
        return valid_from, valid_to, lifecycle, next_review

    def _matching_active_alert(
        self,
        source: SourceDefinition,
        resolution: ResolutionResult,
        now: datetime,
    ) -> str | None:
        """Find one same-source active alert for a correction/reopening notice."""
        targets = {
            (link.dataset_key, link.entity_type.value, link.entity_id)
            for link in resolution.links
            if link.status == "resolved"
        }
        if not targets:
            return None
        try:
            active = self._repo.list_relevant(
                now - timedelta(days=14),
                now + timedelta(days=1),
                include_simulated=self._is_simulated,
            )
        except Exception:
            return None
        source_id = f"ingest:{source.source_id}"
        matches: dict[str, Any] = {}
        for alert in active:
            if alert.source_id != source_id:
                continue
            for link in alert.links:
                if not link.is_current or not link.entity_id:
                    continue
                key = (link.dataset_key, link.entity_type.value, link.entity_id)
                if key in targets:
                    matches[alert.alert_id] = alert
                    break
        if len(matches) != 1:
            return None
        return next(iter(matches))

    def build(
        self,
        *,
        document: dict[str, Any],
        source: SourceDefinition,
        extraction: NewsExtraction,
        resolution: ResolutionResult,
        now: datetime | None = None,
        alert_id_override: str | None = None,
        existing: Any | None = None,
    ) -> DisruptionInput | None:
        if not extraction.relevant:
            return None
        ref = now or datetime.now(timezone.utc)
        published_at = document.get("published_at")
        if not isinstance(published_at, datetime):
            published_at = ref
        if published_at.tzinfo is None:
            published_at = published_at.replace(tzinfo=timezone.utc)
        valid_from, valid_to, lifecycle, next_review = self._temporal_state(
            extraction, published_at, ref
        )
        if existing is not None and existing.valid_from < valid_from:
            valid_from = existing.valid_from
        if lifecycle in (LifecycleStatus.RESOLVED, LifecycleStatus.CANCELLED):
            if valid_to is None:
                valid_to = ref
            next_review = None

        effect = {
            "block": DisruptionEffect.BLOCK,
            "penalize": DisruptionEffect.PENALIZE,
            "info": DisruptionEffect.INFO,
            "unknown": DisruptionEffect.INFO,
        }[extraction.effect]

        links: list[DisruptionLinkInput] = []
        unresolved_details: list[str] = list(extraction.unresolved_details)
        direction = self._direction(extraction)
        mode_value = extraction.modes[0].casefold() if extraction.modes else None
        service_date = valid_from.date() if valid_from else None
        for entity in resolution.links:
            if entity.status == "resolved":
                link_mode = entity.mode or mode_value
                links.append(
                    DisruptionLinkInput(
                        entity_type=entity.entity_type,
                        entity_id=entity.entity_id,
                        dataset_key=entity.dataset_key,
                        raw_reference=entity.raw_reference,
                        direction=direction,
                        mode=link_mode.casefold() if link_mode else None,
                        service_date=(
                            service_date if entity.entity_type is LinkEntityType.TRIP else None
                        ),
                        details={
                            **entity.details,
                            "resolution_status": entity.status,
                            "display_name": entity.display_name,
                        },
                    )
                )
            else:
                unresolved_details.append(
                    f"{entity.entity_type.value}:{entity.raw_reference}:{entity.status}"
                )
                links.append(
                    DisruptionLinkInput(
                        entity_type=entity.entity_type,
                        entity_id=entity.raw_reference,
                        dataset_key=entity.dataset_key,
                        raw_reference=entity.raw_reference,
                        mode=entity.mode or mode_value,
                        details={
                            **entity.details,
                            "resolution_status": entity.status,
                            "candidates": entity.candidates,
                        },
                    )
                )

        if effect in (DisruptionEffect.BLOCK, DisruptionEffect.PENALIZE) and not links:
            # No verifiable target: keep the finding as information for review,
            # never as an executable block with invented identifiers.
            effect = DisruptionEffect.INFO
            lifecycle = LifecycleStatus.DRAFT if lifecycle is LifecycleStatus.ACTIVE else lifecycle
            unresolved_details.append("nessuna entita risolta: effetto declassato a info")

        unresolved = bool(unresolved_details or resolution.unresolved or resolution.ambiguous)
        verification = (
            VerificationStatus.NEEDS_REVIEW if unresolved else VerificationStatus.UNVERIFIED
        )
        uncertainty = Uncertainty.HIGH if unresolved else Uncertainty(extraction.uncertainty)
        confidence = extraction.confidence
        if unresolved:
            confidence = min(confidence, 0.6)
        if lifecycle is LifecycleStatus.DRAFT:
            confidence = min(confidence, 0.55)

        recurrence = None
        if extraction.recurrence is not None:
            recurrence = DailyRecurrence(
                start=extraction.recurrence.start,
                end=extraction.recurrence.end,
                days=extraction.recurrence.days,
            )

        title = str(document.get("title") or "Avviso senza titolo")
        body = str(document.get("body_text") or "")
        if unresolved_details:
            body = f"{body}\n\n[Verifica richiesta: {'; '.join(unresolved_details)}]"
        source_id = f"ingest:{source.source_id}"
        alert_id = alert_id_override or self._alert_id(
            source.source_id, str(document.get("external_id") or "")
        )
        if alert_id_override:
            unresolved_details.append("rettifica/riapertura collegata a un avviso esistente")
        return DisruptionInput(
            source_id=source_id,
            alert_id=alert_id,
            source_url=document.get("canonical_url") or source.url,
            data_reference=document.get("canonical_url") or source.url,
            title=title[:500],
            description=body[:20000] or None,
            alert_type=_CATEGORY_ALERT_TYPE.get(extraction.category, "info"),
            effect=effect,
            severity=Severity(extraction.severity),
            confidence=float(confidence),
            published_at=published_at,
            observed_at=document.get("published_at")
            if isinstance(document.get("published_at"), datetime)
            else None,
            ingested_at=ref,
            valid_from=valid_from,
            valid_to=valid_to,
            timezone=source.timezone,
            lifecycle_status=lifecycle,
            verification_status=verification,
            uncertainty=uncertainty,
            is_simulated=self._is_simulated,
            next_review_at=next_review,
            recurrence=recurrence,
            links=links,
        )

    def catalogue(
        self,
        *,
        document: dict[str, Any],
        source: SourceDefinition,
        extraction: NewsExtraction,
        resolution: ResolutionResult,
        now: datetime | None = None,
    ) -> Any | None:
        ref = now or datetime.now(timezone.utc)
        alert_id_override = None
        existing = None
        if extraction.lifecycle in {"resolved", "cancelled"}:
            alert_id_override = self._matching_active_alert(
                source, resolution, ref
            )
            if alert_id_override:
                existing = self._repo.get(f"ingest:{source.source_id}", alert_id_override)
        proposal = self.build(
            document=document,
            source=source,
            extraction=extraction,
            resolution=resolution,
            now=ref,
            alert_id_override=alert_id_override,
            existing=existing,
        )
        if proposal is None:
            return None
        try:
            return self._repo.upsert(proposal)
        except Exception as exc:
            raise CatalogueError(f"scrittura perturbazione fallita: {exc}") from exc


__all__ = ["CatalogueError", "DisruptionCataloguer"]
