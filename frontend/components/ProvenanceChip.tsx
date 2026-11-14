"use client";

import clsx from "clsx";
import { getDict, type Locale } from "@/lib/i18n";

export type ProvenanceVariant = "real" | "simulated" | "unavailable";

type ProvenanceChipProps = {
  variant: ProvenanceVariant;
  locale?: Locale;
  className?: string;
};

export function ProvenanceChip({ variant, locale = "it", className }: ProvenanceChipProps) {
  const d = getDict(locale);

  if (variant === "real") {
    return (
      <span
        className={clsx("inline-flex items-center gap-1.5", className)}
        aria-label={d.provenance.real}
        title={d.provenance.real}
        data-provenance="real"
      >
        <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true" className="shrink-0">
          <circle cx="5" cy="5" r="4" fill="#5B8C6E" />
        </svg>
        <span className="sr-only">{d.provenance.real}</span>
      </span>
    );
  }

  if (variant === "simulated") {
    return (
      <span
        className={clsx(
          "inline-flex items-center gap-1.5 rounded-[6px] border border-dashed border-[var(--border)] px-2 py-0.5 text-[11px] font-medium uppercase tracking-wider text-[var(--text-muted)]",
          className,
        )}
        data-provenance="simulated"
      >
        <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true" className="shrink-0">
          <circle cx="5" cy="5" r="3.5" fill="none" stroke="currentColor" strokeWidth="1.5" />
        </svg>
        <span>{d.provenance.simulated}</span>
      </span>
    );
  }

  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1.5 rounded-[6px] border border-dashed border-[var(--border)] px-2 py-0.5 text-[11px] font-medium uppercase tracking-wider text-[var(--text-muted)]",
        className,
      )}
      data-provenance="unavailable"
    >
      <svg width="10" height="10" viewBox="0 0 10 10" aria-hidden="true" className="shrink-0">
        <line
          x1="1.5"
          y1="5"
          x2="8.5"
          y2="5"
          stroke="currentColor"
          strokeWidth="1.75"
          strokeLinecap="round"
        />
      </svg>
      <span>{d.provenance.unavailable}</span>
    </span>
  );
}

export function TemplateTextChip({
  locale = "it",
  className,
}: {
  locale?: Locale;
  className?: string;
}) {
  const d = getDict(locale);
  return (
    <span
      className={clsx(
        "inline-flex items-center rounded-[6px] border border-dashed border-[var(--border)] px-2 py-0.5 text-[11px] font-medium uppercase tracking-wider text-[var(--text-muted)]",
        className,
      )}
      data-narrative-mode="template"
    >
      {d.provenance.templateText}
    </span>
  );
}
