"""Database schema verification tests for per-row provenance columns."""

from __future__ import annotations

from app.db.migrations import apply_migrations
from app.db.session import get_sqlite_connection

SOURCE_TABLES = (
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
)
PROVENANCE_COLUMNS = {"source_id", "data_reference", "is_simulated", "ingested_at"}


def test_tracciabilita_riga() -> None:
    """REQ-PER-02: source tables carry source_id, data_reference, is_simulated, ingested_at."""
    conn = get_sqlite_connection(":memory:")
    try:
        apply_migrations(conn)
        for table in SOURCE_TABLES:
            cols = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
            missing = PROVENANCE_COLUMNS - cols
            assert not missing, f"Table '{table}' missing provenance columns: {sorted(missing)}"
    finally:
        conn.close()
