"""Optional narrative rendering layer with deterministic template/replay fallback."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from shared.schemas.api import Narrative, NarrativeItem, NarrativeTexts

from app.domain.models.decision import Decision, PlanTarget


def _translate_tourist_en(action: str, conflict_detected: bool) -> str:
    if "MANN" in action or "coperto" in action.lower():
        return (
            "Alternative: take Metro Line 1 / Bus R2 toward indoor landmarks (MANN Museum), "
            "estimated time 20 minutes."
        )
    if conflict_detected or "Fuorigrotta" in action or "R2" in action:
        return "Alternative: Line R2 from Fuorigrotta toward city center, about 20 minutes."
    return "Public transport running regularly: check live departures before traveling."


def _load_cached_replay(cache_dir: str | Path, decision_id: str) -> Narrative | None:
    path = Path(cache_dir) / f"{decision_id}.json"
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        return Narrative.model_validate(raw)
    except (OSError, ValueError):
        return None


def render_narrative(
    decision: Decision,
    *,
    mode: Literal["replay", "live", "off"] = "replay",
    decision_id: str | None = None,
    cache_dir: str | Path = ".cache/llm",
) -> Narrative:
    """Render multilingual/stylistic narrative outside the Decision contract.

    Never alters Decision or decision_id (REQ-DEG-02).
    """
    if mode == "off":
        return Narrative(mode="off", items=[])

    if mode == "replay" and decision_id:
        cached = _load_cached_replay(cache_dir, decision_id)
        if cached is not None:
            return cached

    # Deterministic template fallback used both for replay without cache file
    # and when live LLM is unavailable (REQ-DEG-02, OPERATIONS.md §3.2 llm_unavailable).
    effective_mode: Literal["replay", "live", "off"] = "replay" if mode == "live" else mode
    items: list[NarrativeItem] = []
    for idx, plan_item in enumerate(decision.plan):
        if plan_item.target == PlanTarget.TOURIST:
            texts = NarrativeTexts(
                it=plan_item.action,
                en=_translate_tourist_en(plan_item.action, decision.conflict.detected),
            )
        else:
            texts = NarrativeTexts(it=plan_item.action)
        items.append(NarrativeItem(plan_index=idx, texts=texts))

    return Narrative(mode=effective_mode, items=items)
