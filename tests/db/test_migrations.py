"""Database migration tests verifying from-scratch schema creation and idempotence."""

from __future__ import annotations

from app.db.migrations import apply_migrations
from app.db.session import get_sqlite_connection


def test_da_zero() -> None:
    """REQ-PER-01: migrations apply cleanly from zero on an empty database and are idempotent."""
    conn = get_sqlite_connection(":memory:")
    try:
        applied_first = apply_migrations(conn)
        assert applied_first == ["001_init.sql"]

        applied_second = apply_migrations(conn)
        assert applied_second == []

        rows = conn.execute(
            "SELECT name, type FROM sqlite_master WHERE type IN ('table', 'view')"
        ).fetchall()
        objects = {r["name"]: r["type"] for r in rows}

        expected_tables = {
            "schema_migrations",
            "zones",
            "stops",
            "routes",
            "trips",
            "stop_times",
            "service_alerts",
            "events",
            "weather_snapshots",
            "occupancy_estimates",
            "vehicle_positions",
            "trip_updates",
            "ingestion_runs",
            "findings",
            "decisions",
        }
        expected_views = {
            "v_weather_latest",
            "v_occupancy_latest",
            "v_service_alerts_active",
            "v_vehicle_positions_latest",
            "v_trip_updates_latest",
        }
        assert expected_tables.issubset({k for k, v in objects.items() if v == "table"})
        assert expected_views.issubset({k for k, v in objects.items() if v == "view"})
    finally:
        conn.close()

