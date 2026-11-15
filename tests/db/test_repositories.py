"""Tests verifying identical pipeline behavior across Memory and SQL repositories."""

from __future__ import annotations

from datetime import datetime

import httpx

from app.db.migrations import apply_migrations
from app.db.session import get_sqlite_connection
from app.domain.models.config import AppConfig
from app.domain.models.finding import Finding
from app.repositories.memory import InMemorySourceRepository
from app.repositories.postgres import PostgresSourceRepository
from app.services.agents.context.agent import ContextAgent
from app.services.agents.crowding.agent import CrowdingAgent
from app.services.agents.mobility.agent import MobilityAgent
from app.services.agents.mobility.otp_client import OtpClient
from app.services.connectors.events.connector import EventsConnector
from app.services.connectors.gtfs.connector import GtfsConnector
from app.services.connectors.occupancy.connector import OccupancyConnector
from app.services.connectors.rss.connector import RssConnector
from app.services.connectors.weather.connector import WeatherConnector
from app.services.orchestrator.pipeline import run_pipeline
from app.utils.clock import FixedClock


def _seed_and_run_agents(
    repo: InMemorySourceRepository | PostgresSourceRepository, now: datetime
) -> list[Finding]:
    offline_http = httpx.Client(
        transport=httpx.MockTransport(
            lambda req: (_ for _ in ()).throw(httpx.ConnectError("offline", request=req))
        )
    )
    GtfsConnector(repo, http_client=offline_http).run_static()
    RssConnector(repo, client=offline_http).fallback()
    GtfsConnector(repo, http_client=offline_http).fallback(now=now)
    WeatherConnector(repo, client=offline_http).fallback()
    EventsConnector(repo).run()
    OccupancyConnector(repo).run()

    otp = OtpClient(base_url="http://127.0.0.1:59999", http_client=offline_http, mode="demo")
    f_mob = MobilityAgent(repo, otp_client=otp).evaluate(route_id="L2", now=now)
    f_crd = CrowdingAgent(repo).evaluate(zone_id="Z_BAGNOLI", now=now)
    f_ctx = ContextAgent(repo).evaluate(zone_id="Z_BAGNOLI", now=now)
    assert isinstance(f_mob, Finding)
    assert isinstance(f_crd, Finding)
    assert isinstance(f_ctx, Finding)
    return [f_mob, f_crd, f_ctx]


def test_due_implementazioni(app_config: AppConfig, fixed_clock: FixedClock) -> None:
    """REQ-PER-03: Memory and SQL repositories produce identical decisions."""
    now = fixed_clock.now()
    mem_repo = InMemorySourceRepository(load_fixtures=True)

    conn = get_sqlite_connection(":memory:")
    try:
        apply_migrations(conn)
        sql_repo = PostgresSourceRepository(conn)

        mem_findings = _seed_and_run_agents(mem_repo, now)
        sql_findings = _seed_and_run_agents(sql_repo, now)

        out_mem = run_pipeline(mem_findings, app_config, clock=fixed_clock)
        out_sql = run_pipeline(sql_findings, app_config, clock=fixed_clock)

        assert out_mem.decision_id == out_sql.decision_id
        assert out_mem.decision.model_dump() == out_sql.decision.model_dump()
    finally:
        conn.close()
