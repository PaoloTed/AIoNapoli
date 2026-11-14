"""Deterministic derivation of severity and confidence for RSS alerts (D-14)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

_SEVERITY_RANK: dict[str, int] = {
    "low": 1,
    "medium": 2,
    "high": 3,
    "critical": 4,
}


@dataclass(frozen=True)
class DerivationResult:
    severity: str
    confidence: float
    matched_keyword: str | None


def load_derivation_rules(path: str | Path | None = None) -> dict[str, Any]:
    target = Path(path) if path is not None else Path(__file__).resolve().parent / "derivation.yaml"
    data = yaml.safe_load(target.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("derivation.yaml deve contenere una mappa YAML")
    return data


def _cap_severity(severity: str, max_severity: str) -> str:
    if _SEVERITY_RANK[severity] > _SEVERITY_RANK[max_severity]:
        return max_severity
    return severity


def derive_severity_and_confidence(
    source_id: str,
    title: str,
    description: str = "",
    rules: dict[str, Any] | None = None,
) -> DerivationResult:
    """Derive severity and confidence deterministically from derivation.yaml."""
    cfg = rules if rules is not None else load_derivation_rules()
    sources = cfg.get("sources", {})
    source_cfg = sources.get(
        source_id,
        {
            "category": "unknown",
            "confidence": 0.50,
            "default_severity": "medium",
            "max_severity": "high",
        },
    )
    confidence = float(source_cfg["confidence"])
    default_sev = str(source_cfg.get("default_severity", "medium"))
    max_sev = str(source_cfg.get("max_severity", "critical"))
    if source_cfg.get("category") == "aggregator" and max_sev == "critical":
        max_sev = "high"

    text = f"{title} {description}".lower()
    keyword_map = cfg.get("keyword_severity", {})

    for sev_level in ("critical", "high", "medium", "low"):
        keywords = keyword_map.get(sev_level, [])
        for kw in keywords:
            if str(kw).lower() in text:
                capped = _cap_severity(sev_level, max_sev)
                return DerivationResult(
                    severity=capped,
                    confidence=confidence,
                    matched_keyword=str(kw),
                )

    return DerivationResult(
        severity=_cap_severity(default_sev, max_sev),
        confidence=confidence,
        matched_keyword=None,
    )

