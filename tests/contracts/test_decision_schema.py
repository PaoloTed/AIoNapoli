"""Contract tests for the frozen 6-field Decision schema."""

from __future__ import annotations

from shared.schemas.decision import DECISION_FIELDS, Decision


def test_sei_campi() -> None:
    expected = {
        "trigger",
        "conflict",
        "plan",
        "reasoning_log",
        "confidence",
        "timestamp",
    }
    assert set(Decision.model_fields.keys()) == expected
    assert DECISION_FIELDS == expected


def test_senza_relevance() -> None:
    assert "relevance" not in Decision.model_fields
    assert "narrative" not in Decision.model_fields
    assert "decision_id" not in Decision.model_fields
