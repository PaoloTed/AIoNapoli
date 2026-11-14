"""Specialized Crowding Agent producing Finding or structured Refusal."""

from __future__ import annotations

from datetime import datetime, timezone

from app.domain.logic.units import occupancy_to_density
from app.domain.models.finding import AgentName, Finding, FindingType, Severity
from app.domain.models.refusal import Refusal
from app.repositories.base import SourceRepository


class CrowdingAgent:
    """Interprets occupancy estimates and geo-fenced events into density_alert findings."""

    def __init__(self, repository: SourceRepository) -> None:
        self._repo = repository

    def evaluate(
        self,
        *,
        zone_id: str | None = None,
        line: str | None = None,
        allow_simulation: bool = True,
        require_event_geofence: bool = True,
        now: datetime | None = None,
    ) -> Finding | Refusal:
        ref_now = now or datetime.now(timezone.utc)

        occupancy_rows = self._repo.get_latest_occupancy(line=line)
        if not occupancy_rows:
            return Refusal(
                agent=AgentName.CROWDING,
                reason_code="missing_occupancy",
                missing_input=["occupancy_estimates"],
                detail="Nessuna stima di occupazione disponibile e nessuna simulazione attiva",
            )
        if not allow_simulation and all(bool(r.get("is_simulated")) for r in occupancy_rows):
            return Refusal(
                agent=AgentName.CROWDING,
                reason_code="missing_occupancy",
                missing_input=["occupancy_estimates_realtime"],
                detail="Occupancy presente solo in simulazione con allow_simulation=false",
            )

        events = self._repo.get_events(zone_id=zone_id)
        if require_event_geofence and events:
            for ev in events:
                geofence = ev.get("geofence")
                if not isinstance(geofence, str) or not geofence.strip():
                    return Refusal(
                        agent=AgentName.CROWDING,
                        reason_code="missing_geofence",
                        missing_input=["events.geofence"],
                        detail=f"Evento '{ev.get('event_id', 'sconosciuto')}' privo di geo-fence",
                    )

        # Compute normalized density from max occupancy_pct using single source of truth
        max_occ = max(float(r["occupancy_pct"]) for r in occupancy_rows)
        if max_occ < 0.0 or max_occ > 100.0:
            return Refusal(
                agent=AgentName.CROWDING,
                reason_code="invalid_density",
                missing_input=["occupancy_pct"],
                detail=f"Valore occupancy_pct fuori range [0..100]: {max_occ}",
            )
        dens = occupancy_to_density(max_occ)
        if dens < 0.0 or dens > 1.0:
            return Refusal(
                agent=AgentName.CROWDING,
                reason_code="invalid_density",
                missing_input=["density"],
                detail=f"Densita' calcolata fuori range [0..1]: {dens}",
            )

        if dens >= 0.90:
            severity = Severity.CRITICAL if dens >= 0.95 else Severity.HIGH
        elif dens >= 0.70:
            severity = Severity.MEDIUM
        else:
            severity = Severity.LOW

        primary_occ = occupancy_rows[0]
        resolved_zone = zone_id or (str(events[0]["zone_id"]) if events else None) or "Z_BAGNOLI"
        content: dict[str, object] = {
            "density": round(dens, 2),
            "zone_id": resolved_zone,
            "line_id": str(primary_occ["line"]),
        }
        if events:
            content["expected_attendance"] = int(events[0]["expected_attendance"])

        return Finding(
            agent=AgentName.CROWDING,
            type=FindingType.DENSITY_ALERT,
            content=content,
            confidence=0.82,
            severity=severity,
            source_id=str(primary_occ["source_id"]),
            data_reference=str(primary_occ["data_reference"]),
            is_simulated=any(bool(r.get("is_simulated")) for r in occupancy_rows),
            timestamp=ref_now,
        )
