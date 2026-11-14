"use client";

import { EXPECTED_CONTRACT_VERSION } from "@/lib/contracts";
import { getDict, type Locale } from "@/lib/i18n";

export function DegradedBanner({
  message,
  onRetry,
  locale = "it",
}: {
  message: string;
  onRetry?: () => void;
  locale?: Locale;
}) {
  const d = getDict(locale);
  return (
    <div
      role="status"
      className="flex flex-wrap items-center justify-between gap-3 rounded-[10px] border border-dashed border-[#C79A3A] bg-[var(--surface)] px-4 py-3 text-[14px] text-[var(--text)]"
      data-state="degraded"
    >
      <div className="flex items-center gap-2">
        <svg
          width="12"
          height="12"
          viewBox="0 0 12 12"
          aria-hidden="true"
          className="shrink-0 text-[#C79A3A]"
        >
          <circle cx="6" cy="6" r="4.5" fill="currentColor" />
        </svg>
        <span className="text-[11px] font-medium uppercase tracking-wider text-[var(--text-muted)]">
          DEGRADED
        </span>
        <span>{message}</span>
      </div>

      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="rounded-[6px] border border-[var(--border)] px-3 py-1 text-[13px] font-medium text-[var(--text)] hover:border-[var(--accent)] transition-colors duration-120"
        >
          {d.states.retry}
        </button>
      )}
    </div>
  );
}

export function ContractMismatchBanner({
  receivedVersion,
  locale = "it",
}: {
  receivedVersion: string;
  locale?: Locale;
}) {
  const d = getDict(locale);
  return (
    <div
      role="alert"
      className="flex flex-wrap items-center justify-between gap-2 rounded-[10px] border border-[#C2382F] bg-[var(--surface)] px-4 py-3 text-[14px] text-[var(--text)]"
      data-state="contract_mismatch"
    >
      <div className="flex flex-wrap items-center gap-2">
        <span className="rounded-[6px] bg-[#C2382F] px-2 py-0.5 text-[11px] font-medium uppercase tracking-wider text-white">
          contract_mismatch
        </span>
        <span className="font-semibold">{d.states.contractMismatchTitle}</span>
        <span className="font-mono text-[13px] text-[var(--text-muted)]">
          atteso {EXPECTED_CONTRACT_VERSION} / ricevuto {receivedVersion}
        </span>
      </div>
      <span className="text-[13px] text-[var(--text-muted)]">
        {d.states.contractMismatchDetail}
      </span>
    </div>
  );
}

export function NoRulesBanner({
  description,
  locale = "it",
}: {
  description?: string;
  locale?: Locale;
}) {
  const d = getDict(locale);
  return (
    <div
      role="status"
      className="flex flex-wrap items-center gap-2 rounded-[10px] border border-[var(--border)] bg-[var(--accent-soft)] px-4 py-3 text-[14px] text-[var(--text)]"
      data-state="no_rules"
    >
      <span className="rounded-[6px] border border-[var(--border)] bg-[var(--surface)] px-2 py-0.5 text-[11px] font-medium uppercase tracking-wider text-[var(--accent)]">
        no_rules
      </span>
      <span className="font-medium">{d.operator.noRulesBanner}</span>
      {description && <span className="text-[var(--text-muted)]">— {description}</span>}
    </div>
  );
}
