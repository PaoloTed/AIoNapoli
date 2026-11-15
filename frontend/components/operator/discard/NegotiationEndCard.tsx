/**
 * @purpose Scheda conclusiva del ciclo di negoziazione
 * @contracts NegotiationFinishedData, TraceEvent
 * @tokens operator
 * @verified 2026-11-15
 */

import { operatorTokens as t } from "@/styles/design-tokens-operator";
import { Badge } from "@/components/ui/Badge";
import { isNegotiationFinished } from "@/lib/types/trace";
import type { TraceEvent } from "@/lib/types/trace";

const OUTCOME_LABEL: Record<string, string> = {
  agreement: "Accordo raggiunto",
  exhausted: "Turni esauriti",
  uncertain: "Esito incerto",
  timeout: "Timeout",
};

export function NegotiationEndCard({ event }: { event: TraceEvent }) {
  if (!isNegotiationFinished(event.data)) return null;
  const agreement = event.data.agreement;
  const color = agreement ? t.color.severity.low : t.color.severity.medium;
  return (
    <article
      style={{
        background: `${color}12`,
        border: `1px solid ${color}66`,
        borderRadius: t.radius.md,
        padding: t.space[3],
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: t.space[3],
        flexWrap: "wrap",
      }}
    >
      <div>
        <strong style={{ fontSize: t.font.size.md, color: t.color.text.primary }}>
          {OUTCOME_LABEL[event.data.outcome] ?? event.data.outcome}
        </strong>
        <p style={{ margin: 0, fontSize: t.font.size.sm, color: t.color.text.secondary }}>
          Iterazioni: {event.data.iterations} · seq #{event.seq}
        </p>
      </div>
      <Badge tone="severity" severity={agreement ? "low" : "medium"}>
        {agreement ? "Agreement" : "No agreement"}
      </Badge>
    </article>
  );
}
