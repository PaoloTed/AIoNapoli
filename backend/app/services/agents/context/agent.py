"""Specialized Context Agent producing Finding or structured Refusal."""

from __future__ import annotations

from datetime import datetime, timezone

from app.domain.models.finding import AgentName, Finding, FindingType, Severity
from app.domain.models.refusal import Refusal
from app.repositories.base import SourceRepository


class ContextAgent:
    """Interprets weather snapshots, events, and service alerts into impact_assessment."""

    def __init__(self, repository: SourceRepository) -> None:
        self._repo = repository

    def evaluate(
        self,
        *,
        zone_id: str | None = None,
        now: datetime | None = None,
    ) -> Finding | Refusal:
        ref_now = now or datetime.now(timezone.utc)

        weather_rows = self._repo.get_latest_weather(zone_id=zone_id)
        if not weather_rows:
            return Refusal(
                agent=AgentName.CONTEXT,
                reason_code="missing_alert_level",
                missing_input=["weather_snapshots.alert_level"],
                detail="Snapshot meteo assente per valutare il livello di allerta",
            )
        weather = weather_rows[0]
        alert_level = weather.get("alert_level")
        if not isinstance(alert_level, str) or not alert_level.strip():
            return Refusal(
                agent=AgentName.CONTEXT,
                reason_code="missing_alert_level",
                missing_input=["weather_snapshots.alert_level"],
                detail="Snapshot meteo privo di livello di allerta (alert_level)",
            )

        events = self._repo.get_events(zone_id=zone_id)
        for ev in events:
            if not ev.get("window_start") or not ev.get("window_end"):
                return Refusal(
                    agent=AgentName.CONTEXT,
                    reason_code="missing_time_window",
                    missing_input=["events.window_start", "events.window_end"],
                    detail=f"Evento '{ev.get('event_id', 'sconosciuto')}' senza finestra temporale",
                )

        alerts = self._repo.get_active_service_alerts(now=ref_now)
        for al in alerts:
            src = al.get("source_id")
            if not isinstance(src, str) or not src.strip():
                return Refusal(
                    agent=AgentName.CONTEXT,
                    reason_code="unsourced_alert",
                    missing_input=["service_alerts.source_id"],
                    detail=f"Alert '{al.get('alert_id', 'sconosciuto')}' senza fonte citata",
                )

        heavy_rain_flag = bool(weather.get("heavy_rain")) or alert_level in ("arancione", "rossa")
        expected_att = int(events[0]["expected_attendance"]) if events else 0
        if alert_level == "rossa" or (heavy_rain_flag and expected_att >= 10000):
            severity = Severity.HIGH if alert_level == "rossa" else Severity.MEDIUM
        elif heavy_rain_flag or expected_att >= 5000:
            severity = Severity.MEDIUM
        else:
            severity = Severity.LOW

        resolved_zone = (
            zone_id
            or weather.get("zone_id")
            or (events[0].get("zone_id") if events else None)
            or "Z_BAGNOLI"
        )

        content: dict[str, object] = {
            "heavy_rain": heavy_rain_flag,
            "alert_level": alert_level,
            "zone_id": resolved_zone,
        }
        if events:
            content["expected_attendance"] = expected_att

        return Finding(
            agent=AgentName.CONTEXT,
            type=FindingType.IMPACT_ASSESSMENT,
            content=content,
            confidence=0.75,
            severity=severity,
            source_id=str(weather["source_id"]),
            data_reference=str(weather["data_reference"]),
            is_simulated=bool(weather.get("is_simulated", True))
            or any(bool(e.get("is_simulated", True)) for e in events),
            timestamp=ref_now,
        )

