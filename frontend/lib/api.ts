import {
  EXPECTED_CONTRACT_VERSION,
  compatDecisionResponseSchema,
  compatScenarioResponseSchema,
  decisionResponseSchema,
  problemSchema,
  scenarioResponseSchema,
  type AgentName,
  type DecisionResponse,
  type Finding,
  type FindingResponse,
  type Problem,
  type ScenarioResponse,
} from "./contracts";
import { getDict, type Locale } from "./i18n";

export const REQUEST_TIMEOUT_MS = 5000;

export function getApiBaseUrl(): string {
  const base = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";
  return base.replace(/\/+$/, "");
}

export class ApiError extends Error {
  constructor(readonly problem: Problem) {
    super(problem.detail);
    this.name = "ApiError";
  }
}

export class NetworkError extends Error {
  constructor(
    readonly kind: "timeout" | "network",
    message: string,
  ) {
    super(message);
    this.name = "NetworkError";
  }
}

export class ContractValidationError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ContractValidationError";
  }
}

export type CheckedEnvelope<T> = {
  data: T;
  contractVersion: string;
  contractMismatch: boolean;
};

function sanitizeProblem(status: number, path: string, rawBody: unknown): Problem {
  const parsed = problemSchema.safeParse(rawBody);
  if (parsed.success) {
    return {
      type: parsed.data.type,
      title: parsed.data.title,
      status: parsed.data.status,
      code: parsed.data.code,
      detail:
        parsed.data.code === "internal_error" ? "Errore interno del servizio" : parsed.data.detail,
      instance: parsed.data.instance,
      ...(parsed.data.field !== undefined ? { field: parsed.data.field } : {}),
      ...(parsed.data.refusal !== undefined ? { refusal: parsed.data.refusal } : {}),
    };
  }
  return {
    type: "about:blank",
    title: "Errore interno",
    status,
    code: "internal_error",
    detail: "Errore interno del servizio",
    instance: path,
  };
}

async function requestJson(
  path: string,
  init?: RequestInit,
  externalSignal?: AbortSignal,
): Promise<unknown> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort("timeout"), REQUEST_TIMEOUT_MS);

  const onExternalAbort = () => controller.abort(externalSignal?.reason);
  if (externalSignal) {
    if (externalSignal.aborted) {
      clearTimeout(timeoutId);
      throw new NetworkError("network", "Richiesta annullata");
    }
    externalSignal.addEventListener("abort", onExternalAbort, { once: true });
  }

  let res: Response;
  try {
    res = await fetch(`${getApiBaseUrl()}${path}`, {
      ...init,
      cache: "no-store",
      signal: controller.signal,
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers ?? {}),
      },
    });
  } catch (err) {
    clearTimeout(timeoutId);
    if (externalSignal) {
      externalSignal.removeEventListener("abort", onExternalAbort);
    }
    const isAbort =
      err instanceof Error && (err.name === "AbortError" || controller.signal.aborted);
    throw new NetworkError(
      isAbort ? "timeout" : "network",
      isAbort ? "Timeout richiesta verso il backend" : "Backend non raggiungibile",
    );
  }

  clearTimeout(timeoutId);
  if (externalSignal) {
    externalSignal.removeEventListener("abort", onExternalAbort);
  }

  let body: unknown;
  try {
    body = await res.json();
  } catch {
    throw new ApiError(sanitizeProblem(res.status, path, null));
  }

  if (!res.ok) {
    throw new ApiError(sanitizeProblem(res.status, path, body));
  }

  return body;
}

function parseEnvelope<T>(
  rawBody: unknown,
  strictSchema: { parse: (v: unknown) => T },
  compatSchema: { parse: (v: unknown) => T },
): CheckedEnvelope<T> {
  if (
    typeof rawBody !== "object" ||
    rawBody === null ||
    typeof (rawBody as { contract_version?: unknown }).contract_version !== "string"
  ) {
    throw new ContractValidationError("Missing contract_version in backend response");
  }

  const version = (rawBody as { contract_version: string }).contract_version;
  const mismatch = version !== EXPECTED_CONTRACT_VERSION;

  try {
    const data = mismatch ? compatSchema.parse(rawBody) : strictSchema.parse(rawBody);
    return {
      data,
      contractVersion: version,
      contractMismatch: mismatch,
    };
  } catch (err) {
    throw new ContractValidationError(
      err instanceof Error ? err.message : "Invalid contract payload",
    );
  }
}

export async function getScenario(
  scenarioId: string,
  signal?: AbortSignal,
): Promise<CheckedEnvelope<ScenarioResponse>> {
  const path = `/api/v1/scenario/${encodeURIComponent(scenarioId)}`;
  const raw = await requestJson(path, { method: "GET" }, signal);
  return parseEnvelope<ScenarioResponse>(raw, scenarioResponseSchema, compatScenarioResponseSchema);
}

export type DecisionRequest = { scenario_id: string } | { findings: Finding[] };

// POST /decision never retries automatically (API-CLIENT.md §2)
export async function postDecision(
  payload: DecisionRequest,
  signal?: AbortSignal,
): Promise<CheckedEnvelope<DecisionResponse>> {
  const path = "/api/v1/decision";
  const raw = await requestJson(
    path,
    {
      method: "POST",
      body: JSON.stringify(payload),
    },
    signal,
  );
  return parseEnvelope<DecisionResponse>(raw, decisionResponseSchema, compatDecisionResponseSchema);
}

export type RepeatDecisionResult = {
  first: CheckedEnvelope<DecisionResponse>;
  second: CheckedEnvelope<DecisionResponse>;
  same: boolean;
};

export async function repeatDecisionCheck(scenarioId: string): Promise<RepeatDecisionResult> {
  const first = await postDecision({ scenario_id: scenarioId });
  const second = await postDecision({ scenario_id: scenarioId });
  return {
    first,
    second,
    same: first.data.decision_id === second.data.decision_id,
  };
}

export function getScenarioStreamUrl(scenarioId: string): string {
  return `${getApiBaseUrl()}/api/v1/scenario/${encodeURIComponent(scenarioId)}/stream`;
}

export type ErrorPlacement = "screen" | "banner" | "card" | "decision" | "none";

export type ProblemPresentation = {
  code: string;
  placement: ErrorPlacement;
  stateKind: "empty" | "degraded" | "error" | "partial" | "ok";
  headline: string;
  detail: string;
  canRetry: boolean;
  hidePlan: boolean;
};

export function mapProblemToPresentation(
  problem: Problem,
  locale: Locale = "it",
): ProblemPresentation {
  const d = getDict(locale);
  switch (problem.code) {
    case "invalid_finding":
      return {
        code: problem.code,
        placement: problem.field ? "card" : "banner",
        stateKind: "partial",
        headline: d.states.invalidFinding,
        detail: problem.field
          ? `${d.states.invalidFinding}: ${problem.field}`
          : d.states.invalidFinding,
        canRetry: true,
        hidePlan: false,
      };
    case "agent_mismatch":
      return {
        code: problem.code,
        placement: "card",
        stateKind: "partial",
        headline: d.states.agentMismatch,
        detail: problem.field
          ? `${d.states.agentMismatch} (${problem.field})`
          : d.states.agentMismatch,
        canRetry: true,
        hidePlan: false,
      };
    case "missing_finding":
      return {
        code: problem.code,
        placement: "decision",
        stateKind: "error",
        headline: d.states.missingFinding,
        detail: d.states.missingFinding,
        canRetry: true,
        hidePlan: true,
      };
    case "agent_refusal":
      return {
        code: problem.code,
        placement: "card",
        stateKind: "partial",
        headline: d.states.agentRefusal,
        detail: problem.refusal
          ? `${problem.refusal.reason_code}: ${problem.refusal.detail}`
          : d.states.agentRefusal,
        canRetry: true,
        hidePlan: false,
      };
    case "scenario_not_found":
      return {
        code: problem.code,
        placement: "screen",
        stateKind: "empty",
        headline: d.states.notFoundTitle,
        detail: problem.detail,
        canRetry: false,
        hidePlan: true,
      };
    case "upstream_timeout":
    case "upstream_unavailable":
      return {
        code: problem.code,
        placement: "banner",
        stateKind: "degraded",
        headline: d.states.degradedUpstream,
        detail: d.states.degradedUpstream,
        canRetry: true,
        hidePlan: false,
      };
    case "llm_unavailable":
      return {
        code: problem.code,
        placement: "none",
        stateKind: "ok",
        headline: d.provenance.templateText,
        detail: "",
        canRetry: false,
        hidePlan: false,
      };
    case "config_invalid":
      return {
        code: problem.code,
        placement: "screen",
        stateKind: "error",
        headline: d.states.configInvalid,
        detail: d.states.configInvalid,
        canRetry: false,
        hidePlan: true,
      };
    case "internal_error":
    default:
      return {
        code: problem.code || "internal_error",
        placement: "screen",
        stateKind: "error",
        headline: d.states.internalError,
        detail: d.states.internalError,
        canRetry: true,
        hidePlan: true,
      };
  }
}

export function isAgentRefusalProblem(
  error: unknown,
): error is ApiError & { problem: Problem & { refusal: NonNullable<Problem["refusal"]> } } {
  return (
    error instanceof ApiError &&
    error.problem.code === "agent_refusal" &&
    error.problem.refusal !== undefined
  );
}

export function extractAgentFromField(field?: string): AgentName | undefined {
  if (!field) return undefined;
  if (field.includes("mobility")) return "mobility";
  if (field.includes("crowding")) return "crowding";
  if (field.includes("context")) return "context";
  return undefined;
}

export type { FindingResponse };
