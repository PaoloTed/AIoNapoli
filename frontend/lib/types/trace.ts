/**
 * Strictly typed Trace events and negotiation domain models.
 * Aligned 1:1 with backend app.domain.models.trace and app.domain.models.routing.
 */

import type { AgentName, PlanTarget, ProblemDetail } from "./contracts";

export type TraceEventType =
  | "phase"
  | "rule_evaluated"
  | "conflict_detected"
  | "priority_applied"
  | "plan_item_created"
  | "route_proposed"
  | "route_invalidated"
  | "negotiation_finished"
  | "worker_delegated"
  | "worker_outcome";

export type StreamControlEventType = "start" | "decision" | "error";

export type AllStreamEventType = TraceEventType | StreamControlEventType;

export type PhaseData = {
  phase: string;
  index: number;
};

export type RuleEvaluatedData = {
  rule_id: string;
  agents: AgentName[];
  fired: boolean;
  reason: string;
};

export type ConflictDetectedData = {
  description: string;
  zone_id?: string | null | undefined;
};

export type PriorityAppliedData = {
  priority: string;
  winner: string;
};

export type PlanItemCreatedData = {
  target: PlanTarget;
  action_ref: string;
};

export type RouteProposedData = {
  proposal_id: string;
  iteration: number;
  route_ids: string[];
  duration_min: number;
};

export type RouteInvalidatedData = {
  proposal_id: string;
  iteration: number;
  constraint_kinds: string[];
  evidence_refs: string[];
};

export type NegotiationFinishedData = {
  iterations: number;
  exhausted: boolean;
  constraints_applied: string[];
};

export type WorkerDelegatedData = {
  agent: string;
  capabilities: string[];
  can_handle_reason: string;
};

export type WorkerOutcomeData = {
  agent: string;
  contributed: boolean;
  reason: string;
  llm_used: string;
  elapsed_ms: number;
};

export type StreamStartData = {
  scenario_id: string;
  contract_version: string;
};

export type StreamDecisionData = {
  decision_id: string;
  contract_version: string;
};

export type TraceEventDataMap = {
  phase: PhaseData;
  rule_evaluated: RuleEvaluatedData;
  conflict_detected: ConflictDetectedData;
  priority_applied: PriorityAppliedData;
  plan_item_created: PlanItemCreatedData;
  route_proposed: RouteProposedData;
  route_invalidated: RouteInvalidatedData;
  negotiation_finished: NegotiationFinishedData;
  worker_delegated: WorkerDelegatedData;
  worker_outcome: WorkerOutcomeData;
  start: StreamStartData;
  decision: StreamDecisionData;
  error: ProblemDetail;
};

/**
 * Strictly monotonic trace event emitted during pipeline execution.
 * `seq` is guaranteed >= 1 and strictly increasing.
 */
export type TraceEvent<T extends keyof TraceEventDataMap = AllStreamEventType> = {
  seq: number;
  event_type: T;
  data: TraceEventDataMap[T];
  agent?: string | null | undefined;
  finding_ref?: string | null | undefined;
  rule_applied?: string | null | undefined;
  outcome?: string | null | undefined;
};

// Routing & Negotiation domain models
export type RouteMode = "walk" | "bus" | "metro" | "tram" | "funicular" | "rail";

export type RouteLeg = {
  mode: RouteMode;
  route_id?: string | null | undefined;
  from_stop: string;
  to_stop: string;
  departure: string;
  arrival: string;
  duration_min: number;
  zone_ids: string[];
  from_stop_id?: string | null | undefined;
  to_stop_id?: string | null | undefined;
  headsign?: string | null | undefined;
};

export type Waypoint = {
  label: string;
  lat: number;
  lon: number;
  kind: "zone" | "stop" | "poi" | "address" | "coordinate";
  resolved_by: "dictionary" | "nominatim" | "user";
};

export type RouteProposal = {
  proposal_id: string;
  origin: Waypoint;
  destination: Waypoint;
  legs: RouteLeg[];
  total_duration_min: number;
  transfers: number;
  zone_ids: string[];
  route_ids: string[];
  is_simulated: boolean;
  source_id: string;
  data_reference: string;
  exclude_applied: string[];
  penalty_applied: boolean;
};

export type ConstraintTarget = {
  route_id?: string | undefined;
  stop_id?: string | undefined;
  zone_id?: string | undefined;
  from_stop?: string | undefined;
  to_stop?: string | undefined;
};

export type TimeWindow = {
  from_at?: string | null | undefined;
  to_at?: string | null | undefined;
};

export type TravelConstraint = {
  kind: "closure" | "penalty" | "uncertainty";
  target: ConstraintTarget;
  direction?: "inbound" | "outbound" | "both" | null | undefined;
  window: TimeWindow;
  applies_at: "engine" | "post_filter";
  evidence_ref: string;
  source_id: string;
  confidence: number;
};

export type Rejection = {
  proposal_id: string;
  iteration: number;
  constraints: TravelConstraint[];
};

export type NegotiationOutcome = {
  final_proposal: RouteProposal;
  iterations: number;
  rejected: Rejection[];
  exhausted: boolean;
  uncertain: boolean;
  constraints_applied: string[];
};

// SSE stream raw frame representation
export type SSEFrame = {
  id: string;
  event: string;
  data: string;
  retry?: number | undefined;
};
