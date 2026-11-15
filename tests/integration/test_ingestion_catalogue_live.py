"""Opt-in: real ANM document -> validated mock extraction -> repository write.

The model answer is a test fixture and the resulting alert is marked simulated.
No real closure is created and the fixture is removed at the end.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

import pytest

from app.config.sources import load_source_registry
from app.db.migrations import apply_migrations
from app.domain.models.disruption import LinkEntityType
from app.repositories.disruptions import DisruptionRepository
from app.services.ingestion.catalogue import DisruptionCataloguer
from app.services.ingestion.extraction import NewsExtraction, NewsExtractor
from app.services.ingestion.repository import IngestionRepository
from app.services.ingestion.resolver import EntityResolver
from app.services.llm.client import LlmResponse
from app.services.orchestrator.config import load_config

DATABASE_URL = os.environ.get("INGESTION_TEST_DATABASE_URL", "")
pytestmark = [
    pytest.mark.db,
    pytest.mark.skipif(not DATABASE_URL, reason="INGESTION_TEST_DATABASE_URL non impostata"),
]


class StaticLlmClient:
    model = "mock-static-news-extraction"

    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload

    def complete_json(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        schema_name: str = "response",
    ) -> LlmResponse:
        return LlmResponse(
            text=json.dumps(self.payload, ensure_ascii=False),
            model=self.model,
            latency_ms=1,
            raw={},
        )


def test_real_document_with_mock_extraction_is_catalogued_and_isolated() -> None:
    psycopg = pytest.importorskip("psycopg")
    conn = psycopg.connect(DATABASE_URL)
    apply_migrations(conn)
    repo = IngestionRepository(conn)
    source_row = repo.source("anm_news")
    if source_row is None:
        conn.close()
        pytest.skip("fonte anm_news non censita: eseguire prima l'acquisizione")
    documents = repo.list_documents(source_id="anm_news", limit=200)
    document_summary = next(
        (item for item in documents if "linea 1" in item["title"].casefold()), None
    )
    if document_summary is None:
        conn.close()
        pytest.skip("nessun documento ANM sulla Linea 1 disponibile")
    document = repo.document(int(document_summary["document_id"]))
    assert document is not None
    config = load_config().model_copy(
        update={"llm_mode": "mock", "llm_model": StaticLlmClient.model}
    )
    source = load_source_registry().by_id()["anm_news"]
    payload = {
        "relevant": True,
        "relevance_reason": "Chiusura anticipata della Linea 1 citata nel documento.",
        "category": "service_change",
        "problem_type": "chiusura anticipata del servizio",
        "operator_names": ["ANM"],
        "route_refs": ["L1"],
        "trip_refs": [],
        "stop_refs": ["CHIAIANO"],
        "place_names": [],
        "road_refs": [],
        "modes": ["SUBWAY"],
        "directions": [],
        "effect": "block",
        "severity": "medium",
        "lifecycle": "active",
        "valid_from": "2026-11-09T20:00:00+01:00",
        "valid_to": "2026-11-12T23:59:00+01:00",
        "recurrence": None,
        "published_is_event_start": False,
        "location_scope": "local",
        "affects_public_transport": True,
        "confidence": 0.9,
        "uncertainty": "low",
        "evidence": [{"quote": "METRO LINEA 1", "supports": "linea coinvolta"}],
        "unresolved_details": [],
        "notes": "Fixture mock su documento reale.",
    }
    client = StaticLlmClient(payload)
    extractor = NewsExtractor(repo, config, client=client)
    disruption_repo = DisruptionRepository(
        conn,
        gtfs_schema="gtfs_anm",
        gtfs_dataset_key="anm",
        osm_dataset_key="osm_napoli",
    )
    resolver = EntityResolver(
        conn, gtfs_schemas=config.gtfs_datasets, osm_schema=config.osm_schema
    )
    cataloguer = DisruptionCataloguer(disruption_repo, config, is_simulated=True)
    alert_id: str | None = None
    try:
        outcome = extractor.interpret(document, source)
        resolution = resolver.resolve_extraction(outcome.extraction, source)
        alert = cataloguer.catalogue(
            document=document,
            source=source,
            extraction=outcome.extraction,
            resolution=resolution,
        )
        assert alert is not None
        alert_id = alert.alert_id
        assert alert.is_simulated is True
        assert any(
            link.entity_key == "gtfs:anm:route:4955" for link in alert.links
        )
        at = datetime(2026, 11, 10, 12, 0, tzinfo=timezone.utc)
        real_only = disruption_repo.find_applicable(
            LinkEntityType.ROUTE, "4955", at, dataset_key="anm"
        )
        assert all(item.source_id != "ingest:anm_news" for item in real_only)
        simulated = disruption_repo.find_applicable(
            LinkEntityType.ROUTE,
            "4955",
            at,
            dataset_key="anm",
            include_simulated=True,
        )
        assert any(item.alert_id == alert_id for item in simulated)

        resolved = NewsExtraction.model_validate(
            {
                **payload,
                "lifecycle": "resolved",
                "effect": "info",
                "valid_to": None,
                "notes": "Riapertura simulata per il test di rettifica.",
            }
        )
        updated = cataloguer.catalogue(
            document=document,
            source=source,
            extraction=resolved,
            resolution=resolution,
            now=datetime(2026, 11, 13, 9, 0, tzinfo=timezone.utc),
        )
        assert updated is not None
        assert updated.alert_id == alert_id
        assert updated.revision == 2
        assert updated.lifecycle_status.value == "resolved"
        assert updated.valid_to is not None
    finally:
        if alert_id:
            conn.execute(
                "DELETE FROM service_alerts WHERE source_id = 'ingest:anm_news' AND alert_id = %s",
                (alert_id,),
            )
            conn.execute(
                "DELETE FROM ingestion_interpretations WHERE model = %s AND document_id = %s",
                (StaticLlmClient.model, int(document["document_id"])),
            )
            conn.commit()
        conn.close()
