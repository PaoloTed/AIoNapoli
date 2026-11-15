"""Canonical JSON and hash utilities re-exported from pure domain logic."""

from __future__ import annotations

from app.domain.logic.refs import (
    canonical_json,
    compute_decision_id,
    compute_finding_ref,
    compute_proposal_signature,
)

__all__ = [
    "canonical_json",
    "compute_decision_id",
    "compute_finding_ref",
    "compute_proposal_signature",
]
