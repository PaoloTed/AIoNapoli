/**
 * Frozen backend contracts mirrored 1:1 in TypeScript without `any`.
 * Strictly aligned with hackaton2026CDS/shared/schemas/ and backend domain models.
 */

export const EXPECTED_CONTRACT_VERSION = "1.0.0";

export type AgentName = "mobility" | "crowding" | "context";
export type Severity = "low" | "medium" | "high" | "critical";
export type FindingType =
  | "route_disruption"
  | "route_alternative"
  | "density_alert"
  | "impact_assessment";

export type PlanTarget = "operator" | "tourist" | "citizen";

export type RuleId =
  | "R1_line2_crowding"
  | "R2_conflict_route_vs_density"
  | "R3_weather_capacity"
  | "R4_event_surge";

export type DeclaredRuleConstant =
  | RuleId
  | "P1"
  | "P2"
  | "P3"
  | "NONE"
  | "NO_CONFLICT"
  | "MONITORING"
  | "PLAN_SYNTHESIS"
  | "INITIAL_INGESTION";

export type RefusalCode =
  | "missing_gtfs"
  | "unmapped_point"
  | "out_of_horizon"
  | "missing_realtime"
  | "missing_occupancy"
  | "missing_geofence"
  | "invalid_density"
  | "missing_alert_level"
  | "missing_time_window"
  | "unsourced_alert"
  | "cannot_validate"
  | "unresolved_location";

export type FindingContent = {
  zone_id?: string;
  line_id?: string;
  congestion?: number;
  density?: number;
  expected_attendance?: number;
  heavy_rain?: boolean;
  alert_level?: "verde" | "gialla" | "arancione" | "rossa" | string;
  origin?: string;
  destination?: string;
  estimated_time_min?: number;
  note?: string;
  [key: string]: unknown;
};

export type Finding = {
  agent: AgentName;
  type: FindingType;
  content: FindingContent;
  confidence: number;
  severity: Severity;
  source_id: string;
  data_reference: string;
  is_simulated: boolean;
  timestamp: string;
};

export type Trigger = {
  rule_id: RuleId;
  agents_involved: AgentName[];
};

export type Conflict = {
  detected: boolean;
  description: string;
};

export type PlanItem = {
  priority: number;
  action: string;
  target: PlanTarget;
  rationale: string;
};

export type ReasoningStep = {
  step: number;
  agent: string;
  finding_ref: string;
  rule_applied: DeclaredRuleConstant | string;
  outcome: string;
};

export type Decision = {
  trigger: Trigger;
  conflict: Conflict;
  plan: PlanItem[];
  reasoning_log: ReasoningStep[];
  confidence: number;
  timestamp: string;
};

export type Refusal = {
  agent: AgentName;
  reason_code: RefusalCode | string;
  missing_input: string[];
  detail: string;
};

export type Contribution = {
  feature: string;
  value: number;
  weight: number;
  contribution: number;
};

export type ScoredItem = {
  plan_index: number;
  score: number;
  contributions: Contribution[];
};

export type TargetRelevance = {
  order: number[];
  items: ScoredItem[];
};

export type RelevanceScore = {
  rounding: number;
  targets: Record<PlanTarget, TargetRelevance>;
};

export type NarrativeTexts = {
  it: string;
  en?: string | undefined;
};

export type NarrativeItem = {
  plan_index: number;
  texts: NarrativeTexts;
};

export type Narrative = {
  mode: "replay" | "live" | "off";
  items: NarrativeItem[];
};

export type VehiclePosition = {
  vehicle_id: string;
  route_id?: string | null | undefined;
  trip_id?: string | null | undefined;
  latitude: number;
  longitude: number;
  bearing?: number | null | undefined;
  speed_mps?: number | null | undefined;
  zone_id?: string | null | undefined;
  observed_at: string;
  source_id: string;
  is_simulated: boolean;
};

export type FindingResponse = {
  contract_version: string;
  finding: Finding;
  finding_ref: string;
};

export type DecisionRequest =
  | { scenario_id: string; findings?: never }
  | { findings: Finding[]; scenario_id?: never };

export type DecisionResponse = {
  contract_version: string;
  decision_id: string;
  decision: Decision;
  relevance: RelevanceScore;
  narrative: Narrative;
};

export type ScenarioResponse = {
  contract_version: string;
  scenario_id: string;
  title: string;
  findings: Finding[];
  vehicle_positions: VehiclePosition[];
};

/**
 * ProblemDetail (RFC 9457) format returned on HTTP errors
 */
export type ProblemDetail = {
  type: string;
  title: string;
  status: number;
  code: string;
  field?: string | undefined;
  detail: string;
  instance: string;
  refusal?: Refusal | undefined;
};

/**
 * Alias for RFC 9457 ProblemDetail maintaining backward compatibility
 */
export type Problem = ProblemDetail;

// Route Request Types (Domain models matching backend app.domain.models.trip_request)
export type TripLocationKind = "zone" | "stop" | "poi" | "address" | "coordinate";
export type ResolvedBy = "dictionary" | "nominatim" | "user";

export type TripLocation = {
  label: string;
  lat: number;
  lon: number;
  kind: TripLocationKind;
  resolved_by: ResolvedBy;
};

export type TripRequest = {
  origin: TripLocation;
  destination: TripLocation;
  when: string;
  constraints: Record<string, unknown>;
};

export type UnresolvedLocation = {
  field?: string | undefined;
  raw_text?: string | undefined;
  reason?: string | undefined;
};

export type RouteRequestIn = {
  text: string;
};

export type RouteRequestOut = {
  trip_request: TripRequest | null;
  unresolved: UnresolvedLocation[];
  parser_mode: string;
  needs_clarification: boolean;
  question: string | null;
};
