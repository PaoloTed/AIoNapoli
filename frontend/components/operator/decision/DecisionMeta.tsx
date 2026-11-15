/**
 * @purpose Barra metadati della decisione con id, versione, timestamp e confidenza
 * @contracts DecisionResponse
 * @tokens operator
 * @verified 2026-11-15
 */

import { operatorTokens as t } from "@/styles/design-tokens-operator";
import { Badge } from "@/components/ui/Badge";
import { formatPercent, formatRomeDateTime } from "@/lib/format";
import type { DecisionResponse } from "@/lib/types/contracts";

export function DecisionMeta({ payload }: { payload: DecisionResponse }) {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: t.space[4],
        background: t.color.bg.panel,
        border: `1px solid ${t.color.border.subtle}`,
        borderRadius: t.radius.md,
        padding: `${t.space[2]} ${t.space[4]}`,
        flexWrap: "wrap",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: t.space[3], flexWrap: "wrap" }}>
        <code style={{ fontSize: t.font.size.md, color: t.color.accent.primary }}>{payload.decision_id}</code>
        <span style={{ fontSize: t.font.size.xs, color: t.color.text.muted }}>
          contratto v{payload.contract_version}
        </span>
        <span style={{ fontSize: t.font.size.xs, color: t.color.text.muted }}>
          {formatRomeDateTime(payload.decision.timestamp)}
        </span>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: t.space[2] }}>
        <Badge tone="accent">{payload.decision.trigger.rule_id}</Badge>
        <Badge tone="severity" severity={payload.decision.confidence >= 0.8 ? "low" : "medium"}>
          confidenza {formatPercent(payload.decision.confidence)}
        </Badge>
      </div>
    </div>
  );
}
