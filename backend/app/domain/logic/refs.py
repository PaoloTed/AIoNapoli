"""Canonical JSON serialization and deterministic content-addressed hashes (D-03, D-10)."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel

from app.domain.models.decision import Decision
from app.domain.models.finding import Finding


def _normalize_value(value: Any, *, float_decimals: int = 4, key_name: str | None = None) -> Any:
    if isinstance(value, BaseModel):
        return _normalize_value(
            value.model_dump(mode="python"),
            float_decimals=float_decimals,
        )
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        dt = (
            value.replace(tzinfo=timezone.utc)
            if value.tzinfo is None
            else value.astimezone(timezone.utc)
        )
        return dt.isoformat()
    if isinstance(value, bool):
        return value
    if isinstance(value, float):
        decimals = 2 if key_name == "confidence" else float_decimals
        return round(value, decimals)
    if isinstance(value, dict):
        return {
            str(k): _normalize_value(v, float_decimals=float_decimals, key_name=str(k))
            for k, v in sorted(value.items(), key=lambda item: str(item[0]))
        }
    if isinstance(value, (list, tuple)):
        return [_normalize_value(item, float_decimals=float_decimals) for item in value]
    if isinstance(value, (set, frozenset)):
        normalized_items = [_normalize_value(item, float_decimals=float_decimals) for item in value]
        return sorted(normalized_items, key=lambda x: json.dumps(x, sort_keys=True))
    return value


def canonical_json(obj: Any) -> str:
    """Serialize any model or Python structure into deterministic canonical JSON."""
    normalized = _normalize_value(obj)
    return json.dumps(
        normalized,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )


def compute_finding_ref(finding: Finding) -> str:
    """Compute stable 12-char SHA-256 reference of a canonicalized Finding."""
    payload = canonical_json(finding)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]


def compute_decision_id(decision: Decision) -> str:
    """Compute stable 16-char SHA-256 identifier of a Decision excluding timestamp."""
    data = decision.model_dump(mode="python")
    data.pop("timestamp", None)
    payload = canonical_json(data)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
