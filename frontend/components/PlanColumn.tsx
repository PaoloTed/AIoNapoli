"use client";

import { clsx } from "clsx";
import type { Narrative, PlanItem, PlanTarget, ScoredItem, TargetRelevance } from "@/lib/contracts";
import type { Locale } from "@/lib/format";
import { getDict } from "@/lib/i18n";
import { PlanCard } from "./PlanCard";

type PlanColumnProps = {
  target: PlanTarget;
  plan: PlanItem[];
  targetRelevance: TargetRelevance;
  rounding: number;
  narrative: Narrative;
  locale?: Locale;
  className?: string | undefined;
};

export function PlanColumn({
  target,
  plan,
  targetRelevance,
  rounding,
  narrative,
  locale = "it",
  className,
}: PlanColumnProps) {
  const d = getDict(locale);

  // Follow backend relevance.targets[target].order strictly without re-sorting (FE-REQ-05, FE-REQ-22)
  const orderedIndices =
    targetRelevance.order.length > 0
      ? targetRelevance.order.filter((idx) => plan[idx]?.target === target)
      : plan.map((item, idx) => (item.target === target ? idx : -1)).filter((idx) => idx >= 0);

  const scoredMap = new Map<number, ScoredItem>();
  for (const s of targetRelevance.items) {
    scoredMap.set(s.plan_index, s);
  }

  const narrativeMap = new Map(narrative.items.map((n) => [n.plan_index, n]));

  return (
    <section
      className={clsx("space-y-3", className)}
      data-testid={`plan-column-${target}`}
      aria-label={d.targets[target]}
    >
      <header className="flex items-center justify-between border-b border-[var(--border)] pb-2">
        <h3 className="text-[11px] font-medium uppercase tracking-wider text-[var(--text-muted)]">
          {d.targets[target]}
        </h3>
        <span className="font-mono text-[12px] text-[var(--text-muted)]">
          {orderedIndices.length}
        </span>
      </header>

      <div className="space-y-3">
        {orderedIndices.map((planIdx) => {
          const item = plan[planIdx];
          if (!item) return null;
          return (
            <PlanCard
              key={`${target}-${planIdx}`}
              item={item}
              narrativeItem={narrativeMap.get(planIdx)}
              narrativeMode={narrative.mode}
              scoredItem={scoredMap.get(planIdx)}
              rounding={rounding}
              showRationale
              locale={locale}
            />
          );
        })}
      </div>
    </section>
  );
}
