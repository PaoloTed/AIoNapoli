/**
 * @purpose Scheda Decisione: piano per target e timeline di reasoning
 * @contracts DecisionResponse, PlanItem
 * @tokens operator
 * @verified 2026-11-15
 */

"use client";

import { useMemo, useState } from "react";
import { useAppStore } from "@/lib/state/store";
import { DecisionMeta } from "@/components/operator/decision/DecisionMeta";
import { TargetGroup } from "@/components/operator/decision/TargetGroup";
import { ReasoningTimeline } from "@/components/operator/decision/ReasoningTimeline";
import { ReasoningFilter } from "@/components/operator/decision/ReasoningFilter";
import { isDecisive } from "@/components/operator/decision/ReasoningStep";
import { EmptyState } from "@/components/ui/EmptyState";
import type { Target } from "@/lib/types/contracts";

const TARGETS: Target[] = ["operator", "citizen", "tourist"];

export default function DecisionPage() {
  const { decision } = useAppStore();
  const [decisiveOnly, setDecisiveOnly] = useState(false);

  const groups = useMemo(() => {
    const plan = decision?.decision.plan ?? [];
    return TARGETS.map((target) => ({
      target,
      items: plan
        .map((item, index) => ({ item, index }))
        .filter((entry) => entry.item.target === target),
    }));
  }, [decision]);

  const reasoning = decision?.decision.reasoning_log ?? [];
  const visibleSteps = decisiveOnly ? reasoning.filter(isDecisive) : reasoning;

  if (!decision) {
    return (
      <EmptyState
        title="Decisione non disponibile"
        description="Il motore non ha ancora prodotto una decisione per lo scenario corrente."
      />
    );
  }

  return (
    <div style={{ display: "grid", gap: "16px" }}>
      <DecisionMeta payload={decision} />
      <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 6fr) minmax(340px, 4fr)", gap: "16px" }}>
        <section aria-label="Piano d'azione" style={{ display: "grid", gap: "16px", alignContent: "start" }}>
          {groups.map((group) => (
            <TargetGroup key={group.target} target={group.target} items={group.items} />
          ))}
        </section>
        <div style={{ display: "grid", gap: "12px", alignContent: "start" }}>
          <ReasoningFilter
            decisiveOnly={decisiveOnly}
            onChange={setDecisiveOnly}
            total={reasoning.length}
            decisive={reasoning.filter(isDecisive).length}
          />
          <ReasoningTimeline steps={visibleSteps} />
        </div>
      </div>
    </div>
  );
}
