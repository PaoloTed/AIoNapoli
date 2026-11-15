"""Unit tests for ANM Scraper connector adapter and deduplication (06_agente_scraping.md §9)."""

from __future__ import annotations

from app.services.connectors.rss.anm_client import AnmClient
from app.services.connectors.rss.cache import DocumentCache
from app.services.connectors.rss.normalize import compute_document_hash, normalize_text


def test_mappatura_base() -> None:
    """Un articolo di esempio produce una riga con tutti i campi obbligatori di service_alerts."""
    client = AnmClient()
    article = {
        "id": "ART_1234",
        "title": "Linea R7 deviazione percorso per lavori",
        "body": "A causa di lavori stradali la linea R7 devia per via Coroglio.",
        "date": "2026-11-15T10:00:00+01:00",
        "url": "https://www.anm.it/notizia/1234",
    }
    row, doc_hash, was_cached = client.map_article(article)

    assert row["alert_id"] == "anm:ART_1234"
    assert row["route_id"] == "R7"
    assert row["source_id"] == "anm"
    assert row["confidence"] == 0.85
    assert row["data_reference"] == "https://www.anm.it/notizia/1234"
    assert not was_cached


def test_severity_da_keyword() -> None:
    """'chiusura' produce severità high, 'orari' produce low."""
    client = AnmClient()
    art_high = {
        "id": "A1",
        "title": "Chiusura immediata della linea",
        "body": "Tratta chiusa per guasto tecnico.",
    }
    row_high, _, _ = client.map_article(art_high)
    assert row_high["severity"] in ("high", "critical")

    art_low = {
        "id": "A2",
        "title": "Informazione orari estivi",
        "body": "Nuova tabella orari consultabile online.",
    }
    row_low, _, _ = client.map_article(art_low)
    assert row_low["severity"] in ("low", "medium")


def test_source_id_fonte_primaria() -> None:
    """source_id deve essere 'anm' (la fonte primaria, non il trasporto scraper)."""
    client = AnmClient()
    article = {"id": "A3", "title": "Avviso ANM", "body": "Dettaglio avviso"}
    row, _, _ = client.map_article(article)
    assert row["source_id"] == "anm"


def test_documento_invariato_zero_chiamate() -> None:
    """Due run sullo stesso corpo non generano una nuova chiamata al modello (was_cached=True)."""
    cache = DocumentCache()
    client = AnmClient(cache=cache)
    article = {"id": "A4", "title": "Avviso ripetuto", "body": "Testo identico del comunicato"}

    _, hash1, was_cached1 = client.map_article(article)
    assert was_cached1 is False

    _, hash2, was_cached2 = client.map_article(article)
    assert hash1 == hash2
    assert was_cached2 is True


def test_hash_su_corpo_normalizzato() -> None:
    """Spazi multipli e CRLF diversi producono lo stesso document_hash."""
    body_raw1 = "Linea 151   regolare.\r\nNessuna deviazione."
    body_raw2 = "Linea 151 regolare. \n Nessuna deviazione."

    norm1 = normalize_text(body_raw1)
    norm2 = normalize_text(body_raw2)
    assert norm1 == norm2

    hash1 = compute_document_hash(norm1)
    hash2 = compute_document_hash(norm2)
    assert hash1 == hash2


def test_html_rimosso() -> None:
    """I tag HTML vengono rimossi dal corpo normalizzato."""
    raw_html = "<p>Attenzione: <b>strada chiusa</b>.<br/>Seguire deviazione.</p>"
    cleaned = normalize_text(raw_html)
    assert "<" not in cleaned
    assert ">" not in cleaned
    assert "Attenzione: strada chiusa. Seguire deviazione." in cleaned


def test_alert_id_stabile() -> None:
    """Stesso articolo produce lo stesso alert_id in esecuzioni ripetute."""
    client = AnmClient()
    article = {"id": "9988", "title": "Avviso", "body": "Contenuto"}
    row1, _, _ = client.map_article(article)
    row2, _, _ = client.map_article(article)
    assert row1["alert_id"] == row2["alert_id"] == "anm:9988"
