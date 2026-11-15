/**
 * @purpose Raggruppamento dei PlanItem per destinatario con ordinamento per priorità
 * @contracts PlanItem, Target
 * @tokens operator
 * @verified 2026-11-15
 */

import { operatorTokens as t } from "@/styles/design-tokens-operator";
import type { PlanItem, Target } from "@/lib/types/contracts";
import { PlanCard } from "./PlanCard";

const TARGET_LABEL: Record<Target, string> = {
  operator: "Operatore",
  tourist: "Turista",
  citizen: "Cittadino",
};

export function TargetGroup({
  target,
  items,
}: {
  target: Target;
  items: Array<{ item: PlanItem; index: number }>;
}) {
  if (items.length === 0) return null;
  const color = t.color.target[target];
  return (
    <section style={{ display: "grid", gap: t.space[2] }} aria-label={`Azioni per ${TARGET_LABEL[target]}`}>
      <h3
        style={{
          margin: 0,
          fontSize: t.font.size.xs,
          textTransform: "uppercase",
          letterSpacing: "0.12em",
          color,
          fontWeight: t.font.weight.semibold,
        }}
      >
        {TARGET_LABEL[target]} · {items.length}
      </h3>
      {items
        .slice()
        .sort((a, b) => a.item.priority - b.item.priority)
        .map(({ item, index }) => (
          <PlanCard key={`${target}-${index}`} item={item} index={index} />
        ))}
    </section>
  );
}
