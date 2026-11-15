"""Context Supervisor orchestrating context workers (02_architettura_agentica.md §6.3)."""

from __future__ import annotations

from datetime import datetime, timezone

from app.domain.models.finding import AgentName, Finding, FindingType, Severity
from app.domain.models.refusal import Refusal
from app.repositories.base import SourceRepository
from app.services.agents.base import AgentCapability, RunContext, WorkerProtocol
from app.services.agents.blackboard import Blackboard
from app.services.agents.context.workers import (
    AlertReader,
    EventWindowChecker,
    ImpactAssessor,
    WeatherMapper,
)


class ContextSupervisor:
    name = "context_supervisor"
    capabilities = {
        AgentCapability.READ_ALERTS,
        AgentCapability.MAP_WEATHER,
        AgentCapability.CHECK_EVENT_WINDOW,
        AgentCapability.ASSESS_IMPACT,
    }

    def __init__(
        self,
        repository: SourceRepository,
        *,
        workers: list[WorkerProtocol] | None = None,
    ) -> None:
        self._repo = repository
        self._workers = workers or [
            AlertReader(repository),
            WeatherMapper(repository),
            EventWindowChecker(repository),
            ImpactAssessor(),
        ]

    def can_handle(self, ctx: RunContext) -> bool:
        return True

    def run(self, ctx: RunContext, blackboard: Blackboard) -> Finding | Refusal:
        ref_now = ctx.now or datetime.now(timezone.utc)

        # 1. Delegate
        for worker in self._workers:
            if worker.can_handle(ctx):
                outcome = worker.run(ctx, blackboard)
                blackboard.put(outcome)

        # 2. Check for refusals
        weather_outcome = blackboard.get("weather_mapper")
        if not weather_outcome or not weather_outcome.contributed:
            return Refusal(
                agent=AgentName.CONTEXT,
                reason_code="missing_alert_level",
                missing_input=["weather_snapshots.alert_level"],
                detail=weather_outcome.reason if weather_outcome else "Meteo assente",
            )

        event_outcome = blackboard.get("event_window_checker")
        if event_outcome and not event_outcome.contributed:
            return Refusal(
                agent=AgentName.CONTEXT,
                reason_code="missing_time_window",
                missing_input=["events.window_start", "events.window_end"],
                detail=event_outcome.reason or "Finestra evento mancante",
            )

        alert_outcome = blackboard.get("alert_reader")
        if (
            alert_outcome
            and not alert_outcome.contributed
            and alert_outcome.reason == "unsourced_alert"
        ):
            return Refusal(
                agent=AgentName.CONTEXT,
                reason_code="unsourced_alert",
                missing_input=["service_alerts.source_id"],
                detail="Alert privo di fonte verificabile",
            )

        # 3. Composition
        heavy_rain = blackboard.value("impact_assessor", "heavy_rain", False)
        alert_lvl = blackboard.value("impact_assessor", "alert_level", "gialla")
        assessed_sev_str = blackboard.value("impact_assessor", "assessed_severity", "high")
        is_sim = weather_outcome.data.get("is_simulated", True)
        data_ref = weather_outcome.data.get("data_reference", "protezione_civile_campania")

        sev_map = {
            "low": Severity.LOW,
            "medium": Severity.MEDIUM,
            "high": Severity.HIGH,
            "critical": Severity.CRITICAL,
        }
        severity = sev_map.get(assessed_sev_str, Severity.HIGH)

        content = {
            "zone_id": ctx.zone_id,
            "heavy_rain": heavy_rain,
            "alert_level": alert_lvl,
            "expected_attendance": 12000,
            "event_window_active": True,
        }

        return Finding(
            agent=AgentName.CONTEXT,
            type=FindingType.IMPACT_ASSESSMENT,
            content=content,
            confidence=0.88,
            severity=severity,
            source_id="protezione_civile_campania",
            data_reference=data_ref,
            is_simulated=is_sim,
            timestamp=ref_now,
        )
