"use client";

import type { Contribution } from "@/lib/contracts";
import { formatScore } from "@/lib/format";

type ContributionListProps = {
  contributions: Contribution[];
  rounding: number;
};

export function ContributionList({ contributions, rounding }: ContributionListProps) {
  if (contributions.length === 0) return null;

  return (
    <ul className="space-y-1 text-[13px]" data-testid="contribution-list">
      {contributions.map((item) => (
        <li
          key={item.feature}
          className="flex flex-wrap items-center justify-between gap-2 rounded-[6px] bg-[var(--bg)] px-2.5 py-1"
        >
          <code className="font-mono text-[12px] text-[var(--text)]">{item.feature}</code>
          <span className="font-mono text-[12px] text-[var(--text-muted)]">
            {item.value} × {item.weight} ={" "}
            <strong className="font-medium text-[var(--text)]">
              {formatScore(item.contribution, rounding)}
            </strong>
          </span>
        </li>
      ))}
    </ul>
  );
}
