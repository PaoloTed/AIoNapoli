/**
 * @purpose Timeline verticale del reasoning_log
 * @contracts ReasoningStep
 * @tokens operator
 * @verified 2026-11-15
 */

import { operatorTokens as t } from "@/styles/design-tokens-operator";
import type { ReasoningStep as ReasoningStepModel } from "@/lib/types/contracts";
import { ReasoningStep } from "./ReasoningStep";

export function ReasoningTimeline({ steps }: { steps: ReasoningStepModel[] }) {
  return (
    <section aria-label="Timeline del ragionamento" aria-live="polite" style={{ display: "grid", gap: t.space[2] }}>
      <h2 style={{ margin: 0, fontSize: t.font.size.lg, fontWeight: t.font.weight.semibold }}>
        Reasoning Timeline
      </h2>
      <ol style={{ margin: 0, padding: 0 }}>
        {steps.map((step, index) => (
          <ReasoningStep key={step.step} step={step} last={index === steps.length - 1} />
        ))}
      </ol>
    </section>
  );
}
