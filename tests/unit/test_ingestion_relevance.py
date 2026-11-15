"""Irrelevant local news must not reach the LLM only because of a keyword."""

from __future__ import annotations

from datetime import datetime, timezone

from app.config.sources import SourceDefinition
from app.services.ingestion.parsing import ParsedEntry
from app.services.ingestion.relevance import assess_relevance


def _source(**overrides: object) -> SourceDefinition:
    values = {
        "source_id": "local_news",
        "name": "News locale",
        "url": "https://example.test/feed",
        "kind": "rss",
        "source_class": "local_news",
        "local_relevance": "required",
        "provenance": ["local_news"],
    }
    values.update(overrides)
    return SourceDefinition.model_validate(values)


def _entry(title: str, body: str) -> ParsedEntry:
    return ParsedEntry(
        external_id="1",
        title=title,
        body=body,
        link="https://example.test/1",
        published_at=datetime(2026, 11, 14, tzinfo=timezone.utc),
        published_precision="second",
        language="it",
        raw={},
    )


def test_local_football_news_is_not_a_mobility_candidate() -> None:
    decision = assess_relevance(
        _entry("Napoli batte la Roma", "La partita si e' giocata allo stadio."),
        _source(),
    )
    assert decision.candidate is False


def test_closure_news_is_candidate_but_not_automatically_an_obstacle() -> None:
    decision = assess_relevance(
        _entry(
            "Chiusura temporanea della metropolitana Linea 1",
            "La stazione Chiaiano e' chiusa per lavori.",
        ),
        _source(),
    )
    assert decision.candidate is True
    assert decision.is_obstacle_candidate is True


def test_national_feed_requires_a_local_reference() -> None:
    source = _source(
        source_id="cciss", source_class="official_transport", local_relevance="required"
    )
    assert (
        assess_relevance(_entry("Incidente in autostrada", "Code e chiusura."), source).candidate
        is False
    )
    assert (
        assess_relevance(
            _entry("Incidente in A1 Roma-Napoli", "Code e chiusura vicino Napoli."),
            source,
        ).candidate
        is True
    )


def test_tourism_event_is_sent_for_semantic_judgement() -> None:
    source = _source(
        source_id="capodimonte",
        source_class="tourism_culture",
        operator="capodimonte",
        local_relevance="required",
    )
    decision = assess_relevance(
        _entry("Mostra serale a Capodimonte", "Apertura straordinaria e navetta."),
        source,
    )
    assert decision.candidate is True
    assert decision.is_obstacle_candidate is False
