"""Deterministic prompt parsing for the three acceptance examples."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from app.services.input.prompt_parser import parse_prompt

TZ = ZoneInfo("Europe/Rome")
NOW = datetime(2026, 11, 15, 9, 0, tzinfo=TZ)


def test_example_campano_citta_della_scienza() -> None:
    result = parse_prompt(
        "Da via Giovanni Antonio Campano a Città della Scienza domani alle 8",
        now=NOW,
        timezone=TZ,
    )
    assert result.origin_text == "via Giovanni Antonio Campano"
    assert result.destination_text == "Città della Scienza"
    assert result.depart_at == datetime(2026, 11, 16, 8, 0, tzinfo=TZ)
    assert result.arrive_by is None
    assert result.contradictions == []


def test_example_chiaiano_mann_preferences() -> None:
    result = parse_prompt(
        "Dalla metro Chiaiano al MANN, con meno cammino possibile",
        now=NOW,
        timezone=TZ,
    )
    assert result.origin_text == "metro Chiaiano"
    assert result.destination_text == "MANN"
    assert result.preferences.minimize_walk is True
    assert result.depart_at == NOW


def test_example_arrive_by() -> None:
    result = parse_prompt(
        "Da qui a Piazza Garibaldi, devo arrivare entro le 10",
        now=NOW,
        timezone=TZ,
    )
    assert result.origin_text == "qui"
    assert result.destination_text == "Piazza Garibaldi"
    assert result.depart_at is None
    assert result.arrive_by == datetime(2026, 11, 15, 10, 0, tzinfo=TZ)


def test_contradiction_is_rejected() -> None:
    result = parse_prompt(
        "Da via Roma a Piazza Garibaldi, parto alle 10 ed entro le 9",
        now=NOW,
        timezone=TZ,
    )
    assert result.contradictions


def test_unsupported_accessibility_is_explicit() -> None:
    result = parse_prompt(
        "Da Chiaiano al MANN senza scale, accessibile",
        now=NOW,
        timezone=TZ,
    )
    assert "assenza di scale" in result.preferences.unsupported_constraints
    assert "accessibilita' verificata" in result.preferences.unsupported_constraints


def test_relative_time_is_parsed() -> None:
    result = parse_prompt("Da Chiaiano al MANN tra 30 minuti", now=NOW, timezone=TZ)
    assert result.depart_at is not None
    assert (result.depart_at - NOW).total_seconds() == 1800
