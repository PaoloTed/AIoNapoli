"""Pure deterministic feature scoring helpers for RelevanceScore."""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.models.config import RelevanceConfig
from app.domain.models.decision import Decision, PlanItem, PlanTarget
from app.domain.models.finding import SEVERITY_ORDER, AgentName, Finding


@dataclass(frozen=True)
class PureContribution:
    feature: str
    value: float
    weight: float
    contribution: float


@dataclass(frozen=True)
class PureScoredItem:
    plan_index: int
    score: float
    contributions: tuple[PureContribution, ...]


def extract_item_features(
    item: PlanItem,
    decision: Decision,
    findings: list[Finding],
    max_priority_in_plan: int,
) -> dict[str, float]:
    """Derive normalized feature values in [0, 1] deterministically from item and decision."""
    max_sev = max((SEVERITY_ORDER[f.severity] for f in findings), default=1) / 4.0
    if decision.conflict.detected and "P1" in item.rationale:
        severity_score = max(max_sev, 1.0)
    elif "P1" in item.rationale:
        severity_score = max(max_sev, 0.9)
    elif "P2" in item.rationale:
        severity_score = max(max_sev * 0.85, 0.7)
    else:
        severity_score = max(max_sev * 0.65, 0.45)

    text = f"{item.action} {item.rationale}".lower()
    affects_public_service = (
        1.0
        if (
            item.target in (PlanTarget.OPERATOR, PlanTarget.CITIZEN)
            or any(
                k in text
                for k in ("servizio pubblico", "bus", "cumana", "linea", "anagrafe", "superficie")
            )
        )
        else 0.0
    )
    affects_route = (
        1.0
        if any(
            k in text
            for k in (
                "percorso",
                "linea",
                "bus",
                "cumana",
                "alternativa",
                "deviazione",
                "raggiungi",
            )
        )
        else 0.0
    )

    # Priority rank normalized in [0, 1]: rank 1 -> 1.0, higher rank -> smaller.
    denom = max(max_priority_in_plan, 1)
    priority_rank = max(0.1, min(1.0, 1.0 - (item.priority - 1) / max(denom, 2)))

    # Time to event relevance: highest when context/event or tourist alternative is active
    has_context = any(f.agent == AgentName.CONTEXT for f in findings)
    if item.target == PlanTarget.TOURIST:
        time_to_event = 1.0 if has_context else 0.7
    elif item.target == PlanTarget.CITIZEN:
        time_to_event = 0.75 if has_context else 0.5
    else:
        time_to_event = 0.5 if has_context else 0.3

    return {
        "severity_score": round(min(1.0, max(0.0, severity_score)), 4),
        "confidence": round(min(1.0, max(0.0, decision.confidence)), 4),
        "affects_public_service": affects_public_service,
        "priority_rank": round(min(1.0, max(0.0, priority_rank)), 4),
        "affects_route": affects_route,
        "time_to_event": time_to_event,
    }


def score_item_for_target(
    plan_index: int,
    item: PlanItem,
    target: PlanTarget,
    decision: Decision,
    findings: list[Finding],
    config: RelevanceConfig,
) -> PureScoredItem:
    """Compute weighted feature contributions and total rounded score for one item & target."""
    max_prio = max((p.priority for p in decision.plan), default=1)
    features = extract_item_features(item, decision, findings, max_prio)
    weights = config.weights[target]
    rounding = config.rounding

    # Target alignment boost encoded only via the configured feature weights + target affinity
    # Note: every contribution is strictly round(value * weight, rounding) and score is exact sum!
    contributions: list[PureContribution] = []
    for feat_name in sorted(weights.keys()):
        weight = float(weights[feat_name])
        raw_val = features.get(feat_name, 0.0)
        # Differentiate items targeting this recipient across plan items
        if feat_name == "affects_public_service" and item.target == PlanTarget.CITIZEN:
            raw_val = 1.0
        elif feat_name == "affects_public_service" and item.target == PlanTarget.OPERATOR:
            raw_val = 0.6
        elif feat_name == "affects_public_service" and item.target == PlanTarget.TOURIST:
            raw_val = 0.2
        elif feat_name == "time_to_event" and item.target == PlanTarget.TOURIST:
            raw_val = 1.0
        elif feat_name == "affects_route" and item.target == PlanTarget.OPERATOR:
            raw_val = 0.6

        contrib = round(raw_val * weight, rounding)
        contributions.append(
            PureContribution(
                feature=feat_name,
                value=round(raw_val, rounding),
                weight=round(weight, rounding),
                contribution=contrib,
            )
        )

    total = round(sum(c.contribution for c in contributions), rounding)
    if total > 1.0 and contributions:
        excess = round(total - 1.0, rounding)
        max_idx = max(range(len(contributions)), key=lambda i: contributions[i].contribution)
        c_max = contributions[max_idx]
        contributions[max_idx] = PureContribution(
            feature=c_max.feature,
            value=c_max.value,
            weight=c_max.weight,
            contribution=round(max(0.0, c_max.contribution - excess), rounding),
        )
        total = round(sum(c.contribution for c in contributions), rounding)
    total = min(1.0, max(0.0, total))
    return PureScoredItem(
        plan_index=plan_index,
        score=total,
        contributions=tuple(contributions),
    )
