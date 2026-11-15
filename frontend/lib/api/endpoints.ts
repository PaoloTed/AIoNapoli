/**
 * @purpose Endpoints tipizzati verso il backend FastAPI (percorsi reali verificati)
 * @contracts ScenarioSnapshot, DecisionResponse, FindingResponse, DecisionRequest
 * @tokens shared
 * @verified 2026-11-15
 */

import { apiFetch, getApiBaseUrl } from "./client";
import type {
  DecisionResponse,
  Finding,
  FindingResponse,
  ScenarioSnapshot,
} from "../types/contracts";

export function getScenario(id: string): Promise<ScenarioSnapshot> {
  return apiFetch<ScenarioSnapshot>(`/api/v1/scenario/${encodeURIComponent(id)}`);
}

export type DecisionRequest = { scenario_id: string } | { findings: Finding[] };

export function postDecision(input: DecisionRequest): Promise<DecisionResponse> {
  return apiFetch<DecisionResponse>("/api/v1/decision", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
}

export function postFinding(agent: Finding["agent"], finding: Finding): Promise<FindingResponse> {
  return apiFetch<FindingResponse>(`/api/v1/finding/${agent}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(finding),
  });
}

export function getScenarioStreamUrl(id: string): string {
  return `${getApiBaseUrl()}/api/v1/scenario/${encodeURIComponent(id)}/stream`;
}
