"use client";

import { useState } from "react";
import clsx from "clsx";

export type MockBannerProps = {
  isMock?: boolean;
  reason?: string;
  onDismiss?: () => void;
  className?: string;
};

/**
 * Visual banner displayed when mock data or offline fallback is active.
 * Complies with FE-REQ / Milestone 1 requirement for explicit mock state visibility.
 */
export function MockBanner({
  isMock,
  reason,
  onDismiss,
  className,
}: MockBannerProps) {
  const [dismissed, setDismissed] = useState(false);

  // Active if explicitly true, or if undefined and NEXT_PUBLIC_USE_MOCKS is enabled
  const active =
    (isMock !== undefined ? isMock : process.env.NEXT_PUBLIC_USE_MOCKS === "true") &&
    !dismissed;

  if (!active) {
    return null;
  }

  const handleDismiss = () => {
    setDismissed(true);
    if (onDismiss) {
      onDismiss();
    }
  };

  return (
    <div
      role="status"
      aria-live="polite"
      data-testid="mock-banner"
      className={clsx(
        "flex items-center justify-between gap-3 border-b border-amber-500/30 bg-amber-500/10 px-4 py-2 text-xs text-amber-200 transition-colors backdrop-blur-sm",
        className,
      )}
    >
      <div className="flex items-center gap-2">
        <span
          className="inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-bold uppercase tracking-wider bg-amber-500/20 text-amber-300 border border-amber-500/40"
          data-testid="mock-badge"
        >
          Mock Mode
        </span>
        <span className="font-medium text-amber-100">
          {reason ?? "Modalità simulazione attiva: backend offline o fixture locali in uso"}
        </span>
      </div>
      <button
        type="button"
        onClick={handleDismiss}
        aria-label="Chiudi avviso modalità mock"
        className="rounded px-2 py-0.5 text-[11px] text-amber-300 hover:bg-amber-500/20 hover:text-amber-100 transition-colors"
      >
        ✕
      </button>
    </div>
  );
}
