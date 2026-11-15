/**
 * @purpose Cronologia verticale degli eventi di negoziazione ordinati per seq
 * @contracts TraceEvent
 * @tokens operator
 * @verified 2026-11-15
 */

import { operatorTokens as t } from "@/styles/design-tokens-operator";
import type { TraceEvent } from "@/lib/types/trace";
import { ProposalCard } from "./ProposalCard";
import { RejectionCard } from "./RejectionCard";
import { NegotiationEndCard } from "./NegotiationEndCard";

const NEGOTIATION_TYPES = new Set<TraceEvent["event_type"]>([
  "route_proposed",
  "route_invalidated",
  "negotiation_finished",
]);

export function NegotiationTimeline({ events }: { events: TraceEvent[] }) {
  const negotiation = events.filter((event) => NEGOTIATION_TYPES.has(event.event_type)).sort((a, b) => a.seq - b.seq);

  return (
    <ol
      style={{
        margin: 0,
        padding: 0,
        listStyle: "none",
        display: "grid",
        gap: t.space[3],
        position: "relative",
      }}
      aria-live="polite"
    >
      {negotiation.map((event) => (
        <li key={`${event.event_type}-${event.seq}`} style={{ display: "grid", gridTemplateColumns: "56px minmax(0, 1fr)", gap: t.space[3] }}>
          <span style={{ fontSize: t.font.size.xs, color: t.color.text.muted, paddingTop: t.space[3] }}>
            #{event.seq}
          </span>
          {event.event_type === "route_proposed" ? <ProposalCard event={event} /> : null}
          {event.event_type === "route_invalidated" ? <RejectionCard event={event} /> : null}
          {event.event_type === "negotiation_finished" ? <NegotiationEndCard event={event} /> : null}
        </li>
      ))}
    </ol>
  );
}
