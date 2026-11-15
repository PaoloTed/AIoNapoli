"""Real-time freshness tests enforcing the 90-second maximum position age."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import httpx

from app.db.migrations import apply_migrations
from app.db.session import get_sqlite_connection
from app.domain.models.refusal import Refusal
from app.repositories.memory import InMemorySourceRepository
from app.repositories.postgres import PostgresSourceRepository
from app.services.agents.mobility.agent import MobilityAgent
from app.services.agents.mobility.otp_client import OtpClient
from app.services.connectors.gtfs.connector import GtfsConnector


def test_max_age() -> None:
    """REQ-CONN-11: vehicle positions older than 90 seconds are excluded from queries and agents."""
    now = datetime(2026, 11, 14, 17, 40, 0, tzinfo=timezone.utc)
    stale_time = now - timedelta(seconds=120)
    fresh_time = now - timedelta(seconds=20)

    conn = get_sqlite_connection(":memory:")
    try:
        apply_migrations(conn)
        sql_repo = PostgresSourceRepository(conn)
        mem_repo = InMemorySourceRepository(load_fixtures=True)
        offline_http = httpx.Client(
            transport=httpx.MockTransport(
                lambda req: (_ for _ in ()).throw(httpx.ConnectError("offline", request=req))
            )
        )
        otp = OtpClient(base_url="http://127.0.0.1:59999", http_client=offline_http, mode="demo")

        for repo in (mem_repo, sql_repo):
            GtfsConnector(repo, http_client=offline_http).run_static()
            repo.upsert_vehicle_positions(
                [
                    {
                        "vehicle_id": "ANM-OLD",
                        "route_id": "R2",
                        "trip_id": None,
                        "observed_at": stale_time.isoformat(),
                        "latitude": 40.82,
                        "longitude": 14.17,
                        "bearing": 180.0,
                        "speed_mps": 4.0,
                        "zone_id": "Z_BAGNOLI",
                        "source_id": "anm",
                        "data_reference": "https://proxy.busone.app/anm/gtfs-rt?ts=old",
                        "is_simulated": False,
                        "ingested_at": now.isoformat(),
                    }
                ]
            )
            assert repo.get_fresh_vehicle_positions(now=now, max_age_s=90) == []

            # With only stale positions and strict real-time required, agent refuses
            refusal = MobilityAgent(repo, otp_client=otp, rt_max_age_s=90).evaluate(
                route_id="L2",
                allow_simulation=False,
                require_realtime=True,
                now=now,
            )
            assert isinstance(refusal, Refusal)
            assert refusal.reason_code == "missing_realtime"

            # Add fresh position (<= 90s)
            repo.upsert_vehicle_positions(
                [
                    {
                        "vehicle_id": "ANM-FRESH",
                        "route_id": "R2",
                        "trip_id": None,
                        "observed_at": fresh_time.isoformat(),
                        "latitude": 40.821,
                        "longitude": 14.179,
                        "bearing": 210.0,
                        "speed_mps": 6.0,
                        "zone_id": "Z_BAGNOLI",
                        "source_id": "anm",
                        "data_reference": "https://proxy.busone.app/anm/gtfs-rt?ts=fresh",
                        "is_simulated": False,
                        "ingested_at": now.isoformat(),
                    }
                ]
            )
            fresh_rows = repo.get_fresh_vehicle_positions(now=now, max_age_s=90)
            assert [r["vehicle_id"] for r in fresh_rows] == ["ANM-FRESH"]
    finally:
        conn.close()

