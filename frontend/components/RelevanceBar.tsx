"use client";

import type { Contribution, ScoredItem } from "@/lib/contracts";
import { formatScore } from "@/lib/format";
import { ContributionList } from "./ContributionList";

const SEGMENT_COLORS = ["#4FB3D9", "#5B8C6E", "#C79A3A", "#D06A32"];

type RelevanceBarProps = {
  scoredItem: ScoredItem;
  rounding: number;
};

export function RelevanceBar({ scoredItem, rounding }: RelevanceBarProps) {
  return (
    <div className="space-y-2" data-testid={`relevance-bar-${scoredItem.plan_index}`}>
      <div className="flex items-center justify-between text-[13px]">
        <span className="text-[11px] font-medium uppercase tracking-wider text-[var(--text-muted)]">
          Relevance
        </span>
        <code className="font-mono text-[13px] font-medium text-[var(--text)]">
          {formatScore(scoredItem.score, rounding)}
        </code>
      </div>

      {/* Segmented bar using backend-provided contribution values only (FE-REQ-05) */}
      <div
        className="flex h-2.5 w-full overflow-hidden rounded-[6px] border border-[var(--border)] bg-[var(--bg)]"
        role="img"
        aria-label={`Relevance score ${formatScore(scoredItem.score, rounding)}`}
      >
        {scoredItem.contributions.map((c: Contribution, i: number) => {
          const widthPct = Math.max(0, Math.min(100, c.contribution * 100));
          return (
            <div
              key={`${c.feature}-${i}`}
              title={`${c.feature}: ${formatScore(c.contribution, rounding)}`}
              style={{
                width: `${widthPct}%`,
                backgroundColor: SEGMENT_COLORS[i % SEGMENT_COLORS.length],
              }}
            />
          );
        })}
      </div>

      <ContributionList contributions={scoredItem.contributions} rounding={rounding} />
    </div>
  );
}
