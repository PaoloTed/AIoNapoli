"use client";

import clsx from "clsx";
import { EXPECTED_CONTRACT_VERSION } from "@/lib/contracts";
import { getDict, type Locale } from "@/lib/i18n";

export type SystemHealth = "live" | "degraded" | "offline";

type SystemStatusBarProps = {
  health: SystemHealth;
  contractVersion: string;
  contractMismatch: boolean;
  locale?: Locale;
};

export function SystemStatusBar({
  health,
  contractVersion,
  contractMismatch,
  locale = "it",
}: SystemStatusBarProps) {
  const d = getDict(locale);

  const healthColor = health === "live" ? "#5B8C6E" : health === "degraded" ? "#C79A3A" : "#C2382F";

  return (
    <div className="flex flex-wrap items-center gap-2" data-testid="system-status-bar">
      {/* System health pill */}
      <span
        className="inline-flex items-center gap-1.5 rounded-[6px] border border-[var(--border)] bg-[var(--surface)] px-2.5 py-1 text-[11px] font-medium uppercase tracking-wider text-[var(--text)]"
        data-system-health={health}
      >
        <svg
          width="10"
          height="10"
          viewBox="0 0 10 10"
          aria-hidden="true"
          style={{ color: healthColor }}
        >
          {health === "live" && <circle cx="5" cy="5" r="4" fill="currentColor" />}
          {health === "degraded" && (
            <circle cx="5" cy="5" r="3.5" fill="none" stroke="currentColor" strokeWidth="1.75" />
          )}
          {health === "offline" && <polygon points="5,1 9,9 1,9" fill="currentColor" />}
        </svg>
        <span>{d.shell.status[health]}</span>
      </span>

      {/* Contract version pill: red if different from EXPECTED_CONTRACT_VERSION (SCREENS.md §2) */}
      <span
        className={clsx(
          "inline-flex items-center gap-1.5 rounded-[6px] border px-2.5 py-1 font-mono text-[12px]",
          contractMismatch
            ? "border-[#C2382F] bg-[#C2382F] text-white"
            : "border-[var(--border)] bg-[var(--surface)] text-[var(--text-muted)]",
        )}
        data-contract-mismatch={contractMismatch ? "true" : "false"}
        title={`${d.shell.contractLabel}: ${contractVersion} (expected ${EXPECTED_CONTRACT_VERSION})`}
      >
        <span>v{contractVersion}</span>
      </span>
    </div>
  );
}
