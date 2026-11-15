import {
  EXPECTED_CONTRACT_VERSION,
  compatDecisionResponseSchema,
  compatScenarioResponseSchema,
  decisionResponseSchema,
  problemSchema,
  scenarioResponseSchema,
  type AgentName,
  type DecisionRequest,
  type DecisionResponse,
  type FindingResponse,
  type ProblemDetail,
  type RouteRequestOut,
  type ScenarioResponse,
} from "./contracts";
import { getDict, type Locale } from "./i18n";

export const REQUEST_TIMEOUT_MS = 5000;

export function getApiBaseUrl(): string {
  const base = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";
  return base.replace(/\/+$/, "");
}

/**
 * Strongly typed ApiError carrying RFC 9457 ProblemDetail
 */
export class ApiError extends Error {
  readonly problem: ProblemDetail;

  constructor(problem: ProblemDetail) {
    super(problem.detail || problem.title || "API Error");
    this.name = "ApiError";
    this.problem = problem;
  }
}

/**
 * Network / Timeout error, extending ApiError for unified handling
 */
export class NetworkError extends ApiError {
  readonly kind: "timeout" | "network";

  constructor(kind: "timeout" | "network", message: string) {
    super({
      type: "about:blank",
      title: kind === "timeout" ? "Timeout" : "Network Error",
      status: kind === "timeout" ? 504 : 503,
      code: kind === "timeout" ? "upstream_timeout" : "upstream_unavailable",
      detail: message,
      instance: "",
    });
    this.name = "NetworkError";
    this.kind = kind;
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

/**
 * Sanitizes raw error responses to guarantee no raw stack traces or internal secrets leak
 */
function sanitizeProblem(status: number, path: string, rawBody: unknown): ProblemDetail {
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

/**
 * Low-level typed HTTP client.
 * Invariant: All fetch() calls in the frontend MUST live in lib/api.ts (FE-REQ-32).
 */
export async function apiFetch<T>(
  path: string,
  options?: RequestInit,
  signal?: AbortSignal,
): Promise<T> {
  const baseUrl = getApiBaseUrl();
  const url = path.startsWith("http://") || path.startsWith("https://") ? path : `${baseUrl}${path}`;

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort("timeout"), REQUEST_TIMEOUT_MS);

  const onExternalAbort = () => controller.abort(signal?.reason);
  if (signal) {
    if (signal.aborted) {
      clearTimeout(timeoutId);
      throw new NetworkError("network", "Richiesta annullata");
    }
    signal.addEventListener("abort", onExternalAbort, { once: true });
  }

  let res: Response;
  try {
    res = await fetch(url, {
      ...options,
      cache: "no-store",
      signal: controller.signal,
      headers: {
        "Content-Type": "application/json",
        ...(options?.headers ?? {}),
      },
    });
  } catch (err) {
    clearTimeout(timeoutId);
    if (signal) {
      signal.removeEventListener("abort", onExternalAbort);
    }
    const isAbort =
      err instanceof Error && (err.name === "AbortError" || controller.signal.aborted);
    throw new NetworkError(
      isAbort ? "timeout" : "network",
      isAbort ? "Timeout richiesta verso il backend" : "Backend non raggiungibile",
    );
  }

  clearTimeout(timeoutId);
  if (signal) {
    signal.removeEventListener("abort", onExternalAbort);
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

  return body as T;
}

/**
 * Internal helper for envelope validation
 */
async function requestJson(
  path: string,
  init?: RequestInit,
  externalSignal?: AbortSignal,
): Promise<unknown> {
  return apiFetch<unknown>(path, init, externalSignal);
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

/**
 * Fetch a scenario snapshot from the backend
 */
export async function getScenario(
  scenarioId: string,
  signal?: AbortSignal,
): Promise<CheckedEnvelope<ScenarioResponse>> {
  const path = `/api/v1/scenario/${encodeURIComponent(scenarioId)}`;
  const raw = await requestJson(path, { method: "GET" }, signal);
  return parseEnvelope<ScenarioResponse>(raw, scenarioResponseSchema, compatScenarioResponseSchema);
}

/**
 * POST /api/v1/decision never retries automatically
 */
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

/**
 * POST /api/v1/route-request parses natural language route inquiries
 */
export async function postRouteRequest(
  text: string,
  signal?: AbortSignal,
): Promise<RouteRequestOut> {
  return apiFetch<RouteRequestOut>(
    "/api/v1/route-request",
    {
      method: "POST",
      body: JSON.stringify({ text }),
    },
    signal,
  );
}

/**
 * Alias for route request API
 */
export async function fetchRouteRequestApi(
  text: string,
  signal?: AbortSignal,
): Promise<RouteRequestOut> {
  return postRouteRequest(text, signal);
}

/**
 * Open SSE EventSource stream for a given scenario
 */
export function openStream(scenarioId: string): EventSource {
  return new EventSource(getScenarioStreamUrl(scenarioId));
}

export function getScenarioStreamUrl(scenarioId: string): string {
  return `${getApiBaseUrl()}/api/v1/scenario/${encodeURIComponent(scenarioId)}/stream`;
}

/**
 * Determinism check comparing 2 consecutive decisions for the same scenario
 */
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

/**
 * Graceful mock fallback mechanism.
 * When NEXT_PUBLIC_USE_MOCKS is true or backend is unreachable, falls back to local fixtures.
 */
export type MockFallbackOptions = {
  forceMock?: boolean;
  onFallback?: (reason: string) => void;
};

export async function withMockFallback<T>(
  apiFn: () => Promise<T>,
  mockFallbackFn: () => T | Promise<T>,
  options?: MockFallbackOptions,
): Promise<{ data: T; isMock: boolean }> {
  const envMock = process.env.NEXT_PUBLIC_USE_MOCKS === "true";
  if (options?.forceMock || envMock) {
    const data = await mockFallbackFn();
    return { data, isMock: true };
  }

  try {
    const data = await apiFn();
    return { data, isMock: false };
  } catch (err) {
    const reason = err instanceof Error ? err.message : "Backend unavailable";
    if (options?.onFallback) {
      options.onFallback(reason);
    }
    const data = await mockFallbackFn();
    return { data, isMock: true };
  }
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
  problem: ProblemDetail,
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
): error is ApiError & { problem: ProblemDetail & { refusal: NonNullable<ProblemDetail["refusal"]> } } {
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
