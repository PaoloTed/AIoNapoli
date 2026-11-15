/**
 * @purpose Hook SSE deterministico con backoff e replay mock per la demo offline
 * @contracts TraceEvent, StreamStatus
 * @tokens shared
 * @verified 2026-11-15
 */

"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { getScenarioStreamUrl } from "../api/endpoints";
import { getMockStreamEvents } from "../api/mocks";
import { useAppStore } from "../state/store";
import type { TraceEvent, TraceEventType } from "../types/trace";

const KNOWN_EVENTS: TraceEventType[] = [
  "start",
  "phase",
  "rule_evaluated",
  "conflict_detected",
  "priority_applied",
  "plan_item_created",
  "route_proposed",
  "route_invalidated",
  "negotiation_finished",
  "worker_delegated",
  "worker_outcome",
  "decision",
];

function parseData(raw: string): Record<string, unknown> {
  try {
    const parsed: unknown = JSON.parse(raw);
    return typeof parsed === "object" && parsed !== null
      ? (parsed as Record<string, unknown>)
      : {};
  } catch {
    return {};
  }
}

export type UseSSEStreamResult = {
  reconnect: () => void;
  replayMock: () => void;
};

export function useSSEStream(
  scenarioId: string,
  options?: { enabled?: boolean; simulated?: boolean },
): UseSSEStreamResult {
  const enabled = options?.enabled ?? true;
  const simulated = options?.simulated ?? false;
  const store = useAppStore();
  const { appendTraceEvents, setStreamStatus, resetStream } = store;
  const [attempt, setAttempt] = useState(0);
  const replayTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const replayMock = useCallback(() => {
    if (replayTimer.current) clearTimeout(replayTimer.current);
    resetStream();
    setStreamStatus("connected");
    const events = getMockStreamEvents();
    events.forEach((event, index) => {
      replayTimer.current = setTimeout(
        () => {
          appendTraceEvents([event]);
          if (index === events.length - 1) {
            setStreamStatus("idle");
          }
        },
        350 * (index + 1),
      );
    });
  }, [appendTraceEvents, resetStream, setStreamStatus]);

  const reconnect = useCallback(() => {
    resetStream();
    setAttempt((n) => n + 1);
  }, [resetStream]);

  useEffect(() => {
    if (!enabled || scenarioId.trim().length === 0) {
      return;
    }

    if (simulated) {
      resetStream();
      setStreamStatus("connected");
      const events = getMockStreamEvents();
      const timers: Array<ReturnType<typeof setTimeout>> = [];
      events.forEach((event, index) => {
        timers.push(
          setTimeout(
            () => {
              appendTraceEvents([event]);
              if (index === events.length - 1) {
                setStreamStatus("idle");
              }
            },
            350 * (index + 1),
          ),
        );
      });
      return () => {
        timers.forEach((timer) => clearTimeout(timer));
      };
    }

    if (typeof EventSource === "undefined") {
      setStreamStatus("disconnected");
      return;
    }

    resetStream();
    setStreamStatus("connected");

    const source = new EventSource(getScenarioStreamUrl(scenarioId));
    let closed = false;

    const close = () => {
      if (!closed) {
        closed = true;
        source.close();
      }
    };

    const handler = (type: TraceEventType) => (event: MessageEvent<string>) => {
      const seq = Number.parseInt(event.lastEventId, 10);
      const parsed: TraceEvent = {
        seq: Number.isFinite(seq) && seq > 0 ? seq : Date.now(),
        event_type: type,
        data: parseData(event.data),
      };
      appendTraceEvents([parsed]);
      if (type === "decision") {
        setStreamStatus("idle");
        close();
      }
    };

    for (const type of KNOWN_EVENTS) {
      source.addEventListener(type, handler(type) as EventListener);
    }

    source.addEventListener("error", () => {
      if (closed) return;
      if (source.readyState === EventSource.CONNECTING) {
        setStreamStatus("reconnecting");
      } else {
        setStreamStatus("disconnected");
        close();
      }
    });

    source.addEventListener("open", () => {
      setStreamStatus("connected");
    });

    return () => {
      close();
      if (replayTimer.current) clearTimeout(replayTimer.current);
    };
  }, [scenarioId, enabled, simulated, attempt, appendTraceEvents, resetStream, setStreamStatus]);

  return { reconnect, replayMock };
}
