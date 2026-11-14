"use client";

import clsx from "clsx";
import type { Severity } from "@/lib/contracts";
import { severityText, type Locale } from "@/lib/format";

type SeverityBadgeProps = {
  severity: Severity;
  locale?: Locale;
  className?: string;
};

const SEVERITY_COLOR: Record<Severity, string> = {
  low: "#5B8C6E",
  medium: "#C79A3A",
  high: "#D06A32",
  critical: "#C2382F",
};

export function SeverityBadge({ severity, locale = "it", className }: SeverityBadgeProps) {
  const color = SEVERITY_COLOR[severity];
  const label = severityText(severity, locale);

  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1.5 rounded-[6px] border border-[var(--border)] px-2 py-0.5 text-[11px] font-medium uppercase tracking-wider text-[var(--text)]",
        className,
      )}
      data-severity={severity}
    >
      <svg
        width="12"
        height="12"
        viewBox="0 0 12 12"
        aria-hidden="true"
        className="shrink-0"
        style={{ color }}
      >
        {severity === "low" && <circle cx="6" cy="6" r="3" fill="currentColor" />}
        {severity === "medium" && <circle cx="6" cy="6" r="4.5" fill="currentColor" />}
        {severity === "high" && (
          <polygon
            points="6,2 10.5,10 1.5,10"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.75"
            strokeLinejoin="round"
          />
        )}
        {severity === "critical" && <polygon points="6,1.5 11,10.5 1,10.5" fill="currentColor" />}
      </svg>
      <span>{label}</span>
    </span>
  );
}
