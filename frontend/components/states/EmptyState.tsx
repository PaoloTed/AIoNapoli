"use client";

import Link from "next/link";
import { getDict, type Locale } from "@/lib/i18n";
import { getConfiguredScenarios } from "@/lib/scenarios";

type EmptyStateProps = {
  requestedScenario: string;
  basePath: "/operator" | "/tourist" | "/citizen";
  locale?: Locale;
};

export function EmptyState({ requestedScenario, basePath, locale = "it" }: EmptyStateProps) {
  const d = getDict(locale);
  const knownScenarios = getConfiguredScenarios();

  return (
    <section
      className="rounded-[10px] border border-[var(--border)] bg-[var(--surface)] p-6 space-y-4"
      data-state="empty"
    >
      <div className="space-y-1">
        <p className="text-[11px] font-medium uppercase tracking-wider text-[var(--text-muted)]">
          404 • scenario_not_found
        </p>
        <h2 className="text-[20px] font-semibold text-[var(--text)]">{d.states.notFoundTitle}</h2>
        <p className="text-[15px] text-[var(--text-muted)]">
          {d.states.requestedScenario}:{" "}
          <code className="font-mono text-[13px] text-[var(--text)]">{requestedScenario}</code>
        </p>
      </div>

      <div className="space-y-2">
        <p className="text-[11px] font-medium uppercase tracking-wider text-[var(--text-muted)]">
          {d.states.knownScenarios}
        </p>
        <div className="flex flex-wrap gap-2">
          {knownScenarios.map((id) => (
            <Link
              key={id}
              href={`${basePath}?scenario=${encodeURIComponent(id)}`}
              className="inline-flex items-center rounded-[6px] border border-[var(--border)] bg-[var(--bg)] px-3 py-1.5 font-mono text-[13px] text-[var(--accent)] hover:bg-[var(--accent-soft)] transition-colors duration-120"
            >
              {id}
            </Link>
          ))}
        </div>
      </div>
    </section>
  );
}
