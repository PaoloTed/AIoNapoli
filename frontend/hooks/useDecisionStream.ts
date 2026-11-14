"use client";

import { useCallback, useEffect, useState } from "react";
import { getScenarioStreamUrl } from "@/lib/api";
import {
  EXPECTED_CONTRACT_VERSION,
  conflictDetectedSchema,
  planItemCreatedSchema,
  priorityAppliedSchema,
  problemSchema,
  ruleEvaluatedSchema,
  streamDecisionSchema,
  streamPhaseSchema,
  streamStartSchema,
  type StreamEvent,
} from "@/lib/contracts";

export type StreamStatus = "idle" | "open" | "done" | "degraded";

export type UseDecisionStreamResult = {
  steps: StreamEvent[];
  status: StreamStatus;
  contractMismatch: boolean;
  reconnect: () => void;
};

function safeParseJson(raw: string): unknown {
  try {
    return JSON.parse(raw);
  } catch {
    return undefined;
  }
}

export function useDecisionStream(scenarioId: string, enabled = true): UseDecisionStreamResult {
  const [steps, setSteps] = useState<StreamEvent[]>([]);
  const [status, setStatus] = useState<StreamStatus>("idle");
  const [contractMismatch, setContractMismatch] = useState(false);
  const [attempt, setAttempt] = useState(0);

  const reconnect = useCallback(() => {
    setSteps([]);
    setAttempt((n) => n + 1);
  }, []);

  useEffect(() => {
    if (!enabled || scenarioId.trim().length === 0) {
      setSteps([]);
      setStatus("idle");
      return;
    }

    if (typeof EventSource === "undefined") {
      setStatus("degraded");
      return;
    }

    // Reset timeline before opening so reconnects never duplicate steps (FE-REQ-16)
    setSteps([]);
    setContractMismatch(false);
    setStatus("open");

    const es = new EventSource(getScenarioStreamUrl(scenarioId));
    let closed = false;

    const closeStream = () => {
      if (!closed) {
        closed = true;
        es.close();
      }
    };

    es.addEventListener("open", () => {
      setSteps([]);
      setStatus("open");
    });

    es.addEventListener("start", (event) => {
      const payload = streamStartSchema.safeParse(
        safeParseJson((event as MessageEvent<string>).data),
      );
      if (!payload.success) return;
      if (payload.data.contract_version !== EXPECTED_CONTRACT_VERSION) {
        setContractMismatch(true);
      }
      setSteps((prev) => [...prev, { event: "start", data: payload.data }]);
    });

    es.addEventListener("phase", (event) => {
      const payload = streamPhaseSchema.safeParse(
        safeParseJson((event as MessageEvent<string>).data),
      );
      if (!payload.success) return;
      setSteps((prev) => [...prev, { event: "phase", data: payload.data }]);
    });

    es.addEventListener("rule_evaluated", (event) => {
      const payload = ruleEvaluatedSchema.safeParse(
        safeParseJson((event as MessageEvent<string>).data),
      );
      if (!payload.success) return;
      setSteps((prev) => [...prev, { event: "rule_evaluated", data: payload.data }]);
    });

    es.addEventListener("conflict_detected", (event) => {
      const payload = conflictDetectedSchema.safeParse(
        safeParseJson((event as MessageEvent<string>).data),
      );
      if (!payload.success) return;
      setSteps((prev) => [...prev, { event: "conflict_detected", data: payload.data }]);
    });

    es.addEventListener("priority_applied", (event) => {
      const payload = priorityAppliedSchema.safeParse(
        safeParseJson((event as MessageEvent<string>).data),
      );
      if (!payload.success) return;
      setSteps((prev) => [...prev, { event: "priority_applied", data: payload.data }]);
    });

    es.addEventListener("plan_item_created", (event) => {
      const payload = planItemCreatedSchema.safeParse(
        safeParseJson((event as MessageEvent<string>).data),
      );
      if (!payload.success) return;
      setSteps((prev) => [...prev, { event: "plan_item_created", data: payload.data }]);
    });

    es.addEventListener("decision", (event) => {
      const payload = streamDecisionSchema.safeParse(
        safeParseJson((event as MessageEvent<string>).data),
      );
      if (payload.success) {
        if (payload.data.contract_version !== EXPECTED_CONTRACT_VERSION) {
          setContractMismatch(true);
        }
        setSteps((prev) => [...prev, { event: "decision", data: payload.data }]);
      }
      setStatus("done");
      closeStream();
    });

    es.addEventListener("error", (event) => {
      if (closed) return;
      const msg = event as MessageEvent<string>;
      if (typeof msg.data === "string" && msg.data.length > 0) {
        const problem = problemSchema.safeParse(safeParseJson(msg.data));
        if (problem.success) {
          setSteps((prev) => [
            ...prev,
            {
              event: "error",
              data: {
                type: problem.data.type,
                title: problem.data.title,
                status: problem.data.status,
                code: problem.data.code,
                detail: problem.data.detail,
                instance: problem.data.instance,
                ...(problem.data.field !== undefined ? { field: problem.data.field } : {}),
                ...(problem.data.refusal !== undefined ? { refusal: problem.data.refusal } : {}),
              },
            },
          ]);
        }
      }
      setStatus("degraded");
      closeStream();
    });

    return () => {
      closeStream();
    };
  }, [scenarioId, enabled, attempt]);

  return { steps, status, contractMismatch, reconnect };
}
