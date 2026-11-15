"""Backend CLI entrypoint for operations, ingestion and diagnostics."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.db.migrations import apply_migrations
from app.db.session import get_connection
from app.domain.models.finding import AgentName
from app.services.connectors.events.connector import EventsConnector
from app.services.connectors.gtfs.connector import GtfsConnector
from app.services.connectors.occupancy.connector import OccupancyConnector
from app.services.connectors.rss.connector import RssConnector
from app.services.connectors.weather.connector import WeatherConnector
from app.services.facade import BackendService
from app.services.ingestion.worker import run_worker
from app.services.llm.client import (
    LlmUnavailableError,
    OpenAICompatibleClient,
    llm_configuration_status,
)
from app.services.orchestrator.config import ConfigInvalidError, load_config


def _cmd_config_validate() -> int:
    try:
        cfg = load_config()
    except ConfigInvalidError as exc:
        print(json.dumps({"status": "error", "code": exc.code, "detail": exc.detail}))
        return 1
    print(cfg.model_dump_json(indent=2))
    return 0


def _legacy_ingest(args: argparse.Namespace) -> int:
    cfg = load_config()
    service = BackendService(config=cfg)
    try:
        connectors = {
            "rss": RssConnector(service.repository, timeout_s=cfg.http_timeout_s),
            "gtfs": GtfsConnector(service.repository, config=cfg),
            "gtfs-rt": GtfsConnector(service.repository, config=cfg),
            "weather": WeatherConnector(service.repository, timeout_s=cfg.http_timeout_s),
            "events": EventsConnector(service.repository),
            "occupancy": OccupancyConnector(service.repository),
        }
        if getattr(args, "status", False):
            gtfs_conn = connectors["gtfs-rt"]
            assert isinstance(gtfs_conn, GtfsConnector)
            try:
                status_data = gtfs_conn.fetch_status()
                print(json.dumps(status_data, indent=2))
                return 0
            except Exception as exc:
                print(json.dumps({"status": "unreachable", "detail": str(exc)}))
                return 0

        # BusOne is legacy material, never part of --all or the default path.
        targets = (
            ["rss", "gtfs", "weather", "events", "occupancy"] if args.all else [args.connector]
        )
        outcomes = []
        for name in targets:
            if name not in connectors:
                print(f"Connettore sconosciuto: {name}", file=sys.stderr)
                return 2
            conn = connectors[name]
            if args.fallback:
                out = conn.fallback()
            elif name == "gtfs":
                out = conn.run(mode="static")  # type: ignore[call-arg]
            else:
                out = conn.run()
            outcomes.append(out.model_dump())
        print(json.dumps(outcomes, indent=2, ensure_ascii=False))
        return 0
    finally:
        service.close()


def _cmd_ingest(args: argparse.Namespace) -> int:
    if getattr(args, "legacy", False):
        return _legacy_ingest(args)
    if getattr(args, "status", False):
        return _cmd_ingestion_status()
    try:
        result = run_worker(
            once=True,
            force=bool(getattr(args, "force", False)),
            source_id=getattr(args, "source", None),
            verify=bool(getattr(args, "verify", False)),
        )
    except Exception as exc:  # noqa: BLE001 - CLI must report clearly
        print(
            json.dumps(
                {
                    "status": "error",
                    "detail": f"{type(exc).__name__}: {exc}",
                    "hint": "richiede APP_PROFILE=postgres e DATABASE_URL",
                },
                indent=2,
            )
        )
        return 2
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
    return 0


def _cmd_db(args: argparse.Namespace) -> int:
    cfg = load_config()
    profile = cfg.app_profile if cfg.app_profile != "memory" else "sqlite"
    if args.action == "reset" and profile == "sqlite":
        db_file = Path(cfg.sqlite_path)
        if db_file.exists():
            db_file.unlink()
    conn = get_connection(
        profile,
        sqlite_path=cfg.sqlite_path,
        database_url=cfg.database_url,
    )
    try:
        if args.action in ("migrate", "reset"):
            applied = apply_migrations(conn)
            print(json.dumps({"action": args.action, "applied": applied}))
        elif args.action == "seed":
            apply_migrations(conn)
            from app.repositories.postgres import PostgresSourceRepository

            repo = PostgresSourceRepository(conn)
            gtfs = GtfsConnector(repo, config=cfg)
            res = gtfs.run_static()
            print(json.dumps({"action": "seed", "rows_written": res.rows_written}))
        return 0
    finally:
        conn.close()


def _cmd_demo(args: argparse.Namespace) -> int:
    cfg = load_config()
    if args.profile:
        cfg = cfg.model_copy(update={"app_profile": args.profile})
    service = BackendService(config=cfg)
    try:
        scenario = service.get_scenario_data(args.scenario)
        resp, _ = service.decide_from_request({"scenario_id": args.scenario})
        findings = scenario.findings
        simulated_count = sum(1 for f in findings if f.is_simulated)
        latest_finding_ts = max(f.timestamp for f in findings)
        latency_s = max(0.0, (resp.decision.timestamp - latest_finding_ts).total_seconds())
        distinct_targets = len({item.target for item in resp.decision.plan})

        resp2, _ = service.decide_from_request({"scenario_id": args.scenario})
        deterministic = resp.decision_id == resp2.decision_id

        report = {
            "scenario_id": args.scenario,
            "decision_id": resp.decision_id,
            "deterministic_replay": deterministic,
            "reasoning_log_steps": len(resp.decision.reasoning_log),
            "target_coverage": f"{distinct_targets}/3",
            "plan_items_count": len(resp.decision.plan),
            "simulated_findings_ratio": round(simulated_count / len(findings), 2)
            if findings
            else 0.0,
            "finding_to_decision_delta_s": round(latency_s, 3),
            "agents_present": [a.value for a in AgentName if any(f.agent == a for f in findings)],
        }
        if args.report:
            output_path = Path("backend/docs/DEMO_REPORT.json")
            output_path.write_text(
                json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            print(
                json.dumps(
                    {"report": report, "decision": resp.model_dump(mode="json")},
                    indent=2,
                    ensure_ascii=False,
                )
            )
        else:
            print(resp.model_dump_json(indent=2))
        return 0
    finally:
        service.close()


def _cmd_ingestion(args: argparse.Namespace) -> int:
    cfg = load_config()
    if args.action == "run":
        try:
            result = run_worker(
                once=args.once,
                force=args.force,
                source_id=args.source,
                interval_s=args.interval,
                verify=args.verify,
                config=cfg,
            )
        except Exception as exc:  # noqa: BLE001
            print(
                json.dumps(
                    {"status": "error", "detail": f"{type(exc).__name__}: {exc}"},
                    indent=2,
                )
            )
            return 2
        print(json.dumps(result, indent=2, ensure_ascii=False, default=str))
        return 0
    service = BackendService(config=cfg)
    try:
        with service._db_lock:
            repo = service._ingestion_repo()
            if args.action == "status":
                payload = repo.status_summary()
            elif args.action == "sources":
                payload = repo.list_sources()
            elif args.action == "documents":
                payload = repo.list_documents(
                    status=args.status, source_id=args.source, limit=args.limit
                )
            elif args.action == "fetches":
                payload = repo.fetches(source_id=args.source, limit=args.limit)
            else:
                return 2
        print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
        return 0
    finally:
        service.close()


def _cmd_ingestion_status() -> int:
    return _cmd_ingestion(argparse.Namespace(action="status"))


def _cmd_disruptions(args: argparse.Namespace) -> int:
    cfg = load_config()
    service = BackendService(config=cfg)
    try:
        if args.action == "list":
            payload = service.list_disruptions(
                include_simulated=args.include_simulated,
                window_hours=args.window_hours,
                limit=args.limit,
            )
        elif args.action == "get":
            payload = service.get_disruption(args.source_id, args.alert_id)
        elif args.action == "expire":
            from datetime import datetime, timezone

            assert service.disruption_repository is not None
            with service._db_lock:
                expired = service.disruption_repository.expire_due(datetime.now(timezone.utc))
                stale = service.disruption_repository.expire_stale_unknown(
                    datetime.now(timezone.utc)
                )
            payload = {
                "expired": [item.alert_id for item in expired],
                "stale": [item.alert_id for item in stale],
            }
        else:
            return 2
        print(json.dumps(payload, indent=2, ensure_ascii=False, default=str))
        return 0
    finally:
        service.close()


def _cmd_llm_check() -> int:
    cfg = load_config()
    status = llm_configuration_status(cfg)
    if cfg.llm_mode != "live" or not status["ready_for_live"]:
        print(json.dumps({"status": "not_configured", **status}, indent=2))
        return 2
    try:
        client = OpenAICompatibleClient(
            base_url=cfg.llm_base_url,
            api_key=cfg.llm_api_key,
            model=cfg.llm_model,
            timeout_s=cfg.llm_timeout_s,
            max_retries=cfg.llm_max_retries,
            max_output_tokens=64,
            temperature=0,
        )
        response = client.complete_json(
            "Rispondi esclusivamente con JSON.",
            'Restituisci {"ok": true}.',
            schema_name="health_check",
        )
    except LlmUnavailableError as exc:
        print(json.dumps({"status": "unavailable", "detail": str(exc), **status}, indent=2))
        return 2
    print(
        json.dumps(
            {
                "status": "ok",
                "model": response.model,
                "latency_ms": response.latency_ms,
                "configured_model": cfg.llm_model,
            },
            indent=2,
        )
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="app.cli")
    sub = parser.add_subparsers(dest="command", required=True)

    p_cfg = sub.add_parser("config")
    p_cfg_sub = p_cfg.add_subparsers(dest="action", required=True)
    p_cfg_sub.add_parser("validate")

    p_ing = sub.add_parser("ingest")
    p_ing.add_argument("--connector", type=str, default="rss")
    p_ing.add_argument("--all", action="store_true")
    p_ing.add_argument("--fallback", action="store_true")
    p_ing.add_argument("--status", action="store_true")
    p_ing.add_argument("--legacy", action="store_true", help="usa i connettori legacy")
    p_ing.add_argument("--force", action="store_true")
    p_ing.add_argument("--source", type=str, default=None)
    p_ing.add_argument("--verify", action="store_true")

    p_ingestion = sub.add_parser("ingestion")
    p_ingestion_sub = p_ingestion.add_subparsers(dest="action", required=True)
    p_run = p_ingestion_sub.add_parser("run")
    p_run.add_argument("--once", action="store_true")
    p_run.add_argument("--force", action="store_true")
    p_run.add_argument("--source", type=str, default=None)
    p_run.add_argument("--interval", type=float, default=None)
    p_run.add_argument("--verify", action="store_true")
    p_ingestion_sub.add_parser("status")
    p_ingestion_sub.add_parser("sources")
    p_docs = p_ingestion_sub.add_parser("documents")
    p_docs.add_argument("--status", type=str, default=None)
    p_docs.add_argument("--source", type=str, default=None)
    p_docs.add_argument("--limit", type=int, default=100)
    p_fetches = p_ingestion_sub.add_parser("fetches")
    p_fetches.add_argument("--source", type=str, default=None)
    p_fetches.add_argument("--limit", type=int, default=100)

    p_dis = sub.add_parser("disruptions")
    p_dis_sub = p_dis.add_subparsers(dest="action", required=True)
    p_dis_list = p_dis_sub.add_parser("list")
    p_dis_list.add_argument("--include-simulated", action="store_true")
    p_dis_list.add_argument("--window-hours", type=int, default=168)
    p_dis_list.add_argument("--limit", type=int, default=100)
    p_dis_get = p_dis_sub.add_parser("get")
    p_dis_get.add_argument("source_id")
    p_dis_get.add_argument("alert_id")
    p_dis_sub.add_parser("expire")

    p_llm = sub.add_parser("llm")
    p_llm_sub = p_llm.add_subparsers(dest="action", required=True)
    p_llm_sub.add_parser("check")

    p_db = sub.add_parser("db")
    p_db.add_argument("action", choices=["migrate", "seed", "reset"])

    p_demo = sub.add_parser("demo")
    p_demo.add_argument("--scenario", type=str, default="bagnoli")
    p_demo.add_argument("--profile", type=str, default=None)
    p_demo.add_argument("--report", action="store_true")

    args = parser.parse_args(argv)
    if args.command == "config" and args.action == "validate":
        return _cmd_config_validate()
    if args.command == "ingest":
        return _cmd_ingest(args)
    if args.command == "ingestion":
        return _cmd_ingestion(args)
    if args.command == "disruptions":
        return _cmd_disruptions(args)
    if args.command == "llm" and args.action == "check":
        return _cmd_llm_check()
    if args.command == "db":
        return _cmd_db(args)
    if args.command == "demo":
        return _cmd_demo(args)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
