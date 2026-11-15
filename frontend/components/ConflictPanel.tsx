"use client";

import type { Conflict, Trigger } from "@/lib/contracts";
import type { Locale } from "@/lib/format";
import { getDict } from "@/lib/i18n";
import { NoRulesBanner } from "./states/DegradedBanner";

export type ConflictPanelProps = {
  conflict: Conflict;
  trigger?: Trigger | undefined;
  locale?: Locale;
};

export function ConflictPanel({ conflict, trigger, locale = "it" }: ConflictPanelProps) {
  const d = getDict(locale);

  if (!conflict.detected) {
    return (
      <div data-testid="no-conflict-panel">
        <NoRulesBanner description={conflict.description} locale={locale} />
      </div>
    );
  }

  return (
    <section
      className="rounded-[10px] border border-[#D06A32] bg-[var(--surface)] p-4 space-y-3"
      data-testid="conflict-panel"
      aria-label={d.operator.conflictDetected}
    >
      <div
        className="rounded-[6px] border border-[#D06A32] bg-[var(--bg)] px-3.5 py-2.5 space-y-2"
        data-testid="conflict-box"
      >
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <svg
              width="14"
              height="14"
              viewBox="0 0 12 12"
              aria-hidden="true"
              className="shrink-0 text-[#D06A32]"
            >
              <polygon points="6,2 10.5,10 1.5,10" fill="currentColor" />
            </svg>
            <span className="text-[11px] font-medium uppercase tracking-wider text-[#D06A32]">
              {d.operator.conflictDetected}
            </span>
          </div>

          {trigger && (
            <div className="flex items-center gap-1.5">
              <span className="text-[11px] font-medium uppercase tracking-wider text-[var(--text-muted)]">
                Regola scatenante:
              </span>
              <code className="rounded-[4px] border border-[var(--border)] bg-[var(--surface)] px-2 py-0.5 font-mono text-[12px] font-semibold text-[var(--accent)]">
                {trigger.rule_id}
              </code>
            </div>
          )}
        </div>

        <p className="text-[15px] font-medium text-[var(--text)] leading-snug">
          {conflict.description}
        </p>

        {trigger && trigger.agents_involved.length > 0 && (
          <div className="flex flex-wrap items-center gap-2 pt-1 border-t border-[var(--border)] text-[12px] text-[var(--text-muted)]">
            <span className="text-[11px] font-medium uppercase tracking-wider">
              Agenti in conflitto:
            </span>
            <div className="flex flex-wrap gap-1.5">
              {trigger.agents_involved.map((ag) => (
                <span
                  key={ag}
                  className="rounded-[4px] border border-[var(--border)] bg-[var(--surface)] px-2 py-0.5 font-mono text-[11px] text-[var(--text)]"
                >
                  {ag}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      <p className="text-[12px] text-[var(--text-muted)]">
        Risoluzione deterministica applicata: priorità di sicurezza e deflusso conformi al regolamento della trace.
      </p>
    </section>
  );
}
