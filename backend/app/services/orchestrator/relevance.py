"""Relevance scoring per target with full feature contribution decomposition."""

from __future__ import annotations

from shared.schemas.api import Contribution, RelevanceScore, ScoredItem, TargetRelevance

from app.domain.logic.scoring import score_item_for_target
from app.domain.models.config import RelevanceConfig
from app.domain.models.decision import Decision, PlanTarget
from app.domain.models.finding import Finding


def score_relevance(
    decision: Decision,
    findings: list[Finding],
    config: RelevanceConfig,
) -> RelevanceScore:
    """Compute per-target RelevanceScore and deterministic item rankings."""
    targets_map: dict[PlanTarget, TargetRelevance] = {}
    for target in PlanTarget:
        scored_items: list[ScoredItem] = []
        for idx, item in enumerate(decision.plan):
            pure_scored = score_item_for_target(
                plan_index=idx,
                item=item,
                target=target,
                decision=decision,
                findings=findings,
                config=config,
            )
            scored_items.append(
                ScoredItem(
                    plan_index=pure_scored.plan_index,
                    score=pure_scored.score,
                    contributions=[
                        Contribution(
                            feature=c.feature,
                            value=c.value,
                            weight=c.weight,
                            contribution=c.contribution,
                        )
                        for c in pure_scored.contributions
                    ],
                )
            )

        # Sort descending by score, breaking ties deterministically by plan_index
        scored_items.sort(key=lambda s: (-s.score, s.plan_index))
        order = [s.plan_index for s in scored_items]
        targets_map[target] = TargetRelevance(order=order, items=scored_items)

    return RelevanceScore(rounding=config.rounding, targets=targets_map)
