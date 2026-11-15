"""Specialized workers for Context domain (02_architettura_agentica.md §6.3)."""

from __future__ import annotations

from app.repositories.base import SourceRepository
from app.services.agents.base import AgentCapability, AgentOutcome, RunContext
from app.services.agents.blackboard import Blackboard


class AlertReader:
    name = "alert_reader"
    capabilities = {AgentCapability.READ_ALERTS}

    def __init__(self, repository: SourceRepository) -> None:
        self._repo = repository

    def can_handle(self, ctx: RunContext) -> bool:
        return True

    def run(self, ctx: RunContext, blackboard: Blackboard) -> AgentOutcome:
        alerts = self._repo.get_active_service_alerts(now=ctx.now)
        # Check that alerts have source_id
        for al in alerts:
            src = al.get("source_id")
            if not isinstance(src, str) or not src.strip():
                return AgentOutcome(
                    agent=self.name,
                    contributed=False,
                    reason="unsourced_alert",
                    confidence=0.0,
                )
        return AgentOutcome(
            agent=self.name,
            contributed=True,
            data={"active_alerts": alerts, "alerts_count": len(alerts)},
            confidence=0.85,
        )


class WeatherMapper:
    name = "weather_mapper"
    capabilities = {AgentCapability.MAP_WEATHER}

    def __init__(self, repository: SourceRepository) -> None:
        self._repo = repository

    def can_handle(self, ctx: RunContext) -> bool:
        return True

    def run(self, ctx: RunContext, blackboard: Blackboard) -> AgentOutcome:
        weather_rows = self._repo.get_latest_weather(zone_id=ctx.zone_id)
        if not weather_rows:
            return AgentOutcome(
                agent=self.name,
                contributed=False,
                reason="Snapshot meteo assente",
                confidence=0.0,
            )
        w = weather_rows[0]
        alert_level = w.get("alert_level")
        if not isinstance(alert_level, str) or not alert_level.strip():
            return AgentOutcome(
                agent=self.name,
                contributed=False,
                reason="alert_level assente",
                confidence=0.0,
            )
        rain_mm = float(w.get("precipitation_mm", 0.0))
        heavy_rain = alert_level in ("arancione", "rossa") or rain_mm >= 25.0
        return AgentOutcome(
            agent=self.name,
            contributed=True,
            data={
                "alert_level": alert_level,
                "precipitation_mm": rain_mm,
                "heavy_rain": heavy_rain,
                "is_simulated": bool(w.get("is_simulated")),
                "data_reference": str(w.get("data_reference", "weather_source")),
            },
            confidence=0.90,
        )


class EventWindowChecker:
    name = "event_window_checker"
    capabilities = {AgentCapability.CHECK_EVENT_WINDOW}

    def __init__(self, repository: SourceRepository) -> None:
        self._repo = repository

    def can_handle(self, ctx: RunContext) -> bool:
        return True

    def run(self, ctx: RunContext, blackboard: Blackboard) -> AgentOutcome:
        events = self._repo.get_events(zone_id=ctx.zone_id)
        valid_events = []
        for ev in events:
            if not ev.get("window_start") or not ev.get("window_end"):
                return AgentOutcome(
                    agent=self.name,
                    contributed=False,
                    reason="missing_time_window",
                    confidence=0.0,
                )
            valid_events.append(ev)
        return AgentOutcome(
            agent=self.name,
            contributed=True,
            data={"events": valid_events, "events_count": len(valid_events)},
            confidence=0.88,
        )


class ImpactAssessor:
    name = "impact_assessor"
    capabilities = {AgentCapability.ASSESS_IMPACT}

    def can_handle(self, ctx: RunContext) -> bool:
        return True

    def run(self, ctx: RunContext, blackboard: Blackboard) -> AgentOutcome:
        heavy_rain = blackboard.value("weather_mapper", "heavy_rain", False)
        alert_level = blackboard.value("weather_mapper", "alert_level", "verde")
        events_count = blackboard.value("event_window_checker", "events_count", 0)

        if heavy_rain and events_count > 0:
            impact_desc = (
                "Pioggia intensa combinata con evento ad alta affluenza: criticita elevata"
            )
            severity = "critical"
        elif heavy_rain:
            impact_desc = (
                "Allerta meteo e pioggia battente: rallentamenti attesi sul trasporto di superficie"
            )
            severity = "high"
        elif events_count > 0:
            impact_desc = "Evento programmato in zona con afflusso concentrato"
            severity = "medium"
        else:
            impact_desc = "Condizioni di contesto ordinarie"
            severity = "low"

        return AgentOutcome(
            agent=self.name,
            contributed=True,
            data={
                "impact_description": impact_desc,
                "assessed_severity": severity,
                "heavy_rain": heavy_rain,
                "alert_level": alert_level,
            },
            confidence=0.85,
        )
