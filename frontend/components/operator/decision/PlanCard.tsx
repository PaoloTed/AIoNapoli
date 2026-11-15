/**
 * @purpose Scheda operativa di un PlanItem con priorità, azione e motivazione
 * @contracts PlanItem
 * @tokens operator
 * @verified 2026-11-15
 */

import { operatorTokens as t } from "@/styles/design-tokens-operator";
import { Badge } from "@/components/ui/Badge";
import type { PlanItem } from "@/lib/types/contracts";

export function PlanCard({ item, index }: { item: PlanItem; index: number }) {
  const accent = t.color.target[item.target];
  return (
    <article
      id={`plan-${index}`}
      style={{
        display: "grid",
        gridTemplateColumns: "44px minmax(0, 1fr)",
        gap: t.space[3],
        background: t.color.bg.panel,
        border: `1px solid ${t.color.border.subtle}`,
        borderLeft: `3px solid ${accent}`,
        borderRadius: t.radius.md,
        padding: t.space[3],
      }}
    >
      <div
        aria-hidden="true"
        style={{
          width: "40px",
          height: "40px",
          borderRadius: t.radius.sm,
          background: `${accent}22`,
          color: accent,
          display: "grid",
          placeItems: "center",
          fontSize: t.font.size.lg,
          fontWeight: t.font.weight.bold,
        }}
      >
        {item.priority}
      </div>
      <div style={{ display: "grid", gap: t.space[1] }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: t.space[2] }}>
          <strong style={{ fontSize: t.font.size.md, color: t.color.text.primary }}>{item.action}</strong>
          <Badge tone="target" target={item.target}>
            {item.target}
          </Badge>
        </div>
        <p style={{ margin: 0, fontSize: t.font.size.base, color: t.color.text.secondary }}>{item.rationale}</p>
      </div>
    </article>
  );
}
