/**
 * @purpose Scheda di un percorso scartato con vincoli violati
 * @contracts RouteInvalidatedData, TraceEvent
 * @tokens operator
 * @verified 2026-11-15
 */

import { operatorTokens as t } from "@/styles/design-tokens-operator";
import { Badge } from "@/components/ui/Badge";
import { isRouteInvalidated } from "@/lib/types/trace";
import type { TraceEvent } from "@/lib/types/trace";

export function RejectionCard({ event }: { event: TraceEvent }) {
  if (!isRouteInvalidated(event.data)) return null;
  const constraints = event.data.constraints ?? [];
  return (
    <article
      style={{
        background: t.color.bg.panel,
        border: `1px solid ${t.color.severity.critical}55`,
        borderLeft: `3px solid ${t.color.severity.critical}`,
        borderRadius: t.radius.md,
        padding: t.space[3],
        display: "grid",
        gap: t.space[2],
      }}
    >
      <header style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: t.space[2] }}>
        <code style={{ fontSize: t.font.size.sm, color: t.color.text.primary }}>{event.data.proposal_id}</code>
        <Badge tone="severity" severity="critical">
          Scartato
        </Badge>
      </header>
      <p style={{ margin: 0, fontSize: t.font.size.base, color: t.color.text.secondary }}>{event.data.reason}</p>
      {constraints.length > 0 ? (
        <ul style={{ margin: 0, paddingLeft: t.space[4], display: "grid", gap: t.space[1] }}>
          {constraints.map((constraint, index) => (
            <li key={`${event.data.proposal_id}-c-${index}`} style={{ fontSize: t.font.size.sm, color: t.color.text.muted }}>
              {constraint.kind} · {constraint.applies_at} · {constraint.description}
            </li>
          ))}
        </ul>
      ) : null}
      <span style={{ fontSize: t.font.size.xs, color: t.color.text.muted }}>
        seq #{event.seq} · validato da {event.agent ?? "incidents"}
      </span>
    </article>
  );
}
