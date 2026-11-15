/**
 * @purpose Scheda di un percorso proposto durante la negoziazione
 * @contracts RouteProposedData, TraceEvent
 * @tokens operator
 * @verified 2026-11-15
 */

import { operatorTokens as t } from "@/styles/design-tokens-operator";
import { Badge } from "@/components/ui/Badge";
import { isRouteProposed } from "@/lib/types/trace";
import type { TraceEvent } from "@/lib/types/trace";

const MODE_LABEL: Record<string, string> = {
  metro: "Metro",
  bus: "Bus",
  tram: "Tram",
  walk: "A piedi",
  rail: "Treno",
};

export function ProposalCard({ event }: { event: TraceEvent }) {
  if (!isRouteProposed(event.data)) return null;
  return (
    <article
      style={{
        background: t.color.bg.panel,
        border: `1px solid ${t.color.border.subtle}`,
        borderLeft: `3px solid ${t.color.accent.primary}`,
        borderRadius: t.radius.md,
        padding: t.space[3],
        display: "grid",
        gap: t.space[2],
      }}
    >
      <header style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: t.space[2] }}>
        <code style={{ fontSize: t.font.size.sm, color: t.color.accent.primary }}>{event.data.proposal_id}</code>
        <Badge tone="accent">Proposto</Badge>
      </header>
      <ol style={{ margin: 0, paddingLeft: t.space[4], display: "grid", gap: t.space[1] }}>
        {event.data.legs.map((leg, index) => (
          <li key={`${event.data.proposal_id}-${index}`} style={{ fontSize: t.font.size.base, color: t.color.text.secondary }}>
            {MODE_LABEL[leg.mode] ?? leg.mode}
            {leg.line_id ? ` ${leg.line_id}` : ""} · {leg.from_stop} → {leg.to_stop}
            {typeof leg.duration_min === "number" ? ` · ${leg.duration_min} min` : ""}
          </li>
        ))}
      </ol>
      <span style={{ fontSize: t.font.size.xs, color: t.color.text.muted }}>
        seq #{event.seq} · agente {event.agent ?? "mobility"}
      </span>
    </article>
  );
}
