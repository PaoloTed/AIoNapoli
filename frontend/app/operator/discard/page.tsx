/**
 * @purpose Scheda Scarti e tracciamento della negoziazione
 * @contracts TraceEvent
 * @tokens operator
 * @verified 2026-11-15
 */

"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useAppStore } from "@/lib/state/store";
import { getMockStreamEvents } from "@/lib/api/mocks";
import { operatorTokens as t } from "@/styles/design-tokens-operator";
import { NegotiationTimeline } from "@/components/operator/discard/NegotiationTimeline";
import { EmptyState } from "@/components/ui/EmptyState";
import { Button } from "@/components/ui/Button";

export default function DiscardPage() {
  const { traceEvents, isSimulated, appendTraceEvents, resetStream, setStreamStatus } = useAppStore();
  const [replaying, setReplaying] = useState(false);
  const timers = useRef<Array<ReturnType<typeof setTimeout>>>([]);

  useEffect(() => {
    return () => {
      timers.current.forEach((timer) => clearTimeout(timer));
    };
  }, []);

  const startReplay = useCallback(() => {
    if (replaying) return;
    timers.current.forEach((timer) => clearTimeout(timer));
    timers.current = [];
    resetStream();
    setReplaying(true);
    setStreamStatus("connected");
    const events = getMockStreamEvents();
    events.forEach((event, index) => {
      timers.current.push(
        setTimeout(() => {
          appendTraceEvents([event]);
          if (index === events.length - 1) {
            setReplaying(false);
            setStreamStatus("idle");
          }
        }, 400 * (index + 1)),
      );
    });
  }, [appendTraceEvents, replaying, resetStream, setStreamStatus]);

  const negotiationCount = traceEvents.filter((event) =>
    ["route_proposed", "route_invalidated", "negotiation_finished"].includes(event.event_type),
  ).length;

  return (
    <div style={{ display: "grid", gap: "16px", maxWidth: "960px" }}>
      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: "12px", flexWrap: "wrap" }}>
        <div>
          <h2 style={{ margin: 0, fontSize: t.font.size.xl }}>Trasparenza della negoziazione</h2>
          <p style={{ margin: 0, fontSize: t.font.size.sm, color: t.color.text.secondary }}>
            {negotiationCount} eventi di negoziazione · {traceEvents.length} eventi totali ordinati per seq
          </p>
        </div>
        <Button variant="primary" onClick={startReplay} disabled={replaying}>
          {replaying ? "Simulazione in corso…" : "Avvia scenario"}
        </Button>
      </header>

      {negotiationCount === 0 ? (
        <EmptyState
          title="Nessun evento di negoziazione"
          description={
            isSimulated
              ? "La modalità simulazione è attiva: avvia lo scenario per osservare proposte, scarti e accordo finale."
              : "Attendi lo stream SSE oppure avvia la simulazione locale per vedere il ciclo Mobilità-Imprevisti."
          }
          action={
            <Button variant="primary" onClick={startReplay} disabled={replaying}>
              Avvia scenario
            </Button>
          }
        />
      ) : (
        <NegotiationTimeline events={traceEvents} />
      )}
    </div>
  );
}
