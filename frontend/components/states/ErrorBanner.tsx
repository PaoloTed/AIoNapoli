"use client";

import type { Problem } from "@/lib/contracts";
import { mapProblemToPresentation } from "@/lib/api";
import { getDict, type Locale } from "@/lib/i18n";

type ErrorBannerProps = {
  problem: Problem;
  onRetry?: () => void;
  locale?: Locale;
};

export function ErrorBanner({ problem, onRetry, locale = "it" }: ErrorBannerProps) {
  const d = getDict(locale);
  const mapped = mapProblemToPresentation(problem, locale);

  return (
    <section
      role="alert"
      className="rounded-[10px] border border-[#C2382F] bg-[var(--surface)] p-4 space-y-3"
      data-state="error"
      data-error-code={mapped.code}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <svg
              width="14"
              height="14"
              viewBox="0 0 12 12"
              aria-hidden="true"
              className="shrink-0 text-[#C2382F]"
            >
              <polygon points="6,1.5 11,10.5 1,10.5" fill="currentColor" />
            </svg>
            <code className="font-mono text-[13px] text-[var(--text)]">{mapped.code}</code>
          </div>
          <h2 className="text-[15px] font-semibold text-[var(--text)]">{mapped.headline}</h2>
          {mapped.detail && mapped.detail !== mapped.headline && (
            <p className="text-[14px] text-[var(--text-muted)]">{mapped.detail}</p>
          )}
        </div>

        {onRetry && (
          <button
            type="button"
            disabled={!mapped.canRetry}
            onClick={onRetry}
            className="rounded-[6px] border border-[var(--border)] bg-[var(--bg)] px-3 py-1.5 text-[13px] font-medium text-[var(--text)] hover:border-[var(--accent)] disabled:cursor-not-allowed disabled:opacity-45 transition-colors duration-120"
          >
            {d.states.retry}
          </button>
        )}
      </div>
    </section>
  );
}
