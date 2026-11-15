"""Opt-in PostgreSQL regression tests, using isolated disposable schemas."""

import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest

from app.domain.models.disruption import DisruptionInput, DisruptionLinkInput, LinkEntityType
from app.repositories.disruptions import DisruptionRepository

DATABASE_URL = os.environ.get("DISRUPTION_TEST_DATABASE_URL", "")
pytestmark = [pytest.mark.db, pytest.mark.skipif(not DATABASE_URL, reason="Postgres opt-in")]
ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def isolated():
    psycopg = pytest.importorskip("psycopg")
    conn = psycopg.connect(DATABASE_URL)
    schema = "test_namespaces_" + uuid4().hex
    conn.execute(f'CREATE SCHEMA "{schema}"')
    conn.execute(f'SET search_path TO "{schema}", public')
    for table in (
        "reference_entities",
        "service_alerts",
        "service_alert_links",
        "service_alert_revisions",
        "gtfs_datasets",
    ):
        conn.execute(f'CREATE TABLE "{schema}".{table} (LIKE public.{table} INCLUDING ALL)')
    conn.execute(
        "ALTER TABLE reference_entities DROP CONSTRAINT IF EXISTS "
        "reference_entities_gtfs_namespace_check"
    )
    conn.execute(
        "ALTER TABLE service_alert_links ADD CONSTRAINT "
        "service_alert_links_entity_key_fkey FOREIGN KEY (entity_key) "
        "REFERENCES reference_entities(entity_key)"
    )
    conn.commit()
    try:
        yield conn, schema
    finally:
        conn.rollback()
        conn.execute("SET search_path TO public")
        conn.execute(f'DROP SCHEMA "{schema}" CASCADE')
        conn.commit()
        conn.close()


def test_legacy_migration_preserves_links_and_audit(isolated):
    conn, _ = isolated
    conn.execute("""INSERT INTO reference_entities
        (entity_key,domain,entity_type,dataset_key,entity_id,dataset_version)
        VALUES ('gtfs:route:2','gtfs','route','eav','2','v1')""")
    conn.execute("""INSERT INTO service_alerts
        (source_id,alert_id,severity,valid_from,confidence,title,data_reference)
        VALUES ('fixture_namespace','legacy','high',NOW(),0.9,'Test','fixture')""")
    for link_ref, dataset in (("gtfs:route:2|||||||", "eav"), ("mismatch", "anm")):
        conn.execute(
            """INSERT INTO service_alert_links
            (source_id,alert_id,link_ref,entity_type,entity_key,raw_reference,
             resolution_status,dataset_key)
            VALUES ('fixture_namespace','legacy',%s,'route','gtfs:route:2',
                    'route:2','resolved',%s)""",
            (link_ref, dataset),
        )
    conn.execute("""INSERT INTO service_alert_revisions
        (source_id,alert_id,revision,content_hash,payload)
        VALUES ('fixture_namespace','legacy',1,'original','{"original":true}')""")
    before = conn.execute("SELECT link_id FROM service_alert_links ORDER BY link_id").fetchall()
    conn.execute((ROOT / "database/migrations/005_gtfs_reference_namespaces.sql").read_text())
    conn.commit()
    assert conn.execute("SELECT entity_key FROM reference_entities").fetchone() == (
        "gtfs:eav:route:2",
    )
    rows = conn.execute(
        "SELECT link_id, entity_key, link_ref, resolution_status "
        "FROM service_alert_links ORDER BY link_id"
    ).fetchall()
    assert [row[0] for row in rows] == [row[0] for row in before]
    assert rows[0][1:] == ("gtfs:eav:route:2", "gtfs:eav:route:2|||||||", "resolved")
    assert rows[1][1] is None and rows[1][3] == "unresolved"
    assert conn.execute("SELECT payload FROM service_alert_revisions").fetchone()[0] == {
        "original": True
    }


def test_two_feed_syncs_and_disruptions_stay_separate(isolated):
    from psycopg import sql

    conn, schema = isolated
    conn.execute("""CREATE TABLE routes (route_id TEXT, route_short_name TEXT,
        route_long_name TEXT, route_type INTEGER);
        INSERT INTO routes VALUES ('2','2','Test route',2);
        CREATE TABLE trips (trip_id TEXT, route_id TEXT, service_id TEXT, trip_headsign TEXT);
        INSERT INTO trips VALUES ('same:trip','2','weekday','Test');
        CREATE TABLE stops (stop_id TEXT, stop_name TEXT);
        INSERT INTO stops VALUES ('same:stop','Test stop');""")
    conn.commit()
    sync = (ROOT / "infra/postgres/sync-gtfs-refs.sql").read_text()

    def sync_dataset(dataset):
        query = sync.replace(":" + '"gtfs_schema"', sql.Identifier(schema).as_string(conn))
        query = query.replace(":'dataset_key'", sql.Literal(dataset).as_string(conn))
        query = query.replace(":'dataset_version'", "'v1'")
        conn.commit()
        conn.execute(query)
        conn.commit()

    sync_dataset("eav")
    sync_dataset("anm")
    sync_dataset("anm")  # An ANM refresh must not change EAV references.
    rows = conn.execute(
        "SELECT dataset_key,count(*),bool_and(is_current) "
        "FROM reference_entities GROUP BY dataset_key ORDER BY dataset_key"
    ).fetchall()
    assert rows == [("anm", 3, True), ("eav", 3, True)]
    repo = DisruptionRepository(conn)
    at = datetime(2026, 11, 16, tzinfo=timezone.utc)
    for dataset in ("eav", "anm"):
        repo.upsert(
            DisruptionInput(
                source_id="fixture_namespace",
                alert_id=dataset,
                title="[SIMULATO] Test",
                data_reference="fixture:namespace",
                alert_type="closure",
                effect="block",
                severity="high",
                confidence=0.9,
                published_at=at,
                valid_from=at,
                valid_to=datetime(2026, 11, 17, tzinfo=timezone.utc),
                is_simulated=True,
                links=[
                    DisruptionLinkInput(entity_type=kind, entity_id=identifier, dataset_key=dataset)
                    for kind, identifier in (
                        (LinkEntityType.ROUTE, "2"),
                        (LinkEntityType.TRIP, "same:trip"),
                        (LinkEntityType.STOP, "same:stop"),
                    )
                ],
            )
        )
    for kind, identifier in (
        (LinkEntityType.ROUTE, "2"),
        (LinkEntityType.TRIP, "same:trip"),
        (LinkEntityType.STOP, "same:stop"),
    ):
        for dataset in ("eav", "anm"):
            found = repo.find_applicable(
                kind, identifier, at, dataset_key=dataset, include_simulated=True
            )
            assert [alert.alert_id for alert in found] == [dataset]
    eav_before = repo.get("fixture_namespace", "eav")
    assert eav_before is not None
    assert all(link.entity_key.startswith("gtfs:eav:") for link in eav_before.links)
