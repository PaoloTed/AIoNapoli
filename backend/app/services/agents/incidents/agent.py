"""Incidents agent (Agente Imprevisti): validates route proposals against known obstacles.

Specified in implementations/01_agenti_negoziazione/04_agente_imprevisti.md.
Produces applicable TravelConstraint objects without modifying frozen external contracts.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.domain.models.routing import (
    LineTarget,
    RouteProposal,
    StopTarget,
    TimeWindow,
    TravelConstraint,
    ZoneTarget,
)
from app.repositories.base import SourceRepository
from app.utils.clock import Clock, SystemClock


class IncidentsAgent:
    """Validates proposals against service alerts, strikes, disruptions, and events."""

    def __init__(
        self,
        repository: SourceRepository,
        *,
        clock: Clock | None = None,
        event_surge_threshold: int = 10000,
        stale_alert_days: int = 7,
    ) -> None:
        self._repo = repository
        self._clock = clock or SystemClock()
        self._surge_threshold = event_surge_threshold
        self._stale_days = stale_alert_days

    def _now(self) -> datetime:
        now = self._clock.now()
        if now.tzinfo is None:
            return now.replace(tzinfo=timezone.utc)
        return now.astimezone(timezone.utc)

    def get_known_constraints(self, now: datetime | None = None) -> list[TravelConstraint]:
        """Pre-load known active constraints (D-23, 03_ciclo_negoziazione.md §7)."""
        ref_now = now or self._now()
        constraints: list[TravelConstraint] = []

        try:
            alerts = self._repo.get_active_service_alerts(ref_now)
            for alert in alerts:
                c = self._alert_to_constraint(alert, ref_now)
                if c is not None and c.kind == "closure":
                    constraints.append(c)
        except Exception:
            pass

        return self._sort_and_limit(constraints)

    def validate(
        self,
        proposal: RouteProposal,
        ctx: Any = None,
    ) -> list[TravelConstraint]:
        """Validate a route proposal against all operational disruption sources."""
        now = self._now()
        constraints: list[TravelConstraint] = []
        try:
            alerts = self._repo.get_active_service_alerts(now)
            events = self._repo.get_events()
        except Exception:
            # Safe degradation: repository failure produces uncertainty, never unhandled error
            return [
                TravelConstraint(
                    kind="uncertainty",
                    target=ZoneTarget(zone_id=proposal.destination.label),
                    evidence_ref="repo_error",
                    source_id="incidents",
                    confidence=0.10,
                )
            ]

        # Check if tables are completely empty
        if not alerts and not events:
            return [
                TravelConstraint(
                    kind="uncertainty",
                    target=ZoneTarget(zone_id=proposal.destination.label),
                    evidence_ref="no_data_available",
                    source_id="incidents",
                    confidence=0.30,
                )
            ]

        # Extract proposal features for matching
        proposal_route_ids = set(proposal.route_ids)
        proposal_zone_ids = set(proposal.zone_ids)
        proposal_stops: set[str] = set()
        proposal_modes: set[str] = set()
        for leg in proposal.legs:
            proposal_modes.add(leg.mode.lower())
            if leg.from_stop_id:
                proposal_stops.add(leg.from_stop_id)
            if leg.to_stop_id:
                proposal_stops.add(leg.to_stop_id)
            if leg.from_stop:
                proposal_stops.add(leg.from_stop)
            if leg.to_stop:
                proposal_stops.add(leg.to_stop)

        # 1. Correlate Alerts
        for alert in alerts:
            c = self._alert_to_constraint(alert, now)
            if c is None:
                continue

            hit = False
            # Strike mode compatibility: a bus strike doesn't hit metro/rail
            route_type = str(alert.get("route_type") or "").lower()
            if route_type:
                if route_type in ("bus", "autobus") and not any(
                    m in ("bus",) for m in proposal_modes
                ):
                    continue
                if route_type in ("metro", "metropolitana") and not any(
                    m in ("metro", "rail") for m in proposal_modes
                ):
                    continue

            if isinstance(c.target, StopTarget) and c.target.stop_id in proposal_stops:
                hit = True
            elif isinstance(c.target, LineTarget) and c.target.route_id in proposal_route_ids:
                hit = True
            elif isinstance(c.target, ZoneTarget) and c.target.zone_id in proposal_zone_ids:
                hit = True

            if hit:
                constraints.append(c)

        # 2. Correlate Events
        for ev in events:
            ev_zone = ev.get("zone_id")
            if not ev_zone or ev_zone not in proposal_zone_ids:
                continue

            # Check time window
            ev_start = self._parse_dt(ev.get("start_time"))
            ev_end = self._parse_dt(ev.get("end_time"))
            ev_window = TimeWindow(from_at=ev_start, to_at=ev_end)

            # Check if event overlaps with proposal travel window
            prop_start = proposal.legs[0].departure if proposal.legs else now
            prop_end = proposal.legs[-1].arrival if proposal.legs else now

            if ev_start is not None and ev_end is not None:
                if not ev_window.overlaps(prop_start, prop_end):
                    continue

            attendance = int(ev.get("expected_attendance") or ev.get("attendance") or 0)
            if attendance >= self._surge_threshold:
                # Heavy event produces penalty (never closure! 04_agente_imprevisti.md §5.1)
                constraints.append(
                    TravelConstraint(
                        kind="penalty",
                        target=ZoneTarget(zone_id=ev_zone),
                        window=ev_window,
                        evidence_ref=str(ev.get("event_id") or f"event_{ev_zone}"),
                        source_id="events",
                        confidence=0.75,
                    )
                )
            elif attendance > 0:
                constraints.append(
                    TravelConstraint(
                        kind="penalty",
                        target=ZoneTarget(zone_id=ev_zone),
                        window=ev_window,
                        evidence_ref=str(ev.get("event_id") or f"event_{ev_zone}"),
                        source_id="events",
                        confidence=0.60,
                    )
                )

        return self._sort_and_limit(constraints)

    def _alert_to_constraint(self, alert: dict[str, Any], now: datetime) -> TravelConstraint | None:
        alert_id = str(alert.get("alert_id") or "alert_unknown")
        source_id = str(alert.get("source_id") or "anm")
        raw_conf = alert.get("confidence")
        confidence = float(raw_conf) if raw_conf is not None else 0.85

        # Check freshness / stale source
        valid_from = self._parse_dt(alert.get("valid_from"))
        if valid_from is not None:
            age_days = (now - valid_from).total_seconds() / 86400.0
            if age_days > self._stale_days:
                return TravelConstraint(
                    kind="uncertainty",
                    target=LineTarget(route_id=str(alert.get("route_id") or "unknown")),
                    evidence_ref=alert_id,
                    source_id=source_id,
                    confidence=0.30,
                )

        valid_to = self._parse_dt(alert.get("valid_to"))
        window = TimeWindow(from_at=valid_from, to_at=valid_to)

        # Stop target
        stop_id = alert.get("stop_id")
        if stop_id:
            return TravelConstraint(
                kind="closure",
                target=StopTarget(stop_id=str(stop_id)),
                window=window,
                evidence_ref=alert_id,
                source_id=source_id,
                confidence=min(1.0, max(confidence, 0.95)),
            )

        # Route target
        route_id = alert.get("route_id")
        if route_id:
            return TravelConstraint(
                kind="closure",
                target=LineTarget(route_id=str(route_id)),
                window=window,
                evidence_ref=alert_id,
                source_id=source_id,
                confidence=min(1.0, max(confidence, 0.90)),
            )

        # Zone target
        zone_id = alert.get("zone_id")
        if zone_id:
            return TravelConstraint(
                kind="closure",
                target=ZoneTarget(zone_id=str(zone_id)),
                window=window,
                evidence_ref=alert_id,
                source_id=source_id,
                confidence=min(1.0, max(confidence, 0.80)),
            )

        return None

    def _parse_dt(self, val: Any) -> datetime | None:
        if isinstance(val, datetime):
            return val if val.tzinfo is not None else val.replace(tzinfo=timezone.utc)
        if isinstance(val, str) and val:
            try:
                dt = datetime.fromisoformat(val)
                return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)
            except ValueError:
                return None
        return None

    def _sort_and_limit(self, constraints: list[TravelConstraint]) -> list[TravelConstraint]:
        # Deterministic sorting: by confidence desc, then evidence_ref asc
        constraints.sort(key=lambda c: (-c.confidence, c.evidence_ref))
        return constraints[:10]
