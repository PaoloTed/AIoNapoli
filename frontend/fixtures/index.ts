import type { DecisionResponse, ScenarioResponse } from "@/lib/types/contracts";
import type { TraceEvent } from "@/lib/types/trace";
import decisionBagnoliRaw from "./decision-bagnoli.json";
import refusalExamplesRaw from "./refusal-examples.json";
import scenarioBagnoliRaw from "./scenario-bagnoli.json";

export const scenarioBagnoli = scenarioBagnoliRaw as unknown as ScenarioResponse;
export const decisionBagnoli = decisionBagnoliRaw as unknown as DecisionResponse;
export const refusalExamples = refusalExamplesRaw;

export const streamBagnoliEvents: TraceEvent[] = [
  { seq: 1, event_type: "start", data: { scenario_id: "bagnoli", contract_version: "1.0.0" } },
  { seq: 2, event_type: "phase", data: { phase: "validazione", index: 1 } },
  { seq: 3, event_type: "phase", data: { phase: "trace", index: 2 } },
  { seq: 4, event_type: "phase", data: { phase: "regole", index: 3 } },
  {
    seq: 5,
    event_type: "rule_evaluated",
    data: {
      rule_id: "R1_line2_crowding",
      agents: ["mobility", "crowding"],
      fired: true,
      reason: "mobility.severity=high e density=0.91 oltre soglia 0.85",
    },
    agent: "orchestrator",
    finding_ref: "a5852d144fb2",
    rule_applied: "R1_line2_crowding",
    outcome: "mobility.severity=high e density=0.91 oltre soglia 0.85",
  },
  {
    seq: 6,
    event_type: "rule_evaluated",
    data: {
      rule_id: "R2_conflict_route_vs_density",
      agents: ["mobility", "crowding"],
      fired: true,
      reason: "percorso e zona satura coincidono su Z_BAGNOLI (density=0.91 > 0.85)",
    },
    agent: "orchestrator",
    finding_ref: "b26d58b90c9a",
    rule_applied: "R2_conflict_route_vs_density",
    outcome: "percorso e zona satura coincidono su Z_BAGNOLI (density=0.91 > 0.85)",
  },
  {
    seq: 7,
    event_type: "rule_evaluated",
    data: {
      rule_id: "R3_weather_capacity",
      agents: ["context", "crowding"],
      fired: true,
      reason: "pioggia intensa attiva e density=0.91 oltre soglia 0.70, capacita' ridotta",
    },
    agent: "orchestrator",
    finding_ref: "df855e7bf9a2",
    rule_applied: "R3_weather_capacity",
    outcome: "pioggia intensa attiva e density=0.91 oltre soglia 0.70, capacita' ridotta",
  },
  {
    seq: 8,
    event_type: "rule_evaluated",
    data: {
      rule_id: "R4_event_surge",
      agents: ["context", "mobility"],
      fired: true,
      reason: "affluenza attesa 12000 > 10000 con congestion=0.88, valutate alternative",
    },
    agent: "orchestrator",
    finding_ref: "df855e7bf9a2",
    rule_applied: "R4_event_surge",
    outcome: "affluenza attesa 12000 > 10000 con congestion=0.88, valutate alternative",
  },
  { seq: 9, event_type: "phase", data: { phase: "conflitto", index: 4 } },
  {
    seq: 10,
    event_type: "conflict_detected",
    data: {
      description:
        "Il percorso verso Z_BAGNOLI attraversa la zona satura rilevata da crowding; deviazione diretta scartata per sicurezza",
      zone_id: "Z_BAGNOLI",
    },
    agent: "orchestrator",
    finding_ref: "none",
    rule_applied: "R2_conflict_route_vs_density",
    outcome:
      "Il percorso verso Z_BAGNOLI attraversa la zona satura rilevata da crowding; deviazione diretta scartata per sicurezza",
  },
  { seq: 11, event_type: "phase", data: { phase: "priorita", index: 5 } },
  {
    seq: 12,
    event_type: "priority_applied",
    data: { priority: "P1", winner: "crowding" },
    agent: "orchestrator",
    finding_ref: "none",
    rule_applied: "P1",
    outcome: "priorita' P1 applicata, prevale crowding",
  },
  { seq: 13, event_type: "phase", data: { phase: "piano", index: 6 } },
  { seq: 14, event_type: "plan_item_created", data: { target: "operator", action_ref: "plan:0" } },
  { seq: 15, event_type: "plan_item_created", data: { target: "tourist", action_ref: "plan:1" } },
  { seq: 16, event_type: "plan_item_created", data: { target: "citizen", action_ref: "plan:2" } },
  { seq: 17, event_type: "phase", data: { phase: "rilevanza", index: 7 } },
  { seq: 18, event_type: "phase", data: { phase: "hash", index: 8 } },
  {
    seq: 19,
    event_type: "route_proposed",
    data: { proposal_id: "prop_otp_1", iteration: 1, route_ids: ["L2"], duration_min: 22 },
    agent: "mobility",
    outcome: "proposta prop_otp_1 al giro 1",
  },
  {
    seq: 20,
    event_type: "route_invalidated",
    data: {
      proposal_id: "prop_otp_1",
      iteration: 1,
      constraint_kinds: ["closure"],
      evidence_refs: ["anm_cantiere_chiaia"],
    },
    agent: "incidents",
    outcome: "proposta prop_otp_1 scartata al giro 1",
  },
  {
    seq: 21,
    event_type: "negotiation_finished",
    data: { iterations: 2, exhausted: false, constraints_applied: ["anm_cantiere_chiaia"] },
    agent: "orchestrator",
    outcome: "negoziazione conclusa",
  },
  {
    seq: 22,
    event_type: "decision",
    data: { decision_id: "23afe929acf8f472", contract_version: "1.0.0" },
  },
];
