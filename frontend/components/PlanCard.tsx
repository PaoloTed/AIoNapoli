"use client";

import { useState } from "react";
import type { NarrativeItem, PlanItem, ScoredItem } from "@/lib/contracts";
import type { Locale } from "@/lib/format";
import { TemplateTextChip } from "./ProvenanceChip";
import { RelevanceBar } from "./RelevanceBar";

type PlanCardProps = {
  item: PlanItem;
  narrativeItem?: NarrativeItem | undefined;
  narrativeMode: "replay" | "live" | "off";
  scoredItem?: ScoredItem | undefined;
  rounding: number;
  showRationale?: boolean;
  locale?: Locale;
};

export function PlanCard({
  item,
  narrativeItem,
  narrativeMode,
  scoredItem,
  rounding,
  showRationale = true,
  locale = "it",
}: PlanCardProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    if (typeof navigator !== "undefined" && navigator.clipboard) {
      navigator.clipboard.writeText(item.action);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    }
  };

  const narrativeText = narrativeItem
    ? locale === "en" && narrativeItem.texts.en
      ? narrativeItem.texts.en
      : narrativeItem.texts.it
    : undefined;

  return (
    <article
      className="rounded-[10px] border border-[var(--border)] bg-[var(--surface)] p-4 space-y-3"
      data-testid={`plan-card-${item.target}`}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="rounded-[6px] border border-[var(--border)] bg-[var(--bg)] px-2 py-0.5 font-mono text-[12px] text-[var(--text)]">
            #{item.priority}
          </span>
          <button
            type="button"
            onClick={handleCopy}
            className="rounded-[4px] px-1.5 py-0.5 font-mono text-[10px] text-[var(--text-muted)] hover:text-[var(--text)] hover:bg-[var(--bg)] transition-colors cursor-pointer"
            title="Copia testo dell'azione"
          >
            {copied ? "Copiato!" : "Copia"}
          </button>
        </div>

        {narrativeMode !== "live" && <TemplateTextChip locale={locale} />}
      </div>

      <p className="text-[15px] font-medium text-[var(--text)]">{item.action}</p>

      {narrativeText && (
        <p
          lang={locale === "en" && narrativeItem?.texts.en ? "en" : "it"}
          className="text-[14px] text-[var(--text-muted)] border-l-2 border-[var(--accent)] pl-3"
        >
          {narrativeText}
        </p>
      )}

      {showRationale && <p className="text-[13px] text-[var(--text-muted)]">{item.rationale}</p>}

      {scoredItem && (
        <div className="border-t border-[var(--border)] pt-2.5">
          <RelevanceBar scoredItem={scoredItem} rounding={rounding} />
        </div>
      )}
    </article>
  );
}
