"""Validation tests for disruption models (no database)."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.domain.models.disruption import (
    DisruptionEffect,
    DisruptionInput,
    DisruptionLinkInput,
    LifecycleStatus,
    LinkEntityType,
    VerificationStatus,
)
from app.domain.models.finding import Severity


def _input(**overrides: object) -> DisruptionInput:
    values: dict[str, object] = {
        "source_id": "test",
        "alert_id": "a1",
        "data_reference": "fixture:test:a1",
        "title": "Test",
        "alert_type": "closure",
        "effect": DisruptionEffect.BLOCK,
        "severity": Severity.HIGH,
        "confidence": 0.8,
        "published_at": datetime(2026, 11, 14, tzinfo=timezone.utc),
        "valid_from": datetime(2026, 11, 15, tzinfo=timezone.utc),
        "valid_to": datetime(2026, 11, 20, tzinfo=timezone.utc),
        "is_simulated": True,
        "links": [DisruptionLinkInput(entity_type=LinkEntityType.ROUTE, entity_id="2")],
    }
    values.update(overrides)
    return DisruptionInput.model_validate(values)


def test_block_requires_a_link() -> None:
    with pytest.raises(ValueError):
        _input(links=[])


def test_unknown_expiry_requires_review() -> None:
    with pytest.raises(ValueError):
        _input(valid_to=None, verification_status=VerificationStatus.VERIFIED)
    with pytest.raises(ValueError):
        _input(valid_to=None, verification_status=VerificationStatus.NEEDS_REVIEW)
    ok = _input(
        valid_to=None,
        verification_status=VerificationStatus.NEEDS_REVIEW,
        next_review_at=datetime(2026, 11, 21, tzinfo=timezone.utc),
    )
    assert ok.verification_status is VerificationStatus.NEEDS_REVIEW


def test_future_publication_and_lifecycle_are_not_active() -> None:
    future = _input(
        published_at=datetime(2026, 12, 1, tzinfo=timezone.utc),
        valid_from=datetime(2026, 11, 15, tzinfo=timezone.utc),
        valid_to=datetime(2026, 12, 31, tzinfo=timezone.utc),
    )
    assert not future.is_temporally_applicable(datetime(2026, 11, 16, tzinfo=timezone.utc))
    resolved = _input(lifecycle_status=LifecycleStatus.RESOLVED)
    assert not resolved.is_temporally_applicable(datetime(2026, 11, 16, tzinfo=timezone.utc))
