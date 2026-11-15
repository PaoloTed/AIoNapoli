"use client";

import type { Decision } from "@/lib/contracts";

export type DiscardRecalcPanelProps = {
  decision: Decision;
  locale?: string;
};

export function DiscardRecalcPanel({ decision }: DiscardRecalcPanelProps) {
  const hasConflict = decision.conflict.detected;
  const reasoningSteps = decision.reasoning_log;

  // Find step with conflict or priority applied
  const conflictStep = reasoningSteps.find(
    (s) => s.outcome.toLowerCase().includes("priorita") || s.rule_applied.includes("R"),
  );

  return (
    <section
      className="rounded-[10px] border border-[var(--border)] bg-[var(--surface)] p-4 space-y-3"
      data-testid="discard-recalc-panel"
      aria-label="Scarto e Ricalcolo"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-medium uppercase tracking-wider text-[var(--accent)]">
            Scarto e Ricalcolo
          </span>
          <span className="rounded-[4px] border border-[var(--border)] bg-[var(--bg)] px-2 py-0.5 font-mono text-[11px] text-[var(--text-muted)]">
            Trace deterministica
          </span>
        </div>
        <span className="font-mono text-[12px] text-[var(--text-muted)]">
          {reasoningSteps.length} passi valutati
        </span>
      </div>

      {hasConflict ? (
        <div className="space-y-3">
          <div className="grid gap-3 sm:grid-cols-2">
            {/* Scarto */}
            <div className="rounded-[6px] border border-[#C2382F]/50 bg-[var(--bg)] p-3 space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-medium uppercase tracking-wider text-[#C2382F]">
                  Opzione scartata
                </span>
                <code className="font-mono text-[11px] text-[var(--text-muted)]">
                  {decision.trigger.rule_id}
                </code>
              </div>
              <p className="text-[14px] font-medium text-[var(--text)] line-through opacity-85">
                Instradamento standard ad alta frequenza sulla tratta critica
              </p>
              <p className="text-[12px] text-[var(--text-muted)]">
                Motivo: {decision.conflict.description}
              </p>
            </div>

            {/* Ricalcolo */}
            <div className="rounded-[6px] border border-[#5B8C6E]/60 bg-[var(--bg)] p-3 space-y-1.5">
              <div className="flex items-center justify-between">
                <span className="text-[11px] font-medium uppercase tracking-wider text-[#5B8C6E]">
                  Ricalcolo vincente
                </span>
                <span className="rounded-[4px] bg-[#5B8C6E]/15 px-1.5 py-0.5 text-[10px] font-semibold text-[#5B8C6E]">
                  ADOTTATO
                </span>
              </div>
              <p className="text-[14px] font-medium text-[var(--text)]">
                {decision.plan[0]?.action ?? "Piano di deflusso e ripartizione carico alternativo"}
              </p>
              <p className="text-[12px] text-[var(--text-muted)]">
                Risoluzione: {conflictStep ? conflictStep.outcome : "ottimizzazione su vincolo di sicurezza"}
              </p>
            </div>
          </div>

          <div className="rounded-[4px] bg-[var(--bg)] p-2 text-[11px] text-[var(--text-muted)] border border-[var(--border)]">
            <span className="font-semibold">Nota di contratto:</span> Il ciclo di negoziazione multi-round non espone payload di bozze scartate nel contratto v1.0.0; lo scarto è documentato dal reasoning log della trace (FE-REQ-14, FE-REQ-16).
          </div>
        </div>
      ) : (
        <div className="rounded-[6px] border border-[var(--border)] bg-[var(--bg)] p-3 text-[13px] text-[var(--text-muted)]">
          Nessuno scarto necessario: tutte le condizioni operative rientrano nei limiti nominali.
        </div>
      )}
    </section>
  );
}
