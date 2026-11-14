"use client";

import { useQuery } from "@tanstack/react-query";
import {
  ApiError,
  ContractValidationError,
  NetworkError,
  getScenario,
  type CheckedEnvelope,
} from "@/lib/api";
import { EXPECTED_CONTRACT_VERSION, type Problem, type ScenarioResponse } from "@/lib/contracts";

export type ScenarioLoadStatus = "loading" | "ready" | "partial" | "empty" | "degraded" | "error";

export type UseScenarioResult = {
  scenario: ScenarioResponse | undefined;
  status: ScenarioLoadStatus;
  contractVersion: string;
  contractMismatch: boolean;
  problem: Problem | undefined;
  networkError: NetworkError | undefined;
  contractError: ContractValidationError | undefined;
  refetch: () => void;
};

export function useScenario(scenarioId: string): UseScenarioResult {
  const query = useQuery<CheckedEnvelope<ScenarioResponse>, Error>({
    queryKey: ["scenario", scenarioId],
    queryFn: ({ signal }) => getScenario(scenarioId, signal),
    enabled: scenarioId.trim().length > 0,
    staleTime: 0,
    refetchOnWindowFocus: false,
    retry: (failureCount, error) => {
      if (error instanceof ContractValidationError) return false;
      if (error instanceof ApiError && error.problem.status !== 503) return false;
      return failureCount < 2;
    },
    retryDelay: (attempt) => Math.min(400 * 2 ** attempt, 2000),
  });

  const refetch = () => {
    void query.refetch();
  };

  if (query.isPending || query.isFetching) {
    if (!query.data) {
      return {
        scenario: undefined,
        status: "loading",
        contractVersion: EXPECTED_CONTRACT_VERSION,
        contractMismatch: false,
        problem: undefined,
        networkError: undefined,
        contractError: undefined,
        refetch,
      };
    }
  }

  if (query.error) {
    if (query.error instanceof ApiError) {
      const code = query.error.problem.code;
      const status: ScenarioLoadStatus =
        code === "scenario_not_found"
          ? "empty"
          : code === "upstream_timeout" || code === "upstream_unavailable"
            ? "degraded"
            : "error";
      return {
        scenario: undefined,
        status,
        contractVersion: EXPECTED_CONTRACT_VERSION,
        contractMismatch: false,
        problem: query.error.problem,
        networkError: undefined,
        contractError: undefined,
        refetch,
      };
    }
    if (query.error instanceof NetworkError) {
      return {
        scenario: undefined,
        status: "degraded",
        contractVersion: EXPECTED_CONTRACT_VERSION,
        contractMismatch: false,
        problem: undefined,
        networkError: query.error,
        contractError: undefined,
        refetch,
      };
    }
    return {
      scenario: undefined,
      status: "error",
      contractVersion: EXPECTED_CONTRACT_VERSION,
      contractMismatch: false,
      problem: {
        type: "about:blank",
        title: "Errore",
        status: 500,
        code: "internal_error",
        detail: "Errore interno del servizio",
        instance: `/api/v1/scenario/${scenarioId}`,
      },
      networkError: undefined,
      contractError: query.error instanceof ContractValidationError ? query.error : undefined,
      refetch,
    };
  }

  if (!query.data) {
    return {
      scenario: undefined,
      status: "loading",
      contractVersion: EXPECTED_CONTRACT_VERSION,
      contractMismatch: false,
      problem: undefined,
      networkError: undefined,
      contractError: undefined,
      refetch,
    };
  }

  const scenario = query.data.data;
  const status: ScenarioLoadStatus = scenario.findings.length < 3 ? "partial" : "ready";

  return {
    scenario,
    status,
    contractVersion: query.data.contractVersion,
    contractMismatch: query.data.contractMismatch,
    problem: undefined,
    networkError: undefined,
    contractError: undefined,
    refetch,
  };
}
