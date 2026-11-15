import { z } from "zod";

// Re-export all strictly typed frozen contracts from lib/types/contracts
export * from "./types/contracts";

// Re-export all strictly typed trace & negotiation models from lib/types/trace
export * from "./types/trace";

import type {
  AgentName,
  Finding,
  FindingType,
  PlanTarget,
  ProblemDetail,
} from "./types/contracts";

export const AGENT_ORDER: readonly AgentName[] = ["mobility", "crowding", "context"] as const;
export const PLAN_TARGETS: readonly PlanTarget[] = ["operator", "tourist", "citizen"] as const;

export const FINDING_KEYS = [
  "agent",
  "type",
  "content",
  "confidence",
  "severity",
  "source_id",
  "data_reference",
  "is_simulated",
  "timestamp",
] as const;

export const DECISION_KEYS = [
  "trigger",
  "conflict",
  "plan",
  "reasoning_log",
  "confidence",
  "timestamp",
] as const;

// StreamEvent type for backward compatibility with useDecisionStream
export type StreamStartPayload = {
  scenario_id: string;
  contract_version: string;
};

export type StreamPhasePayload = {
  phase: string;
  index: number;
};

export type RuleEvaluatedPayload = {
  rule_id: string;
  agents: AgentName[];
  fired: boolean;
  reason: string;
};

export type ConflictDetectedPayload = {
  description: string;
  zone_id?: string | null | undefined;
};

export type PriorityAppliedPayload = {
  priority: string;
  winner: string;
};

export type PlanItemCreatedPayload = {
  target: PlanTarget;
  action_ref: string;
};

export type StreamDecisionPayload = {
  decision_id: string;
  contract_version: string;
};

export type StreamEvent =
  | { event: "start"; data: StreamStartPayload }
  | { event: "phase"; data: StreamPhasePayload }
  | { event: "rule_evaluated"; data: RuleEvaluatedPayload }
  | { event: "conflict_detected"; data: ConflictDetectedPayload }
  | { event: "priority_applied"; data: PriorityAppliedPayload }
  | { event: "plan_item_created"; data: PlanItemCreatedPayload }
  | { event: "decision"; data: StreamDecisionPayload }
  | { event: "error"; data: ProblemDetail };

// Zod schemas
export const agentNameSchema = z.enum(["mobility", "crowding", "context"]);
export const severitySchema = z.enum(["low", "medium", "high", "critical"]);
export const findingTypeSchema = z.enum([
  "route_disruption",
  "route_alternative",
  "density_alert",
  "impact_assessment",
]);
export const planTargetSchema = z.enum(["operator", "tourist", "citizen"]);
export const ruleIdSchema = z.enum([
  "R1_line2_crowding",
  "R2_conflict_route_vs_density",
  "R3_weather_capacity",
  "R4_event_surge",
]);

const ALLOWED_TYPES_BY_AGENT: Record<AgentName, readonly FindingType[]> = {
  mobility: ["route_disruption", "route_alternative"],
  crowding: ["density_alert"],
  context: ["impact_assessment"],
};

function createFindingSchema(strict: boolean) {
  const base = z.object({
    agent: agentNameSchema,
    type: findingTypeSchema,
    content: z.record(z.unknown()),
    confidence: z.number().min(0).max(1),
    severity: severitySchema,
    source_id: z.string().min(1),
    data_reference: z.string().min(1),
    is_simulated: z.boolean(),
    timestamp: z.string().min(1),
  });
  const shaped = strict ? base.strict() : base;
  return shaped.refine((value) => ALLOWED_TYPES_BY_AGENT[value.agent].includes(value.type), {
    message: "Incoherent agent and finding type pair",
    path: ["type"],
  });
}

function createVehiclePositionSchema(strict: boolean) {
  const base = z.object({
    vehicle_id: z.string().min(1),
    route_id: z.string().nullish(),
    trip_id: z.string().nullish(),
    latitude: z.number(),
    longitude: z.number(),
    bearing: z.number().nullish(),
    speed_mps: z.number().nullish(),
    zone_id: z.string().nullish(),
    observed_at: z.string().min(1),
    source_id: z.string().min(1),
    is_simulated: z.boolean(),
  });
  return strict ? base.strict() : base;
}

function createDecisionSchema(strict: boolean) {
  const maybeStrict = <T extends z.ZodRawShape>(shape: T) =>
    strict ? z.object(shape).strict() : z.object(shape);

  const trigger = maybeStrict({
    rule_id: ruleIdSchema,
    agents_involved: z.array(agentNameSchema).min(1),
  });
  const conflict = maybeStrict({
    detected: z.boolean(),
    description: z.string().min(1),
  });
  const planItem = maybeStrict({
    priority: z.number().int().min(1),
    action: z.string().min(1),
    target: planTargetSchema,
    rationale: z.string().min(1),
  });
  const reasoningStep = maybeStrict({
    step: z.number().int().min(1),
    agent: z.string().min(1),
    finding_ref: z.string().min(1),
    rule_applied: z.string().min(1),
    outcome: z.string().min(1),
  });
  return maybeStrict({
    trigger,
    conflict,
    plan: z.array(planItem).min(1),
    reasoning_log: z.array(reasoningStep).min(1),
    confidence: z.number().min(0).max(1),
    timestamp: z.string().min(1),
  });
}

function createRelevanceSchema(strict: boolean) {
  const maybeStrict = <T extends z.ZodRawShape>(shape: T) =>
    strict ? z.object(shape).strict() : z.object(shape);

  const contribution = maybeStrict({
    feature: z.string().min(1),
    value: z.number(),
    weight: z.number(),
    contribution: z.number(),
  });
  const scoredItem = maybeStrict({
    plan_index: z.number().int().min(0),
    score: z.number().min(0).max(1),
    contributions: z.array(contribution),
  });
  const targetRelevance = maybeStrict({
    order: z.array(z.number().int().min(0)),
    items: z.array(scoredItem),
  });
  return maybeStrict({
    rounding: z.number().int().min(0),
    targets: maybeStrict({
      operator: targetRelevance,
      tourist: targetRelevance,
      citizen: targetRelevance,
    }),
  });
}

function createNarrativeSchema(strict: boolean) {
  const maybeStrict = <T extends z.ZodRawShape>(shape: T) =>
    strict ? z.object(shape).strict() : z.object(shape);

  return maybeStrict({
    mode: z.enum(["replay", "live", "off"]),
    items: z.array(
      maybeStrict({
        plan_index: z.number().int().min(0),
        texts: maybeStrict({
          it: z.string(),
          en: z.string().optional(),
        }),
      }),
    ),
  });
}

export const findingSchema = createFindingSchema(true);
export const decisionSchema = createDecisionSchema(true);
export const refusalSchema = z
  .object({
    agent: agentNameSchema,
    reason_code: z.string().min(1),
    missing_input: z.array(z.string()),
    detail: z.string(),
  })
  .strict();

export const vehiclePositionSchema = createVehiclePositionSchema(true);
export const relevanceScoreSchema = createRelevanceSchema(true);
export const narrativeSchema = createNarrativeSchema(true);

export const scenarioResponseSchema = z
  .object({
    contract_version: z.string().min(1),
    scenario_id: z.string().min(1),
    title: z.string(),
    findings: z.array(findingSchema),
    vehicle_positions: z.array(vehiclePositionSchema).default([]),
  })
  .strict();

export const decisionResponseSchema = z
  .object({
    contract_version: z.string().min(1),
    decision_id: z.string().min(1),
    decision: decisionSchema,
    relevance: relevanceScoreSchema,
    narrative: narrativeSchema,
  })
  .strict();

export const problemSchema = z.object({
  type: z.string().default("about:blank"),
  title: z.string().default("Errore"),
  status: z.number().int(),
  code: z.string().min(1),
  field: z.string().optional(),
  detail: z.string(),
  instance: z.string().default(""),
  refusal: refusalSchema.optional(),
});

// Tolerant schemas used ONLY when contract_version differs from EXPECTED_CONTRACT_VERSION
export const compatScenarioResponseSchema = z.object({
  contract_version: z.string().min(1),
  scenario_id: z.string().min(1),
  title: z.string(),
  findings: z.array(createFindingSchema(false)),
  vehicle_positions: z.array(createVehiclePositionSchema(false)).default([]),
});

export const compatDecisionResponseSchema = z.object({
  contract_version: z.string().min(1),
  decision_id: z.string().min(1),
  decision: createDecisionSchema(false),
  relevance: createRelevanceSchema(false),
  narrative: createNarrativeSchema(false),
});

// SSE event schemas
export const streamStartSchema = z.object({
  scenario_id: z.string(),
  contract_version: z.string(),
});

export const streamPhaseSchema = z.object({
  phase: z.string(),
  index: z.number().int(),
});

export const ruleEvaluatedSchema = z.object({
  rule_id: z.string(),
  agents: z.array(agentNameSchema),
  fired: z.boolean(),
  reason: z.string(),
});

export const conflictDetectedSchema = z.object({
  description: z.string(),
  zone_id: z.string().nullish(),
});

export const priorityAppliedSchema = z.object({
  priority: z.string(),
  winner: z.string(),
});

export const planItemCreatedSchema = z.object({
  target: planTargetSchema,
  action_ref: z.string(),
});

export const streamDecisionSchema = z.object({
  decision_id: z.string(),
  contract_version: z.string(),
});

// Content accessors (FE-REQ-03)
const num = (c: Record<string, unknown>, k: string): number | undefined =>
  typeof c[k] === "number" && Number.isFinite(c[k]) ? (c[k] as number) : undefined;

export const density = (f: Finding): number | undefined => num(f.content, "density");
export const congestion = (f: Finding): number | undefined => num(f.content, "congestion");
export const zoneId = (f: Finding): string | undefined =>
  typeof f.content.zone_id === "string" && f.content.zone_id.length > 0
    ? f.content.zone_id
    : undefined;
export const heavyRain = (f: Finding): boolean | undefined =>
  typeof f.content.heavy_rain === "boolean" ? f.content.heavy_rain : undefined;
export const expectedAttendance = (f: Finding): number | undefined =>
  num(f.content, "expected_attendance");
