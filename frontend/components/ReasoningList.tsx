"use client";

import type { ReasoningStep } from "@/lib/contracts";
import { getDict, type Locale } from "@/lib/i18n";

type ReasoningListProps = {
  steps: ReasoningStep[];
  locale?: Locale;
};

// Operator-only component (FE-REQ-21)
export function ReasoningList({ steps, locale = "it" }: ReasoningListProps) {
  const d = getDict(locale);

  return (
    <section
      className="rounded-[10px] border border-[var(--border)] bg-[var(--surface)] p-4 space-y-3"
      data-testid="reasoning-list"
    >
      <h3 className="text-[11px] font-medium uppercase tracking-wider text-[var(--text-muted)]">
        {d.operator.reasoningTitle}
      </h3>

      <ol className="space-y-2">
        {steps.map((step) => (
          <li
            key={step.step}
            className="rounded-[6px] border border-[var(--border)] bg-[var(--bg)] px-3 py-2.5 space-y-1"
          >
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-mono text-[12px] text-[var(--text-muted)]">#{step.step}</span>
                <span className="text-[11px] font-medium uppercase tracking-wider text-[var(--accent)]">
                  {step.agent}
                </span>
                <code className="font-mono text-[13px] text-[var(--text)]">
                  {step.rule_applied}
                </code>
              </div>

              <code className="font-mono text-[12px] text-[var(--text-muted)]">
                ref:{step.finding_ref}
              </code>
            </div>
            <p className="text-[14px] text-[var(--text)]">{step.outcome}</p>
          </li>
        ))}
      </ol>
    </section>
  );
}
