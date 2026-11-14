"""Contract tests for the frozen 9-field Finding schema."""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from shared.schemas.finding import FINDING_FIELDS, Finding


def test_nove_campi() -> None:
    expected = {
        "agent",
        "type",
        "content",
        "confidence",
        "severity",
        "source_id",
        "data_reference",
        "is_simulated",
        "timestamp",
    }
    assert set(Finding.model_fields.keys()) == expected
    assert FINDING_FIELDS == expected


def test_content_libero() -> None:
    finding = Finding.model_validate(
        {
            "agent": "crowding",
            "type": "density_alert",
            "content": {
                "density": 0.91,
                "zone_id": "Z_BAGNOLI",
                "note": "campo extra libero",
                "custom_nested": {"k": [1, 2, 3]},
            },
            "confidence": 0.82,
            "severity": "high",
            "source_id": "ir_sensors",
            "data_reference": "occupancy:2026-11-14T17:40:00+01:00",
            "is_simulated": True,
            "timestamp": "2026-11-14T17:40:00+01:00",
        }
    )
    assert finding.content["note"] == "campo extra libero"
    assert finding.content["custom_nested"] == {"k": [1, 2, 3]}


def test_type_incoerente() -> None:
    with pytest.raises(ValidationError):
        Finding.model_validate(
            {
                "agent": "mobility",
                "type": "density_alert",
                "content": {},
                "confidence": 0.8,
                "severity": "high",
                "source_id": "anm",
                "data_reference": "gtfs:1",
                "is_simulated": False,
                "timestamp": "2026-11-14T17:40:00+01:00",
            }
        )
