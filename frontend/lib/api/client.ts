/**
 * @purpose Client HTTP tipizzato con supporto RFC 7807 e timeout deterministico
 * @contracts ProblemDetail, ApiError
 * @tokens shared
 * @verified 2026-11-15
 */

import type { ProblemDetail } from "../types/contracts";

export function getApiBaseUrl(): string {
  const base = process.env.NEXT_PUBLIC_API_BASE_URL ?? "";
  return base.replace(/\/+$/, "");
}

export class ApiError extends Error {
  readonly kind: "http" | "timeout" | "aborted" | "network";
  readonly status: number;
  readonly problem: ProblemDetail | null;

  constructor(
    message: string,
    kind: "http" | "timeout" | "aborted" | "network",
    status = 0,
    problem: ProblemDetail | null = null,
  ) {
    super(message);
    this.name = "ApiError";
    this.kind = kind;
    this.status = status;
    this.problem = problem;
  }
}

export function isProblemDetail(value: unknown): value is ProblemDetail {
  if (typeof value !== "object" || value === null) return false;
  const candidate = value as Partial<ProblemDetail>;
  return (
    typeof candidate.type === "string" &&
    typeof candidate.title === "string" &&
    typeof candidate.status === "number" &&
    typeof candidate.code === "string" &&
    typeof candidate.detail === "string" &&
    typeof candidate.instance === "string"
  );
}

function composeSignals(s1: AbortSignal, s2: AbortSignal): AbortSignal {
  const controller = new AbortController();
  const onAbort = () => controller.abort();
  s1.addEventListener("abort", onAbort, { once: true });
  s2.addEventListener("abort", onAbort, { once: true });
  return controller.signal;
}

export async function apiFetch<T>(
  path: string,
  options?: RequestInit & { timeoutMs?: number; signal?: AbortSignal },
): Promise<T> {
  const timeoutMs = options?.timeoutMs ?? 8000;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  const mergedSignal = options?.signal
    ? composeSignals(options.signal, controller.signal)
    : controller.signal;

  try {
    const response = await fetch(`${getApiBaseUrl()}${path}`, {
      ...options,
      cache: "no-store",
      signal: mergedSignal,
      headers: {
        Accept: "application/json, application/problem+json",
        ...options?.headers,
      },
    });

    if (!response.ok) {
      const contentType = response.headers.get("content-type") ?? "";
      let problem: ProblemDetail | null = null;
      if (contentType.includes("application/problem+json") || contentType.includes("application/json")) {
        try {
          const parsed: unknown = await response.json();
          if (isProblemDetail(parsed)) {
            problem = parsed;
          }
        } catch {
          // corpo non parsabile: si mantiene il problema nullo
        }
      }
      throw new ApiError(
        problem?.detail ?? `HTTP ${response.status} ${response.statusText}`,
        "http",
        response.status,
        problem,
      );
    }

    if (response.status === 204) {
      return undefined as T;
    }

    const text = await response.text();
    if (!text) {
      return undefined as T;
    }

    try {
      return JSON.parse(text) as T;
    } catch {
      throw new ApiError("Risposta del server non parsabile come JSON", "http", response.status, null);
    }
  } catch (error: unknown) {
    if (error instanceof ApiError) throw error;
    if (error instanceof DOMException && error.name === "AbortError") {
      if (options?.signal?.aborted) {
        throw new ApiError("Richiesta interrotta dal client", "aborted", 0, null);
      }
      throw new ApiError(`Timeout richiesta superato (${timeoutMs}ms)`, "timeout", 408, null);
    }
    throw new ApiError(error instanceof Error ? error.message : "Errore di rete", "network", 0, null);
  } finally {
    clearTimeout(timer);
  }
}
