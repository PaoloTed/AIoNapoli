/**
 * @purpose Store applicativo leggero condiviso dalle due superfici
 * @contracts ScenarioSnapshot, DecisionResponse, TraceEvent
 * @tokens shared
 * @verified 2026-11-15
 */

"use client";

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import type { DecisionResponse, ScenarioSnapshot, Target } from "../types/contracts";
import type { TraceEvent } from "../types/trace";

export type StreamStatus = "idle" | "connected" | "reconnecting" | "disconnected";
export type Locale = "it" | "en";

type SortableEvent = Pick<TraceEvent, "seq">;

function sortBySeq(events: TraceEvent[]): TraceEvent[] {
  return [...events].sort((a, b) => a.seq - b.seq);
}

function mergeEvents(current: TraceEvent[], incoming: TraceEvent[]): TraceEvent[] {
  const map = new Map<number, TraceEvent>();
  for (const event of current) map.set(event.seq, event);
  for (const event of incoming) map.set(event.seq, event);
  return sortBySeq([...map.values()]);
}

export type AppStore = {
  scenario: ScenarioSnapshot | null;
  decision: DecisionResponse | null;
  traceEvents: TraceEvent[];
  streamStatus: StreamStatus;
  isSimulated: boolean;
  target: Target;
  lang: Locale;
  setScenario: (scenario: ScenarioSnapshot | null) => void;
  setDecision: (decision: DecisionResponse | null) => void;
  setTraceEvents: (events: SortableEvent[]) => void;
  appendTraceEvents: (events: SortableEvent[]) => void;
  setStreamStatus: (status: StreamStatus) => void;
  setSimulated: (value: boolean) => void;
  setTarget: (target: Target) => void;
  setLang: (lang: Locale) => void;
  resetStream: () => void;
};

const StoreContext = createContext<AppStore | null>(null);

export function StoreProvider({ children }: { children: ReactNode }) {
  const [scenario, setScenario] = useState<ScenarioSnapshot | null>(null);
  const [decision, setDecision] = useState<DecisionResponse | null>(null);
  const [traceEvents, setTraceEventsState] = useState<TraceEvent[]>([]);
  const [streamStatus, setStreamStatus] = useState<StreamStatus>("idle");
  const [isSimulated, setSimulated] = useState(false);
  const [target, setTarget] = useState<Target>("citizen");
  const [lang, setLang] = useState<Locale>("it");

  const setTraceEvents = useCallback((events: SortableEvent[]) => {
    setTraceEventsState(sortBySeq(events as TraceEvent[]));
  }, []);

  const appendTraceEvents = useCallback((events: SortableEvent[]) => {
    setTraceEventsState((prev) => mergeEvents(prev, events as TraceEvent[]));
  }, []);

  const resetStream = useCallback(() => {
    setTraceEventsState([]);
    setStreamStatus("idle");
  }, []);

  const value = useMemo<AppStore>(
    () => ({
      scenario,
      decision,
      traceEvents,
      streamStatus,
      isSimulated,
      target,
      lang,
      setScenario,
      setDecision,
      setTraceEvents,
      appendTraceEvents,
      setStreamStatus,
      setSimulated,
      setTarget,
      setLang,
      resetStream,
    }),
    [
      scenario,
      decision,
      traceEvents,
      streamStatus,
      isSimulated,
      target,
      lang,
      setTraceEvents,
      appendTraceEvents,
      resetStream,
    ],
  );

  return <StoreContext.Provider value={value}>{children}</StoreContext.Provider>;
}

export function useAppStore(): AppStore {
  const ctx = useContext(StoreContext);
  if (!ctx) {
    throw new Error("useAppStore deve essere usato dentro StoreProvider");
  }
  return ctx;
}
