"use client";

import { useMemo } from "react";
import type { PlanItem, RelevanceScore } from "@/lib/contracts";

export type RelevanceDivergencePanelProps = {
  relevance: RelevanceScore;
  plan?: PlanItem[];
  locale?: string;
};

// Calculates pairwise order inversion count between two targets (ricerca1/07_misure_e_numeri.md §4)
export function computeOrderInversions(orderA: number[], orderB: number[]): number {
  // Only compare items that belong to both order lists
  const commonIndices = orderA.filter((idx) => orderB.includes(idx));
  if (commonIndices.length < 2) return 0;

  let inversions = 0;
  for (let i = 0; i < commonIndices.length; i++) {
    for (let j = i + 1; j < commonIndices.length; j++) {
      const item1 = commonIndices[i];
      const item2 = commonIndices[j];
      if (item1 === undefined || item2 === undefined) continue;

      const posA1 = orderA.indexOf(item1);
      const posA2 = orderA.indexOf(item2);
      const posB1 = orderB.indexOf(item1);
      const posB2 = orderB.indexOf(item2);

      const signA = Math.sign(posA1 - posA2);
      const signB = Math.sign(posB1 - posB2);
      if (signA !== 0 && signB !== 0 && signA !== signB) {
        inversions++;
      }
    }
  }
  return inversions;
}

export function RelevanceDivergencePanel({ relevance }: RelevanceDivergencePanelProps) {
  const divergenceOpTour = useMemo(() => {
    const orderOp = relevance.targets.operator?.order ?? [];
    const orderTour = relevance.targets.tourist?.order ?? [];
    return computeOrderInversions(orderOp, orderTour);
  }, [relevance.targets]);

  const divergenceTourCit = useMemo(() => {
    const orderTour = relevance.targets.tourist?.order ?? [];
    const orderCit = relevance.targets.citizen?.order ?? [];
    return computeOrderInversions(orderTour, orderCit);
  }, [relevance.targets]);

  return (
    <section
      className="rounded-[10px] border border-[var(--border)] bg-[var(--surface)] p-4 space-y-3"
      data-testid="relevance-divergence-panel"
      aria-label="Scomposizione della Rilevanza e Scarto fra Destinatari"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-medium uppercase tracking-wider text-[var(--accent)]">
            Rilevanza Scomposta
          </span>
          <span className="rounded-[4px] border border-[var(--border)] bg-[var(--bg)] px-2 py-0.5 font-mono text-[11px] text-[var(--text-muted)]">
            Scarto fra ordinamenti
          </span>
        </div>
        <span className="font-mono text-[12px] text-[var(--text-muted)]">
          Pesi indipendenti per target
        </span>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <div className="rounded-[6px] border border-[var(--border)] bg-[var(--bg)] p-3 space-y-1">
          <p className="text-[11px] font-medium uppercase tracking-wider text-[var(--text-muted)]">
            Divergenza Turista ↔ Operatore
          </p>
          <div className="flex items-baseline gap-2">
            <span className="font-mono text-[20px] font-bold text-[var(--text)]" data-testid="divergence-op-tour">
              {divergenceOpTour}
            </span>
            <span className="text-[12px] text-[var(--text-muted)]">
              {divergenceOpTour === 1 ? "inversione di priorità" : "inversioni di priorità"}
            </span>
          </div>
          <p className="text-[11px] text-[var(--text-muted)]">
            La guida turista riordina privilegiando tempo di percorrenza e orientamento immediato.
          </p>
        </div>

        <div className="rounded-[6px] border border-[var(--border)] bg-[var(--bg)] p-3 space-y-1">
          <p className="text-[11px] font-medium uppercase tracking-wider text-[var(--text-muted)]">
            Divergenza Cittadino ↔ Turista
          </p>
          <div className="flex items-baseline gap-2">
            <span className="font-mono text-[20px] font-bold text-[var(--text)]" data-testid="divergence-tour-cit">
              {divergenceTourCit}
            </span>
            <span className="text-[12px] text-[var(--text-muted)]">
              {divergenceTourCit === 1 ? "inversione di priorità" : "inversioni di priorità"}
            </span>
          </div>
          <p className="text-[11px] text-[var(--text-muted)]">
            La vista cittadino privilegia regolarità del trasporto pubblico e affollamento di banchina.
          </p>
        </div>
      </div>

      <p className="text-[12px] text-[var(--text-muted)] border-t border-[var(--border)] pt-2">
        <strong className="text-[var(--text)]">Metodo verificabile (FE-REQ-22):</strong> La personalizzazione per target non è una manipolazione di testo; è un calcolo matematico deterministico sui pesi delle feature, esposto qui e verificabile.
      </p>
    </section>
  );
}
