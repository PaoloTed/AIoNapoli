"""Service facade insulating API and CLI from repository and database drivers."""

from __future__ import annotations

import json
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from shared.schemas.api import (
    CONTRACT_VERSION,
    DecisionResponse,
    FindingResponse,
    ScenarioResponse,
    VehiclePosition,
)
from shared.schemas.journeys import (
    JourneyPlanRequest,
    JourneyPlanResponse,
    JourneyPromptRequest,
    JourneyPromptResponse,
)

from app.db.migrations import apply_migrations
from app.db.session import get_connection
from app.domain.models.config import AppConfig
from app.domain.models.finding import AgentName, Finding
from app.domain.models.trace import Trace
from app.repositories.audit import AuditStore, InMemoryAuditStore, PostgresAuditStore
from app.repositories.base import SourceRepository
from app.repositories.disruptions import DisruptionRepository
from app.repositories.memory import InMemorySourceRepository
from app.repositories.postgres import PostgresSourceRepository
from app.repositories.territory import OSMTerritoryRepository
from app.services.ingestion.repository import IngestionRepository
from app.services.input.agent import InputAgent
from app.services.input.geocoder import PlaceResolver
from app.services.journeys import JourneyPlanner
from app.services.orchestrator.config import load_config
from app.services.orchestrator.pipeline import run_pipeline
from app.services.validation.finding_validator import (
    ValidationProblem,
    validate_decision_findings,
    validate_submitted_finding,
)
from app.utils.clock import Clock, SystemClock
from app.utils.logging import log_event


def _load_scenario_fixtures() -> dict[str, dict[str, Any]]:
    repo_root = Path(__file__).resolve().parents[3]
    fixture_path = repo_root / "shared" / "mocks" / "scenarios.json"
    if not fixture_path.exists():
        return {}
    raw = json.loads(fixture_path.read_text(encoding="utf-8"))
    return dict(raw.get("scenarios") or {})


def build_stores_for_profile(
    config: AppConfig,
) -> tuple[SourceRepository, AuditStore, Any | None]:
    """Instantiate repository and audit store according to APP_PROFILE."""
    if config.app_profile == "memory":
        return InMemorySourceRepository(load_fixtures=True), InMemoryAuditStore(), None

    conn = get_connection(
        config.app_profile,
        sqlite_path=config.sqlite_path,
        database_url=config.database_url,
    )
    apply_migrations(conn)
    gtfs_schema = config.gtfs_schema if config.app_profile == "postgres" else None
    gtfs_datasets = config.gtfs_dataset_pairs() if config.app_profile == "postgres" else None
    return (
        PostgresSourceRepository(
            conn,
            gtfs_schema=gtfs_schema or None,
            gtfs_dataset_key=config.gtfs_dataset_key,
            gtfs_datasets=gtfs_datasets,
        ),
        PostgresAuditStore(conn),
        conn,
    )


class BackendService:
    """Application service facade used by HTTP API and CLI."""

    def __init__(
        self,
        *,
        config: AppConfig | None = None,
        repository: SourceRepository | None = None,
        audit_store: AuditStore | None = None,
        clock: Clock | None = None,
        journey_planner: JourneyPlanner | None = None,
    ) -> None:
        self.config = config or load_config()
        self.clock = clock or SystemClock()
        self._db_lock = threading.RLock()
        self.territory_repository: OSMTerritoryRepository | None = None
        self.disruption_repository: DisruptionRepository | None = None
        self.place_resolver: PlaceResolver | None = None
        self.input_agent: InputAgent | None = None
        if repository is not None and audit_store is not None:
            self.repository: SourceRepository = repository
            self.audit_store: AuditStore = audit_store
            self._db_conn: Any | None = None
        else:
            repo, audit, conn = build_stores_for_profile(self.config)
            self.repository = repo
            self.audit_store = audit
            self._db_conn = conn
            if conn is not None and self.config.app_profile == "postgres":
                self.territory_repository = OSMTerritoryRepository(
                    conn,
                    schema=self.config.osm_schema,
                    dataset_key=self.config.osm_dataset_key,
                )
                self.disruption_repository = DisruptionRepository(
                    conn,
                    gtfs_schema=self.config.gtfs_schema,
                    gtfs_dataset_key=self.config.gtfs_dataset_key,
                    osm_dataset_key=self.config.osm_dataset_key,
                )
        self.journey_planner = journey_planner or JourneyPlanner(
            self.config,
            disruption_repository=self.disruption_repository,
            territory_repository=self.territory_repository,
            source_repository=self.repository,
        )
        if self._db_conn is not None and self.config.app_profile == "postgres":
            self.place_resolver = PlaceResolver(self._db_conn, self.config)
            self.input_agent = InputAgent(self.config, self.place_resolver, self.journey_planner)
        self._scenarios = _load_scenario_fixtures()

    def close(self) -> None:
        if self._db_conn is not None:
            try:
                self._db_conn.close()
            except Exception:
                pass

    def submit_finding(
        self,
        path_agent: AgentName,
        payload: dict[str, Any],
    ) -> FindingResponse:
        finding, finding_ref = validate_submitted_finding(path_agent, payload)
        self.audit_store.save_finding(finding, finding_ref)
        log_event(
            "api.findings",
            "finding_accepted",
            level=self.config.log_level,
            finding_ref=finding_ref,
        )
        return FindingResponse(
            contract_version=CONTRACT_VERSION,
            finding=finding,
            finding_ref=finding_ref,
        )

    def plan_journey(self, request: JourneyPlanRequest) -> JourneyPlanResponse:
        """Plan one coordinate-based journey through the configured OTP graph."""
        with self._db_lock:
            return self.journey_planner.plan(request)

    def plan_journey_prompt(self, request: JourneyPromptRequest) -> JourneyPromptResponse:
        """Interpret a natural prompt and run the same orchestration."""
        if self.input_agent is None:
            raise ValidationProblem(
                status=503,
                code="input_agent_unavailable",
                title="Agente Input non disponibile",
                detail="il profilo postgres con catalogo GTFS/OSM e' richiesto",
            )
        with self._db_lock:
            return self.input_agent.interpret(request)

    def list_disruptions(
        self,
        *,
        include_simulated: bool = False,
        window_hours: int = 168,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        if self.disruption_repository is None:
            raise ValidationProblem(
                status=503,
                code="disruptions_unavailable",
                title="Perturbazioni non disponibili",
                detail="il profilo postgres e' richiesto",
            )
        now = datetime.now(timezone.utc)
        with self._db_lock:
            records = self.disruption_repository.list_relevant(
                now - timedelta(hours=1),
                now + timedelta(hours=max(1, window_hours)),
                include_simulated=include_simulated,
            )
        return [record.model_dump(mode="json") for record in records[: max(1, limit)]]

    def get_disruption(self, source_id: str, alert_id: str) -> dict[str, Any]:
        if self.disruption_repository is None:
            raise ValidationProblem(
                status=503,
                code="disruptions_unavailable",
                title="Perturbazioni non disponibili",
                detail="il profilo postgres e' richiesto",
            )
        with self._db_lock:
            record = self.disruption_repository.get(source_id, alert_id)
        if record is None:
            raise ValidationProblem(
                status=404,
                code="disruption_not_found",
                title="Perturbazione non trovata",
                detail=f"{source_id}/{alert_id}",
            )
        return record.model_dump(mode="json")

    def _ingestion_repo(self) -> IngestionRepository:
        if self._db_conn is None:
            raise ValidationProblem(
                status=503,
                code="ingestion_unavailable",
                title="Acquisizione non disponibile",
                detail="il profilo postgres e' richiesto",
            )
        return IngestionRepository(self._db_conn)

    def ingestion_sources(self) -> list[dict[str, Any]]:
        with self._db_lock:
            return self._ingestion_repo().list_sources()

    def ingestion_documents(
        self,
        *,
        status: str | None = None,
        source_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        with self._db_lock:
            return self._ingestion_repo().list_documents(
                status=status, source_id=source_id, limit=limit
            )

    def ingestion_status(self) -> dict[str, Any]:
        with self._db_lock:
            return self._ingestion_repo().status_summary()

    def ingestion_fetches(
        self, *, source_id: str | None = None, limit: int = 100
    ) -> list[dict[str, Any]]:
        with self._db_lock:
            return self._ingestion_repo().fetches(source_id=source_id, limit=limit)

    def get_scenario_data(self, scenario_id: str) -> ScenarioResponse:
        raw = self._scenarios.get(scenario_id)
        if raw is None:
            raise ValidationProblem(
                status=404,
                code="scenario_not_found",
                title="Scenario non trovato",
                field="scenario_id",
                detail=f"scenario '{scenario_id}' sconosciuto",
            )
        findings = [Finding.model_validate(f) for f in raw.get("findings", [])]
        positions = [VehiclePosition.model_validate(v) for v in raw.get("vehicle_positions", [])]
        return ScenarioResponse(
            contract_version=CONTRACT_VERSION,
            scenario_id=scenario_id,
            title=str(raw.get("title") or scenario_id),
            findings=findings,
            vehicle_positions=positions,
        )

    def decide_from_request(self, payload: dict[str, Any]) -> tuple[DecisionResponse, Trace]:
        if not isinstance(payload, dict):
            raise ValidationProblem(
                status=422,
                code="invalid_finding",
                title="Richiesta non valida",
                field="request",
                detail="il corpo della richiesta deve essere un oggetto JSON",
            )

        has_scenario = "scenario_id" in payload and payload["scenario_id"] is not None
        has_findings = "findings" in payload and payload["findings"] is not None

        if has_scenario and has_findings:
            raise ValidationProblem(
                status=422,
                code="invalid_finding",
                title="Richiesta ambigua",
                field="request",
                detail="scenario_id e findings sono mutuamente esclusivi",
            )
        if not has_scenario and not has_findings:
            if "findings" in payload and payload["findings"] == []:
                raise ValidationProblem(
                    status=422,
                    code="missing_finding",
                    title="Finding mancanti",
                    field="findings",
                    detail="nessun finding disponibile e nessuno scenario specificato",
                )
            raise ValidationProblem(
                status=422,
                code="missing_finding",
                title="Richiesta incompleta",
                field="request",
                detail="specificare scenario_id oppure findings",
            )

        if has_scenario:
            scenario_id = str(payload["scenario_id"]).strip()
            if not scenario_id:
                raise ValidationProblem(
                    status=422,
                    code="invalid_finding",
                    title="Scenario non valido",
                    field="scenario_id",
                    detail="scenario_id non puo' essere vuoto",
                )
            scenario = self.get_scenario_data(scenario_id)
            findings = scenario.findings
            if not findings:
                raise ValidationProblem(
                    status=422,
                    code="missing_finding",
                    title="Finding mancanti",
                    field="findings",
                    detail=f"nessun finding disponibile nello scenario '{scenario_id}'",
                )
        else:
            raw_findings = payload.get("findings")
            if not isinstance(raw_findings, list):
                raise ValidationProblem(
                    status=422,
                    code="invalid_finding",
                    title="Richiesta non valida",
                    field="findings",
                    detail="findings deve essere una lista",
                )
            findings = validate_decision_findings(raw_findings)

        output = run_pipeline(findings=findings, config=self.config, clock=self.clock)
        self.audit_store.save_decision(output.decision, output.decision_id)
        log_event(
            "orchestrator.pipeline",
            "decision_produced",
            level=self.config.log_level,
            decision_id=output.decision_id,
        )
        resp = DecisionResponse(
            contract_version=CONTRACT_VERSION,
            decision_id=output.decision_id,
            decision=output.decision,
            relevance=output.relevance,
            narrative=output.narrative,
        )
        return resp, output.trace

    def build_sse_events(self, scenario_id: str) -> list[dict[str, Any]]:
        """Execute scenario pipeline and project the Trace into ordered SSE frames."""
        resp, trace = self.decide_from_request({"scenario_id": scenario_id})
        frames: list[dict[str, Any]] = [
            {
                "event": "start",
                "id": "1",
                "retry": 3000,
                "data": json.dumps(
                    {"scenario_id": scenario_id, "contract_version": CONTRACT_VERSION},
                    separators=(",", ":"),
                    ensure_ascii=False,
                ),
            }
        ]
        seq = 2
        for ev in trace.events:
            frames.append(
                {
                    "event": ev.event_type,
                    "id": str(seq),
                    "data": json.dumps(ev.data, separators=(",", ":"), ensure_ascii=False),
                }
            )
            seq += 1

        frames.append(
            {
                "event": "decision",
                "id": str(seq),
                "data": json.dumps(
                    {
                        "decision_id": resp.decision_id,
                        "contract_version": CONTRACT_VERSION,
                    },
                    separators=(",", ":"),
                    ensure_ascii=False,
                ),
            }
        )
        return frames
