/**
 * @purpose Contratti dati congelati 1:1 con il backend FastAPI (Napoli Agentic City)
 * @contracts Finding, Decision, DecisionResponse, Refusal, ProblemDetail, ScenarioSnapshot
 * @tokens shared
 * @verified 2026-11-15
 */

// --- Evidenze Agenti (Finding) ---
export type AgentName = "mobility" | "crowding" | "context";
export type FindingType =
  | "route_disruption"
  | "route_alternative"
  | "density_alert"
  | "impact_assessment";
export type Severity = "low" | "medium" | "high" | "critical";

export interface FindingContent {
  zone_id?: string;
  line_id?: string;
  congestion?: number;
  density?: number;
  expected_attendance?: number;
  heavy_rain?: boolean;
  alert_level?: string;
  origin?: string;
  destination?: string;
  estimated_time_min?: number;
  note?: string;
}

export interface Finding {
  agent: AgentName;
  type: FindingType;
  content: FindingContent;
  confidence: number;
  severity: Severity;
  source_id: string;
  data_reference: string;
  is_simulated: boolean;
  timestamp: string;
}

// --- Decisione Operativa e Piano d'Azione (Decision) ---
export type RuleId =
  | "R1_line2_crowding"
  | "R2_conflict_route_vs_density"
  | "R3_weather_capacity"
  | "R4_event_surge";
export type Target = "operator" | "tourist" | "citizen";

export interface Trigger {
  rule_id: RuleId;
  agents_involved: AgentName[];
}

export interface Conflict {
  detected: boolean;
  description: string;
}

export interface PlanItem {
  priority: number;
  action: string;
  target: Target;
  rationale: string;
}

export interface ReasoningStep {
  step: number;
  agent: string;
  finding_ref: string;
  rule_applied: string;
  outcome: string;
}

export interface Decision {
  trigger: Trigger;
  conflict: Conflict;
  plan: PlanItem[];
  reasoning_log: ReasoningStep[];
  confidence: number;
  timestamp: string;
}

// --- DecisionResponse (Payload Completo con Rilevanza e Narrativa) ---
export interface Contribution {
  feature: string;
  value: number;
  weight: number;
  contribution: number;
}

export interface TargetRelevanceItem {
  plan_index: number;
  score: number;
  contributions: Contribution[];
}

export interface TargetRelevance {
  order: number[];
  items: TargetRelevanceItem[];
}

export interface Relevance {
  rounding: number;
  targets: {
    operator: TargetRelevance;
    tourist: TargetRelevance;
    citizen: TargetRelevance;
  };
}

export interface NarrativeItem {
  plan_index: number;
  texts: {
    it: string;
    en?: string;
  };
}

export interface Narrative {
  mode: "replay" | "live" | "off";
  items: NarrativeItem[];
}

export interface DecisionResponse {
  contract_version: "1.0.0" | string;
  decision_id: string;
  decision: Decision;
  relevance: Relevance;
  narrative: Narrative;
}

// --- Rifiuti Deterministici e Dettagli Errore RFC 7807 (Refusal & ProblemDetail) ---
export type RefusalReasonCode =
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

export interface Refusal {
  agent: AgentName;
  reason_code: RefusalReasonCode | string;
  missing_input: string[];
  detail: string;
}

export interface ProblemDetail {
  type: string;
  title: string;
  status: number;
  code: string;
  field?: string;
  detail: string;
  instance: string;
  refusal: Refusal | null;
}

// --- Snapshot Scenario e Tracciamento Flotta ---
export interface VehiclePosition {
  vehicle_id: string;
  route_id?: string | null;
  latitude: number;
  longitude: number;
  bearing?: number | null;
  observed_at: string;
  source_id: string;
  is_simulated: boolean;
}

export interface ScenarioSnapshot {
  contract_version: "1.0.0" | string;
  scenario_id: string;
  title: string;
  findings: Finding[];
  vehicle_positions: VehiclePosition[];
}

export interface FindingResponse {
  contract_version: string;
  finding: Finding;
  finding_ref: string;
}
