/**
 * @purpose Tipizzazione eventi SSE e negoziazione percorsi
 * @contracts TraceEvent, RouteProposedData, RouteInvalidatedData, NegotiationFinishedData
 * @tokens shared
 * @verified 2026-11-15
 */

export type TraceEventType =
  | "start"
  | "phase"
  | "rule_evaluated"
  | "conflict_detected"
  | "priority_applied"
  | "plan_item_created"
  | "route_proposed"
  | "route_invalidated"
  | "negotiation_finished"
  | "worker_delegated"
  | "worker_outcome"
  | "decision";

export interface TraceEvent {
  seq: number;
  event_type: TraceEventType;
  data: Record<string, unknown>;
  agent?: string;
  finding_ref?: string;
  rule_applied?: string;
  outcome?: string;
}

export interface RouteLeg {
  mode: string;
  line_id?: string;
  from_stop: string;
  to_stop: string;
  duration_min?: number;
}

export interface RouteProposedData {
  proposal_id: string;
  legs: RouteLeg[];
}

export interface RouteInvalidatedData {
  proposal_id: string;
  reason: string;
  constraints?: Array<{
    kind: "closure" | "penalty";
    applies_at: "engine" | "post_filter";
    description: string;
  }>;
}

export interface NegotiationFinishedData {
  iterations: number;
  agreement: boolean;
  outcome: "agreement" | "exhausted" | "uncertain" | "timeout";
}

export function isRouteProposed(data: Record<string, unknown>): data is RouteProposedData & Record<string, unknown> {
  return typeof data.proposal_id === "string" && Array.isArray(data.legs);
}

export function isRouteInvalidated(
  data: Record<string, unknown>,
): data is RouteInvalidatedData & Record<string, unknown> {
  return typeof data.proposal_id === "string" && typeof data.reason === "string";
}

export function isNegotiationFinished(
  data: Record<string, unknown>,
): data is NegotiationFinishedData & Record<string, unknown> {
  return typeof data.iterations === "number" && typeof data.agreement === "boolean";
}
