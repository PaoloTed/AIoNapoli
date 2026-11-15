"""The registry must census every unique endpoint, not a hand-picked subset."""

from __future__ import annotations

from app.config.sources import load_source_registry


def test_registry_contains_all_unique_sources_and_anm_scraper() -> None:
    registry = load_source_registry()
    assert len(registry.sources) == 96
    assert len({source.url for source in registry.sources}) == 96
    by_id = registry.by_id()
    assert by_id["anm_news"].kind == "anm_scraper"
    assert by_id["anm_news"].enabled is True
    for source_id in (
        "eav_rail",
        "eav_bus",
        "eav_access",
        "rfi_camp_updates",
        "pc_campania_avvisi",
        "cciss",
        "mit_scioperi",
        "ingv_terremoti",
        "comune_notizie",
        "google_news_viabilita_7d",
        "ilmattino_napoli",
        "capodimonte",
        "citta_scienza",
        "anm_feed",
    ):
        assert source_id in by_id
    assert by_id["anm_feed"].kind == "non_rss"
    assert by_id["anm_feed"].enabled is False
    assert by_id["cciss"].source_class == "official_transport"
    assert by_id["ingv_terremoti"].kind == "atom"


def test_registry_provenance_is_preserved_for_duplicate_endpoints() -> None:
    registry = load_source_registry()
    urls = [source.url for source in registry.sources]
    assert len(urls) == len(set(urls))
    for source in registry.sources:
        assert source.source_id in source.provenance
        assert source.registry_hash()
