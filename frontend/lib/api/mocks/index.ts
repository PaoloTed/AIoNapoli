/**
 * @purpose Dataset mock conformi ai contratti, sorgente di fallback offline
 * @contracts ScenarioSnapshot, DecisionResponse, TraceEvent, Refusal
 * @tokens shared
 * @verified 2026-11-15
 */

import scenarioBagnoliJson from "./scenario-bagnoli.json";
import decisionBagnoliJson from "./decision-bagnoli.json";
import streamBagnoliJson from "./stream-bagnoli.json";
import refusalExamplesJson from "./refusal-examples.json";
import type { DecisionResponse, Refusal, ScenarioSnapshot } from "../../types/contracts";
import type { TraceEvent } from "../../types/trace";

export const mockScenarioBagnoli = scenarioBagnoliJson as unknown as ScenarioSnapshot;
export const mockDecisionBagnoli = decisionBagnoliJson as unknown as DecisionResponse;
export const mockStreamBagnoli = streamBagnoliJson as unknown as TraceEvent[];
export const mockRefusals = refusalExamplesJson as unknown as Refusal[];

export function getMockScenario(scenarioId: string): ScenarioSnapshot {
  // Unico dataset demo consolidato: lo scenario bagnoli alimenta ogni fallback.
  return { ...mockScenarioBagnoli, scenario_id: scenarioId };
}

export function getMockDecision(): DecisionResponse {
  return mockDecisionBagnoli;
}

export function getMockStreamEvents(): TraceEvent[] {
  return mockStreamBagnoli.map((event) => ({ ...event }));
}
