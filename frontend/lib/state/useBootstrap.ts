/**
 * @purpose Bootstrap deterministico di scenario e decisione con fallback mock
 * @contracts ScenarioSnapshot, DecisionResponse, ProblemDetail
 * @tokens shared
 * @verified 2026-11-15
 */

"use client";

import { useCallback, useEffect, useState } from "react";
import { ApiError } from "../api/client";
import { getScenario, postDecision } from "../api/endpoints";
import { withMockFallback } from "../api/mockMode";
import { getMockDecision, getMockScenario } from "../api/mocks";
import { useAppStore } from "./store";
import type { DecisionResponse, ProblemDetail } from "../types/contracts";

export type BootstrapResult = {
  loading: boolean;
  problem: ProblemDetail | null;
  reload: () => void;
};

export function useBootstrapScenario(scenarioId: string): BootstrapResult {
  const { setScenario, setDecision, setSimulated } = useAppStore();
  const [loading, setLoading] = useState(true);
  const [problem, setProblem] = useState<ProblemDetail | null>(null);
  const [attempt, setAttempt] = useState(0);

  const reload = useCallback(() => {
    setAttempt((n) => n + 1);
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setProblem(null);
      try {
        const scenarioResult = await withMockFallback(
          () => getScenario(scenarioId),
          () => getMockScenario(scenarioId),
        );
        if (cancelled) return;
        setScenario(scenarioResult.data);
        if (scenarioResult.isSimulated || scenarioResult.data.findings.some((finding) => finding.is_simulated)) setSimulated(true);

        const decisionResult = await withMockFallback(
          () => postDecision({ scenario_id: scenarioId }),
          () => getMockDecision(),
        );
        if (cancelled) return;
        setDecision(decisionResult.data);
        if (decisionResult.isSimulated) setSimulated(true);
      } catch (error: unknown) {
        if (cancelled) return;
        setProblem(error instanceof ApiError ? error.problem : null);
        const fallbackScenario = getMockScenario(scenarioId);
        setScenario(fallbackScenario);
        setDecision(getMockDecision());
        setSimulated(true);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [scenarioId, attempt, setScenario, setDecision, setSimulated]);

  return { loading, problem, reload };
}

export async function computeRerunDecision(scenarioId: string): Promise<DecisionResponse> {
  const result = await withMockFallback(
    () => postDecision({ scenario_id: scenarioId }),
    () => getMockDecision(),
  );
  return result.data;
}
