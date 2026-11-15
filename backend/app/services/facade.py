"""Service facade insulating API and CLI from repository and database drivers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from shared.schemas.api import (
    CONTRACT_VERSION,
    DecisionResponse,
    FindingResponse,
    ScenarioResponse,
    VehiclePosition,
)

from app.db.migrations import apply_migrations
from app.db.session import get_connection
from app.domain.models.config import AppConfig
from app.domain.models.finding import AgentName, Finding
from app.domain.models.trace import Trace
from app.repositories.audit import AuditStore, InMemoryAuditStore, PostgresAuditStore
from app.repositories.base import SourceRepository
from app.repositories.memory import InMemorySourceRepository
from app.repositories.postgres import PostgresSourceRepository
from app.services.orchestrator.config import load_config
from app.services.orchestrator.pipeline import run_pipeline
from app.services.orchestrator.run_supervisor import RunSupervisor
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
    return PostgresSourceRepository(conn), PostgresAuditStore(conn), conn


class BackendService:
    """Application service facade used by HTTP API and CLI."""

    def __init__(
        self,
        *,
        config: AppConfig | None = None,
        repository: SourceRepository | None = None,
        audit_store: AuditStore | None = None,
        clock: Clock | None = None,
    ) -> None:
        self.config = config or load_config()
        self.clock = clock or SystemClock()
        if repository is not None and audit_store is not None:
            self.repository: SourceRepository = repository
            self.audit_store: AuditStore = audit_store
            self._db_conn: Any | None = None
        else:
            repo, audit, conn = build_stores_for_profile(self.config)
            self.repository = repo
            self.audit_store = audit
            self._db_conn = conn
        self._scenarios = _load_scenario_fixtures()
        self.run_supervisor = RunSupervisor(
            self.repository,
            clock=self.clock,
            enable_negotiation=self.config.enable_negotiation,
        )

    def execute_live_agents(
        self,
        zone_id: str = "Z_BAGNOLI",
        trip_request: Any = None,
        trace: Trace | None = None,
    ) -> list[Finding | Any]:
        """Execute all vertical supervisors and negotiation cycle to produce live findings."""
        return self.run_supervisor.execute_agents(
            zone_id=zone_id,
            trip_request=trip_request,
            trace=trace,
        )

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
            if self.config.findings_source == "agents":
                agent_results = self.execute_live_agents(zone_id="Z_BAGNOLI")
                findings = [f for f in agent_results if isinstance(f, Finding)]
                if not findings:
                    scenario = self.get_scenario_data(scenario_id)
                    findings = scenario.findings
            else:
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
