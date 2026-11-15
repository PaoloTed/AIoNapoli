"""Structured single-line JSON logging utilities."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any


def get_logger(name: str = "napoli_agentic_city") -> logging.Logger:
    """Return configured logger emitting JSON lines."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("%(message)s"))
        logger.addHandler(handler)
        logger.propagate = False
    return logger


def format_log_event(
    component: str,
    event: str,
    *,
    level: str = "info",
    finding_ref: str | None = None,
    decision_id: str | None = None,
    detail: str | None = None,
) -> str:
    """Format a structured JSON log line without secrets or full payloads."""
    payload: dict[str, Any] = {
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
        "level": level.lower(),
        "component": component,
        "event": event,
    }
    if finding_ref is not None:
        payload["finding_ref"] = finding_ref
    if decision_id is not None:
        payload["decision_id"] = decision_id
    if detail is not None:
        payload["detail"] = detail
    return json.dumps(payload, sort_keys=True, ensure_ascii=False)


def log_event(
    component: str,
    event: str,
    *,
    level: str = "info",
    finding_ref: str | None = None,
    decision_id: str | None = None,
    detail: str | None = None,
) -> None:
    """Emit a structured JSON log event."""
    logger = get_logger()
    line = format_log_event(
        component=component,
        event=event,
        level=level,
        finding_ref=finding_ref,
        decision_id=decision_id,
        detail=detail,
    )
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logger.log(numeric_level, line)
