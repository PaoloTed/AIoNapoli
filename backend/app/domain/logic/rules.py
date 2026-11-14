"""Pure deterministic rule evaluation helpers for R1-R4."""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.logic.accessors import (
    congestion,
    density,
    expected_attendance,
    heavy_rain,
    zone_id,
)
from app.domain.models.config import RulesConfig
from app.domain.models.decision import RuleId
from app.domain.models.finding import SEVERITY_ORDER, AgentName, Finding, Severity


@dataclass(frozen=True)
class PureRuleOutcome:
    """Pure result of evaluating a single orchestrator rule."""

    rule_id: RuleId
    agents: tuple[AgentName, ...]
    fired: bool
    reason: str
    zone_id: str | None = None
    missing_fields: tuple[str, ...] = ()


def index_findings_by_agent(findings: list[Finding]) -> dict[AgentName, Finding]:
    """Index findings deterministically by agent in AgentName order."""
    by_agent: dict[AgentName, Finding] = {}
    for finding in findings:
        by_agent[finding.agent] = finding
    return {agent: by_agent[agent] for agent in AgentName if agent in by_agent}


def evaluate_r1_pure(by_agent: dict[AgentName, Finding], config: RulesConfig) -> PureRuleOutcome:
    """R1: mobility.severity >= severity_min and crowding.density > density_threshold_0_1."""
    mob = by_agent.get(AgentName.MOBILITY)
    crd = by_agent.get(AgentName.CROWDING)
    missing: list[str] = []
    if mob is None:
        missing.append("finding mobility")
    if crd is None:
        missing.append("finding crowding")

    crd_density = density(crd) if crd is not None else None
    if crd is not None and crd_density is None:
        missing.append("campo density")

    if missing:
        return PureRuleOutcome(
            rule_id=RuleId.R1_LINE2_CROWDING,
            agents=(AgentName.MOBILITY, AgentName.CROWDING),
            fired=False,
            reason=f"regola non scattata: {', '.join(missing)} assente",
            missing_fields=tuple(missing),
        )

    assert mob is not None and crd is not None and crd_density is not None
    sev_ok = SEVERITY_ORDER[mob.severity] >= SEVERITY_ORDER[config.r1.severity_min]
    dens_ok = crd_density > config.r1.density_threshold_0_1
    fired = sev_ok and dens_ok
    if fired:
        reason = (
            f"mobility.severity={mob.severity.value} e density={crd_density:.2f} "
            f"oltre soglia {config.r1.density_threshold_0_1:.2f}"
        )
    else:
        reason = (
            f"regola non scattata: severity={mob.severity.value} "
            f"(min {config.r1.severity_min.value}), density={crd_density:.2f} "
            f"(soglia > {config.r1.density_threshold_0_1:.2f})"
        )
    return PureRuleOutcome(
        rule_id=RuleId.R1_LINE2_CROWDING,
        agents=(AgentName.MOBILITY, AgentName.CROWDING),
        fired=fired,
        reason=reason,
        zone_id=zone_id(crd) or zone_id(mob),
    )


def evaluate_r2_pure(by_agent: dict[AgentName, Finding], config: RulesConfig) -> PureRuleOutcome:
    """R2: mobility and crowding target the same zone_id and zone density exceeds threshold."""
    mob = by_agent.get(AgentName.MOBILITY)
    crd = by_agent.get(AgentName.CROWDING)
    missing: list[str] = []
    if mob is None:
        missing.append("finding mobility")
    if crd is None:
        missing.append("finding crowding")

    mob_zone = zone_id(mob) if mob is not None else None
    crd_zone = zone_id(crd) if crd is not None else None
    crd_density = density(crd) if crd is not None else None

    if mob is not None and mob_zone is None:
        missing.append("campo mobility.zone_id")
    if crd is not None and crd_zone is None:
        missing.append("campo crowding.zone_id")
    if crd is not None and crd_density is None:
        missing.append("campo density")

    if missing:
        return PureRuleOutcome(
            rule_id=RuleId.R2_CONFLICT_ROUTE_VS_DENSITY,
            agents=(AgentName.MOBILITY, AgentName.CROWDING),
            fired=False,
            reason=f"regola non scattata: {', '.join(missing)} assente",
            missing_fields=tuple(missing),
        )

    assert mob_zone is not None and crd_zone is not None and crd_density is not None
    same_zone = mob_zone == crd_zone
    saturated = crd_density > config.r2.density_threshold_0_1
    fired = same_zone and saturated
    if fired:
        reason = (
            f"percorso e zona satura coincidono su {mob_zone} "
            f"(density={crd_density:.2f} > {config.r2.density_threshold_0_1:.2f})"
        )
    elif not same_zone:
        reason = f"regola non scattata: zone distinte (mobility={mob_zone}, crowding={crd_zone})"
    else:
        reason = (
            f"regola non scattata: zona {mob_zone} non satura "
            f"(density={crd_density:.2f} <= {config.r2.density_threshold_0_1:.2f})"
        )
    return PureRuleOutcome(
        rule_id=RuleId.R2_CONFLICT_ROUTE_VS_DENSITY,
        agents=(AgentName.MOBILITY, AgentName.CROWDING),
        fired=fired,
        reason=reason,
        zone_id=mob_zone if same_zone else None,
    )


def evaluate_r3_pure(by_agent: dict[AgentName, Finding], config: RulesConfig) -> PureRuleOutcome:
    """R3: context.heavy_rain and crowding.density > density_threshold_0_1."""
    ctx = by_agent.get(AgentName.CONTEXT)
    crd = by_agent.get(AgentName.CROWDING)
    missing: list[str] = []
    if ctx is None:
        missing.append("finding context")
    if crd is None:
        missing.append("finding crowding")

    rain = heavy_rain(ctx) if ctx is not None else None
    crd_density = density(crd) if crd is not None else None
    if ctx is not None and rain is None:
        missing.append("campo heavy_rain")
    if crd is not None and crd_density is None:
        missing.append("campo density")

    if missing:
        return PureRuleOutcome(
            rule_id=RuleId.R3_WEATHER_CAPACITY,
            agents=(AgentName.CONTEXT, AgentName.CROWDING),
            fired=False,
            reason=f"regola non scattata: {', '.join(missing)} assente",
            missing_fields=tuple(missing),
        )

    assert rain is not None and crd_density is not None
    rain_ok = (not config.r3.requires_heavy_rain) or rain
    dens_ok = crd_density > config.r3.density_threshold_0_1
    fired = rain_ok and dens_ok
    if fired:
        reason = (
            f"pioggia intensa attiva e density={crd_density:.2f} "
            f"oltre soglia {config.r3.density_threshold_0_1:.2f}, capacita' ridotta"
        )
    else:
        reason = (
            f"regola non scattata: heavy_rain={rain}, density={crd_density:.2f} "
            f"(soglia > {config.r3.density_threshold_0_1:.2f})"
        )
    return PureRuleOutcome(
        rule_id=RuleId.R3_WEATHER_CAPACITY,
        agents=(AgentName.CONTEXT, AgentName.CROWDING),
        fired=fired,
        reason=reason,
        zone_id=zone_id(crd) or (zone_id(ctx) if ctx is not None else None),
    )


def evaluate_r4_pure(by_agent: dict[AgentName, Finding], config: RulesConfig) -> PureRuleOutcome:
    """R4: context.expected_attendance > attendance_threshold and mobility indicates saturation."""
    ctx = by_agent.get(AgentName.CONTEXT)
    mob = by_agent.get(AgentName.MOBILITY)
    missing: list[str] = []
    if ctx is None:
        missing.append("finding context")
    if mob is None:
        missing.append("finding mobility")

    attendance = expected_attendance(ctx) if ctx is not None else None
    mob_cong = congestion(mob) if mob is not None else None
    if ctx is not None and attendance is None:
        missing.append("campo expected_attendance")
    if mob is not None and mob_cong is None:
        missing.append("campo congestion")

    if missing:
        return PureRuleOutcome(
            rule_id=RuleId.R4_EVENT_SURGE,
            agents=(AgentName.CONTEXT, AgentName.MOBILITY),
            fired=False,
            reason=f"regola non scattata: {', '.join(missing)} assente",
            missing_fields=tuple(missing),
        )

    assert attendance is not None and mob_cong is not None and mob is not None
    att_ok = attendance > config.r4.attendance_threshold
    mob_saturated = (
        mob_cong >= config.r4.congestion_threshold_0_1
        or SEVERITY_ORDER[mob.severity] >= SEVERITY_ORDER[Severity.HIGH]
    )
    fired = att_ok and mob_saturated
    if fired:
        reason = (
            f"affluenza attesa {attendance} > {config.r4.attendance_threshold} "
            f"con congestion={mob_cong:.2f}, valutate alternative"
        )
    else:
        reason = (
            f"regola non scattata: affluenza={attendance} "
            f"(soglia > {config.r4.attendance_threshold}), congestion={mob_cong:.2f}"
        )
    return PureRuleOutcome(
        rule_id=RuleId.R4_EVENT_SURGE,
        agents=(AgentName.CONTEXT, AgentName.MOBILITY),
        fired=fired,
        reason=reason,
        zone_id=zone_id(mob) or (zone_id(ctx) if ctx is not None else None),
    )
