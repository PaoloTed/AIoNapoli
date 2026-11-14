"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import {
  ApiError,
  ContractValidationError,
  NetworkError,
  postDecision,
  repeatDecisionCheck,
  type CheckedEnvelope,
  type RepeatDecisionResult,
} from "@/lib/api";
import { EXPECTED_CONTRACT_VERSION, type DecisionResponse, type Problem } from "@/lib/contracts";

export type DecisionLoadStatus = "idle" | "loading" | "ready" | "no_rules" | "degraded" | "error";

export type RepeatComparisonState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "done"; same: boolean; firstId: string; secondId: string }
  | { status: "error"; detail: string };

export type UseDecisionResult = {
  decisionEnvelope: CheckedEnvelope<DecisionResponse> | undefined;
  status: DecisionLoadStatus;
  problem: Problem | undefined;
  networkError: NetworkError | undefined;
  contractMismatch: boolean;
  contractVersion: string;
  refetch: () => void;
  repeatCheck: () => void;
  repeatState: RepeatComparisonState;
};

export function useDecision(scenarioId: string, enabled: boolean): UseDecisionResult {
  const query = useQuery<CheckedEnvelope<DecisionResponse>, Error>({
    queryKey: ["decision", scenarioId],
    queryFn: ({ signal }) => postDecision({ scenario_id: scenarioId }, signal),
    enabled: enabled && scenarioId.trim().length > 0,
    retry: false, // Never retry POST /decision automatically (API-CLIENT.md §2)
    staleTime: 0,
    gcTime: 0,
    refetchOnWindowFocus: false,
  });

  const repeatMutation = useMutation<RepeatDecisionResult, Error, void>({
    mutationFn: () => repeatDecisionCheck(scenarioId),
    retry: false,
  });

  const repeatState: RepeatComparisonState = repeatMutation.isPending
    ? { status: "loading" }
    : repeatMutation.isError
      ? {
          status: "error",
          detail:
            repeatMutation.error instanceof ApiError
              ? repeatMutation.error.problem.code
              : "backend_unreachable",
        }
      : repeatMutation.isSuccess
        ? {
            status: "done",
            same: repeatMutation.data.same,
            firstId: repeatMutation.data.first.data.decision_id,
            secondId: repeatMutation.data.second.data.decision_id,
          }
        : { status: "idle" };

  const refetch = () => {
    void query.refetch();
  };
  const repeatCheck = () => repeatMutation.mutate();

  if (!enabled) {
    return {
      decisionEnvelope: undefined,
      status: "idle",
      problem: undefined,
      networkError: undefined,
      contractMismatch: false,
      contractVersion: EXPECTED_CONTRACT_VERSION,
      refetch,
      repeatCheck,
      repeatState,
    };
  }

  if (query.isPending || (query.isFetching && !query.data)) {
    return {
      decisionEnvelope: undefined,
      status: "loading",
      problem: undefined,
      networkError: undefined,
      contractMismatch: false,
      contractVersion: EXPECTED_CONTRACT_VERSION,
      refetch,
      repeatCheck,
      repeatState,
    };
  }

  if (query.error) {
    if (query.error instanceof ApiError) {
      const code = query.error.problem.code;
      const status: DecisionLoadStatus =
        code === "upstream_timeout" || code === "upstream_unavailable" ? "degraded" : "error";
      return {
        decisionEnvelope: undefined,
        status,
        problem: query.error.problem,
        networkError: undefined,
        contractMismatch: false,
        contractVersion: EXPECTED_CONTRACT_VERSION,
        refetch,
        repeatCheck,
        repeatState,
      };
    }

    if (query.error instanceof NetworkError) {
      return {
        decisionEnvelope: undefined,
        status: "degraded",
        problem: undefined,
        networkError: query.error,
        contractMismatch: false,
        contractVersion: EXPECTED_CONTRACT_VERSION,
        refetch,
        repeatCheck,
        repeatState,
      };
    }

    return {
      decisionEnvelope: undefined,
      status: "error",
      problem: {
        type: "about:blank",
        title: "Errore",
        status: 500,
        code: query.error instanceof ContractValidationError ? "invalid_finding" : "internal_error",
        detail: "Errore interno del servizio",
        instance: "/api/v1/decision",
      },
      networkError: undefined,
      contractMismatch: false,
      contractVersion: EXPECTED_CONTRACT_VERSION,
      refetch,
      repeatCheck,
      repeatState,
    };
  }

  if (!query.data) {
    return {
      decisionEnvelope: undefined,
      status: "idle",
      problem: undefined,
      networkError: undefined,
      contractMismatch: false,
      contractVersion: EXPECTED_CONTRACT_VERSION,
      refetch,
      repeatCheck,
      repeatState,
    };
  }

  const status: DecisionLoadStatus = query.data.data.decision.conflict.detected
    ? "ready"
    : "no_rules";

  return {
    decisionEnvelope: query.data,
    status,
    problem: undefined,
    networkError: undefined,
    contractMismatch: query.data.contractMismatch,
    contractVersion: query.data.contractVersion,
    refetch,
    repeatCheck,
    repeatState,
  };
}
