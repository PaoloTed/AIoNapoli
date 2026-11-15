"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { streamBagnoliEvents } from "@/fixtures";
import { getScenarioStreamUrl } from "@/lib/api";
import type { AllStreamEventType, TraceEvent, TraceEventDataMap } from "@/lib/types/trace";

export type StreamStatus = "idle" | "connecting" | "open" | "done" | "degraded";

export type UseSSEStreamOptions = {
  enabled?: boolean;
  maxRetries?: number;
  initialBackoffMs?: number;
  maxBackoffMs?: number;
  mockEvents?: TraceEvent[];
  playbackSpeedMs?: number;
};

export type UseSSEStreamResult = {
  events: TraceEvent[];
  status: StreamStatus;
  isMock: boolean;
  lastSeq: number;
  reconnect: () => void;
};

const TRACE_EVENT_NAMES: readonly string[] = [
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
  "error",
] as const;

/**
 * Robust SSE client with exponential backoff, monotonic `seq` ordering enforcement,
 * and offline/mock playback fallback.
 */
export function useSSEStream(
  scenarioId: string,
  options: UseSSEStreamOptions = {},
): UseSSEStreamResult {
  const {
    enabled = true,
    maxRetries = 3,
    initialBackoffMs = 1000,
    maxBackoffMs = 8000,
    mockEvents = streamBagnoliEvents,
    playbackSpeedMs = 120,
  } = options;

  const [events, setEvents] = useState<TraceEvent[]>([]);
  const [status, setStatus] = useState<StreamStatus>("idle");
  const [isMock, setIsMock] = useState<boolean>(false);
  const [attempt, setAttempt] = useState<number>(0);

  const lastSeqRef = useRef<number>(0);
  const retryCountRef = useRef<number>(0);
  const esRef = useRef<EventSource | null>(null);

  const reconnect = useCallback(() => {
    setEvents([]);
    lastSeqRef.current = 0;
    retryCountRef.current = 0;
    setAttempt((prev) => prev + 1);
  }, []);

  useEffect(() => {
    if (!enabled || !scenarioId.trim()) {
      setStatus("idle");
      setEvents([]);
      lastSeqRef.current = 0;
      return;
    }

    const forceMocks = process.env.NEXT_PUBLIC_USE_MOCKS === "true";
    const noEventSource = typeof EventSource === "undefined";

    // Playback mock stream if forced or in environments without EventSource
    if (forceMocks || noEventSource) {
      setIsMock(true);
      setStatus("open");
      setEvents([]);
      lastSeqRef.current = 0;

      const playbackList = mockEvents;
      let currentIndex = 0;

      const intervalId = setInterval(() => {
        if (currentIndex < playbackList.length) {
          const rawEv = playbackList[currentIndex];
          if (rawEv && rawEv.seq > lastSeqRef.current) {
            lastSeqRef.current = rawEv.seq;
            setEvents((prev) => [...prev, rawEv]);
          }
          currentIndex += 1;
          if (currentIndex >= playbackList.length) {
            setStatus("done");
            clearInterval(intervalId);
          }
        } else {
          setStatus("done");
          clearInterval(intervalId);
        }
      }, playbackSpeedMs);

      return () => {
        clearInterval(intervalId);
      };
    }

    let active = true;
    let timerId: ReturnType<typeof setTimeout> | null = null;

    function connect() {
      if (!active) return;
      setStatus(retryCountRef.current === 0 ? "connecting" : "connecting");

      const url = getScenarioStreamUrl(scenarioId);
      const es = new EventSource(url);
      esRef.current = es;

      es.onopen = () => {
        if (!active) return;
        setStatus("open");
        setIsMock(false);
        setEvents([]);
        lastSeqRef.current = 0;
        retryCountRef.current = 0;
      };

      const handleMessage = (eventType: string, event: MessageEvent) => {
        if (!active) return;

        let parsedData: unknown = {};
        try {
          parsedData = JSON.parse(event.data);
        } catch {
          parsedData = { raw: event.data };
        }

        const hasRawId =
          typeof event.lastEventId === "string" && event.lastEventId.trim().length > 0;
        const rawId = hasRawId ? parseInt(event.lastEventId, 10) : NaN;

        const dataSeq =
          parsedData && typeof parsedData === "object" && "seq" in parsedData
            ? Number((parsedData as { seq: unknown }).seq)
            : NaN;

        const candidateSeq = !Number.isNaN(dataSeq)
          ? dataSeq
          : !Number.isNaN(rawId)
            ? rawId
            : lastSeqRef.current + 1;

        // Monotonic seq check: discard out-of-order or duplicate sequences
        if (candidateSeq <= lastSeqRef.current) {
          return;
        }
        lastSeqRef.current = candidateSeq;

        const payloadObj = parsedData && typeof parsedData === "object" ? parsedData : {};
        const agent = "agent" in payloadObj && typeof payloadObj.agent === "string" ? payloadObj.agent : null;
        const findingRef =
          "finding_ref" in payloadObj && typeof payloadObj.finding_ref === "string"
            ? payloadObj.finding_ref
            : null;
        const ruleApplied =
          "rule_applied" in payloadObj && typeof payloadObj.rule_applied === "string"
            ? payloadObj.rule_applied
            : null;
        const outcome =
          "outcome" in payloadObj && typeof payloadObj.outcome === "string" ? payloadObj.outcome : null;

        const typedEvent: TraceEvent = {
          seq: candidateSeq,
          event_type: eventType as AllStreamEventType,
          data: parsedData as TraceEventDataMap[keyof TraceEventDataMap],
          agent,
          finding_ref: findingRef,
          rule_applied: ruleApplied,
          outcome,
        };

        setEvents((prev) => [...prev, typedEvent]);

        if (eventType === "decision") {
          setStatus("done");
          es.close();
        } else if (eventType === "error") {
          setStatus("degraded");
          es.close();
        }
      };

      for (const name of TRACE_EVENT_NAMES) {
        es.addEventListener(name, (e) => handleMessage(name, e as MessageEvent));
      }

      // Also listen to default onmessage in case server sends untyped events
      es.onmessage = (e) => handleMessage("phase", e);

      es.onerror = () => {
        if (!active) return;
        es.close();

        if (retryCountRef.current < maxRetries) {
          const backoff = Math.min(
            initialBackoffMs * Math.pow(2, retryCountRef.current),
            maxBackoffMs,
          );
          retryCountRef.current += 1;
          timerId = setTimeout(connect, backoff);
        } else {
          // Max retries reached: gracefully fall back to mock stream if available
          if (mockEvents.length > 0) {
            setIsMock(true);
            setEvents(mockEvents);
            lastSeqRef.current = mockEvents[mockEvents.length - 1]?.seq ?? 0;
            setStatus("done");
          } else {
            setStatus("degraded");
          }
        }
      };
    }

    connect();

    return () => {
      active = false;
      if (timerId) clearTimeout(timerId);
      if (esRef.current) esRef.current.close();
    };
  }, [
    scenarioId,
    enabled,
    attempt,
    maxRetries,
    initialBackoffMs,
    maxBackoffMs,
    mockEvents,
    playbackSpeedMs,
  ]);

  return {
    events,
    status,
    isMock,
    lastSeq: lastSeqRef.current,
    reconnect,
  };
}
