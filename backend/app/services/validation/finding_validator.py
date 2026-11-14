"""Validation helpers for Findings, Refusals, and Decision requests."""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from app.domain.logic.refs import compute_finding_ref
from app.domain.models.finding import AgentName, Finding
from app.domain.models.refusal import Refusal


class ValidationProblem(Exception):
    """Domain/contract validation failure mapped to RFC 9457 Problem+JSON."""

    def __init__(
        self,
        *,
        status: int,
        code: str,
        title: str,
        detail: str,
        field: str | None = None,
        refusal: Refusal | None = None,
    ) -> None:
        self.status = status
        self.code = code
        self.title = title
        self.detail = detail
        self.field = field
        self.refusal = refusal
        super().__init__(detail)


def extract_field_from_pydantic_error(err: dict[str, Any]) -> str:
    """Extract dotted/indexed field path from a Pydantic error dict."""
    loc = list(err.get("loc") or [])
    if loc and loc[0] in ("body", "query", "path"):
        loc = loc[1:]

    msg = str(err.get("msg") or "")
    for prefix in (
        "content.density",
        "content.congestion",
        "content.expected_attendance",
        "content.heavy_rain",
    ):
        if prefix in msg:
            # Replace trailing 'content' with exact sub-field path
            if loc and loc[-1] == "content":
                loc = [*loc[:-1], prefix]
            elif not loc:
                return prefix

    parts: list[str] = []
    for item in loc:
        if isinstance(item, int):
            if parts:
                parts[-1] = f"{parts[-1]}[{item}]"
            else:
                parts.append(f"[{item}]")
        else:
            parts.append(str(item))
    return ".".join(parts) if parts else "request"


def validate_submitted_finding(
    path_agent: AgentName,
    payload: dict[str, Any],
) -> tuple[Finding, str]:
    """Validate incoming Finding (or Refusal) payload for POST /api/v1/finding/{agent}."""
    if not isinstance(payload, dict):
        raise ValidationProblem(
            status=422,
            code="invalid_finding",
            title="Finding non valido",
            field="request",
            detail="il corpo della richiesta deve essere un oggetto JSON",
        )

    # Support explicit Refusal payload as an expected outcome (REQ-API-08)
    if "reason_code" in payload and "missing_input" in payload and "type" not in payload:
        try:
            refusal = Refusal.model_validate(payload)
        except ValidationError as exc:
            first = exc.errors()[0]
            raise ValidationProblem(
                status=422,
                code="invalid_finding",
                title="Rifiuto non conforme",
                field=extract_field_from_pydantic_error(first),
                detail=str(first.get("msg", "rifiuto non valido")),
            ) from exc
        if refusal.agent != path_agent:
            raise ValidationProblem(
                status=422,
                code="agent_mismatch",
                title="Agente non corrispondente",
                field="agent",
                detail=(
                    f"agente nel corpo '{refusal.agent.value}' diverso dal path "
                    f"'{path_agent.value}'"
                ),
            )
        raise ValidationProblem(
            status=422,
            code="agent_refusal",
            title="Agente senza dati sufficienti",
            field=None,
            detail=refusal.detail,
            refusal=refusal,
        )

    # Check agent mismatch before deep validation if agent parses cleanly
    raw_agent = payload.get("agent")
    if isinstance(raw_agent, str) and raw_agent in {a.value for a in AgentName}:
        if raw_agent != path_agent.value:
            raise ValidationProblem(
                status=422,
                code="agent_mismatch",
                title="Agente non corrispondente",
                field="agent",
                detail=f"agente '{raw_agent}' non ammesso sull'endpoint '{path_agent.value}'",
            )

    try:
        finding = Finding.model_validate(payload)
    except ValidationError as exc:
        first = exc.errors()[0]
        field_name = extract_field_from_pydantic_error(first)
        if field_name == "request" and "type" in str(first.get("msg", "")):
            field_name = "type"
        raise ValidationProblem(
            status=422,
            code="invalid_finding",
            title="Finding non valido",
            field=field_name,
            detail=str(first.get("msg", "finding non conforme")),
        ) from exc

    if finding.agent != path_agent:
        raise ValidationProblem(
            status=422,
            code="agent_mismatch",
            title="Agente non corrispondente",
            field="agent",
            detail=f"agente '{finding.agent.value}' diverso dall'endpoint '{path_agent.value}'",
        )

    return finding, compute_finding_ref(finding)


def validate_decision_findings(raw_findings: list[Any]) -> list[Finding]:
    """Validate explicit findings list for POST /api/v1/decision."""
    if not raw_findings:
        raise ValidationProblem(
            status=422,
            code="missing_finding",
            title="Finding mancanti",
            field="findings",
            detail="nessun finding fornito per produrre la decisione",
        )

    validated: list[Finding] = []
    seen_agents: set[AgentName] = set()
    for idx, item in enumerate(raw_findings):
        if not isinstance(item, dict):
            raise ValidationProblem(
                status=422,
                code="invalid_finding",
                title="Finding non valido",
                field=f"findings[{idx}]",
                detail="ogni elemento di findings deve essere un oggetto JSON",
            )
        try:
            finding = Finding.model_validate(item)
        except ValidationError as exc:
            first = exc.errors()[0]
            sub_field = extract_field_from_pydantic_error(first)
            raise ValidationProblem(
                status=422,
                code="invalid_finding",
                title="Finding non valido",
                field=f"findings[{idx}].{sub_field}",
                detail=str(first.get("msg", "finding non conforme")),
            ) from exc

        if finding.agent in seen_agents:
            raise ValidationProblem(
                status=422,
                code="invalid_finding",
                title="Agente duplicato",
                field="findings.agent",
                detail=f"due finding presenti per lo stesso agente '{finding.agent.value}'",
            )
        seen_agents.add(finding.agent)
        validated.append(finding)

    return validated
