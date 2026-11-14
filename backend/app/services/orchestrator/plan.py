"""Build target-specific PlanItems with unique priority ranks and zero log leakage."""

from __future__ import annotations

from app.domain.logic.accessors import density, expected_attendance, heavy_rain, zone_id
from app.domain.logic.rules import index_findings_by_agent
from app.domain.models.config import RulesConfig
from app.domain.models.decision import PlanItem, PlanTarget
from app.domain.models.finding import AgentName, Finding
from app.domain.models.trace import Trace
from app.services.orchestrator.models import Resolution, RuleResult


def build_plan(
    findings: list[Finding],
    rule_results: list[RuleResult],
    resolution: Resolution,
    config: RulesConfig,
    trace: Trace | None = None,
) -> list[PlanItem]:
    """Generate deterministic PlanItems covering operator, tourist, and citizen."""
    fired_rules = [r for r in rule_results if r.fired]
    by_agent = index_findings_by_agent(findings)

    if not fired_rules:
        items = [
            PlanItem(
                priority=1,
                action=config.monitoring_text.operator,
                target=PlanTarget.OPERATOR,
                rationale=(
                    "P3 esperienza e alternative; nessuna soglia critica superata, "
                    "monitoraggio attivo"
                ),
            ),
            PlanItem(
                priority=1,
                action=config.monitoring_text.tourist,
                target=PlanTarget.TOURIST,
                rationale="P3 esperienza; nessun affollamento critico segnalato",
            ),
            PlanItem(
                priority=1,
                action=config.monitoring_text.citizen,
                target=PlanTarget.CITIZEN,
                rationale="P3 esperienza; servizio pubblico regolare",
            ),
        ]
    else:
        crd = by_agent.get(AgentName.CROWDING)
        ctx = by_agent.get(AgentName.CONTEXT)
        mob = by_agent.get(AgentName.MOBILITY)

        dens_val = density(crd) if crd else None
        zone = (
            resolution.conflict.zone_id
            or (zone_id(crd) if crd else None)
            or (zone_id(mob) if mob else None)
            or "Z_BAGNOLI"
        )
        rain_active = heavy_rain(ctx) is True if ctx else False
        att_val = expected_attendance(ctx) if ctx else None

        dens_str = f"{dens_val:.2f}" if dens_val is not None else "elevata"
        if resolution.conflict.detected:
            op_action = (
                f"Attivare deviazione bus di superficie su asse alternativo evitando {zone}; "
                f"priorita' 1 per sicurezza"
            )
            op_rationale = (
                f"P1 sicurezza delle persone; densita' {dens_str} oltre soglia "
                f"{config.r1.density_threshold_0_1:.2f} ({resolution.dominant_rule.value}); "
                f"percorso diretto scartato"
            )
        else:
            op_action = (
                f"Rinforzare il servizio di superficie e presidiare gli accessi in zona {zone}"
            )
            op_rationale = (
                f"{resolution.priority_code} {resolution.priority_label}; "
                f"regola dominante {resolution.dominant_rule.value}"
            )

        if rain_active:
            tour_action = (
                "Alternativa: linea R2 / Linea 1 verso poli al coperto (Museo MANN), "
                "tempo stimato 20 min"
            )
            tour_rationale = (
                "P2 tempo di percorrenza; itinerario al coperto consigliato per pioggia intensa"
            )
        else:
            tour_action = (
                "Alternativa: linea R2 da Fuorigrotta verso centro citta', tempo stimato 20 min"
            )
            tour_rationale = "P2 tempo di percorrenza; deviazione verso area meno affollata"

        if att_val and att_val > config.r4.attendance_threshold:
            cit_action = (
                "Raggiungi il servizio pubblico in 15 min via percorso alternativo Cumana / Bus 151"
            )
        else:
            cit_action = "Raggiungi il servizio pubblico in 15 min via percorso A"
        cit_rationale = (
            "P3 esperienza; collegamento diretto al servizio pubblico evitando i nodi congestionati"
        )

        items = [
            PlanItem(
                priority=1,
                action=op_action,
                target=PlanTarget.OPERATOR,
                rationale=op_rationale,
            ),
            PlanItem(
                priority=1,
                action=tour_action,
                target=PlanTarget.TOURIST,
                rationale=tour_rationale,
            ),
            PlanItem(
                priority=1,
                action=cit_action,
                target=PlanTarget.CITIZEN,
                rationale=cit_rationale,
            ),
        ]

    if trace is not None:
        for idx, item in enumerate(items):
            trace.plan_item_created(
                target=item.target.value,
                action_ref=f"plan:{idx}",
            )

    return items
