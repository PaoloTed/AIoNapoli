"use client";

import clsx from "clsx";
import type { RuleEvaluatedPayload } from "@/lib/contracts";
import { getDict, type Locale } from "@/lib/i18n";

type RuleRowProps = {
  rule: RuleEvaluatedPayload;
  locale?: Locale;
};

export function RuleRow({ rule, locale = "it" }: RuleRowProps) {
  const d = getDict(locale);

  return (
    <li
      className={clsx(
        "rounded-[6px] border px-3 py-2.5 space-y-1 transition-opacity duration-200 motion-reduce:transition-none",
        rule.fired
          ? "border-[var(--accent)] bg-[var(--accent-soft)]"
          : "border-[var(--border)] bg-[var(--bg)]",
      )}
      data-testid={`rule-row-${rule.rule_id}`}
      data-rule-fired={rule.fired ? "true" : "false"}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true" className="shrink-0">
            {rule.fired ? (
              <circle cx="6" cy="6" r="4.5" fill="var(--accent)" />
            ) : (
              <circle
                cx="6"
                cy="6"
                r="4"
                fill="none"
                stroke="var(--text-muted)"
                strokeWidth="1.5"
              />
            )}
          </svg>
          <code className="font-mono text-[13px] font-medium text-[var(--text)]">
            {rule.rule_id}
          </code>
          <span className="text-[11px] font-medium uppercase tracking-wider text-[var(--text-muted)]">
            {rule.agents.join(" + ")}
          </span>
        </div>

        <span
          className={clsx(
            "rounded-[6px] border px-2 py-0.5 text-[11px] font-medium uppercase tracking-wider",
            rule.fired
              ? "border-[var(--accent)] text-[var(--accent)]"
              : "border-[var(--border)] text-[var(--text-muted)]",
          )}
        >
          {rule.fired ? d.operator.ruleFired : d.operator.ruleNotFired}
        </span>
      </div>

      {/* Reason is always shown, including when fired=false (FE-REQ-15) */}
      <p className="text-[14px] text-[var(--text)]">{rule.reason}</p>
    </li>
  );
}
