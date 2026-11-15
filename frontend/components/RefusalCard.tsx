"use client";

import type { AgentName, Refusal } from "@/lib/contracts";
import type { Locale } from "@/lib/format";
import { getDict } from "@/lib/i18n";
import { ProvenanceChip } from "./ProvenanceChip";

export type RefusalCardProps = {
  agent: AgentName;
  refusal: Refusal;
  locale?: Locale;
  onClick?: () => void;
  isSelected?: boolean;
};

export function RefusalCard({
  agent,
  refusal,
  locale = "it",
  onClick,
  isSelected = false,
}: RefusalCardProps) {
  const d = getDict(locale);
  const agentLabel = d.agents[agent];

  return (
    <article
      onClick={onClick}
      className={`rounded-[10px] border border-dashed border-[var(--border)] bg-[var(--surface)] p-4 space-y-2.5 transition-colors duration-120 ${
        onClick ? "cursor-pointer hover:border-[#D06A32]" : ""
      } ${isSelected ? "ring-2 ring-[#D06A32]" : ""}`}
      data-testid={`refusal-card-${agent}`}
      data-finding-state="refusal"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-medium uppercase tracking-wider text-[var(--text-muted)]">
            {agentLabel}
          </span>
          <code className="rounded-[4px] border border-[var(--border)] bg-[var(--bg)] px-1.5 py-0.5 font-mono text-[12px] text-[#D06A32]">
            RIFIUTO AGENTE
          </code>
        </div>
        <ProvenanceChip variant="unavailable" locale={locale} />
      </div>

      <div className="space-y-1">
        <p className="text-[14px] font-medium text-[var(--text)]">
          {d.states.agentRefusal}: nessun dato generato
        </p>
        <p className="text-[13px] text-[var(--text-muted)]">
          L&apos;agente ha sospeso la valutazione per assenza di ingressi verificabili. Nessun dato sintetico dedotto lato client (FE-REQ-07, FE-REQ-20).
        </p>
      </div>

      <div className="rounded-[6px] border border-[var(--border)] bg-[var(--bg)] p-2.5 space-y-1.5 text-[13px]">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-[11px] font-medium uppercase tracking-wider text-[var(--text-muted)]">
            reason_code:
          </span>
          <code className="font-mono font-semibold text-[var(--text)]">
            {refusal.reason_code}
          </code>
        </div>

        {refusal.missing_input && refusal.missing_input.length > 0 && (
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[11px] font-medium uppercase tracking-wider text-[var(--text-muted)]">
              input mancanti:
            </span>
            <div className="flex flex-wrap gap-1">
              {refusal.missing_input.map((inp) => (
                <code
                  key={inp}
                  className="rounded-[4px] bg-[var(--surface)] px-1.5 py-0.5 font-mono text-[11px] text-[var(--text-muted)] border border-[var(--border)]"
                >
                  {inp}
                </code>
              ))}
            </div>
          </div>
        )}

        {refusal.detail && (
          <p className="text-[12px] text-[var(--text-muted)] border-t border-[var(--border)] pt-1 mt-1">
            {refusal.detail}
          </p>
        )}
      </div>
    </article>
  );
}
