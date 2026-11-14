"use client";

import type { RepeatComparisonState } from "@/hooks/useDecision";
import type { Decision, Finding } from "@/lib/contracts";
import { formatPercent, formatRomeDateTime, type Locale } from "@/lib/format";
import { getDict } from "@/lib/i18n";
import { NoRulesBanner } from "./states/DegradedBanner";

type DecisionHeaderProps = {
  decisionId: string;
  decision: Decision;
  findings: Finding[];
  onRepeat: () => void;
  repeatState: RepeatComparisonState;
  locale?: Locale;
};

function computeFindingToDecisionDelta(
  findings: Finding[],
  decisionTimestamp: string,
): string | undefined {
  const decisionMs = Date.parse(decisionTimestamp);
  if (Number.isNaN(decisionMs) || findings.length === 0) return undefined;
  const findingTimes = findings.map((f) => Date.parse(f.timestamp)).filter((t) => !Number.isNaN(t));
  if (findingTimes.length === 0) return undefined;
  const latestFindingMs = Math.max(...findingTimes);
  const deltaMs = Math.max(0, decisionMs - latestFindingMs);
  if (deltaMs < 1000) return `${deltaMs} ms`;
  return `${(deltaMs / 1000).toFixed(1)} s`;
}

export function DecisionHeader({
  decisionId,
  decision,
  findings,
  onRepeat,
  repeatState,
  locale = "it",
}: DecisionHeaderProps) {
  const d = getDict(locale);
  const distinctTargets = new Set(decision.plan.map((p) => p.target)).size;
  const simulatedCount = findings.filter((f) => f.is_simulated).length;
  const latencyLabel = computeFindingToDecisionDelta(findings, decision.timestamp);

  return (
    <section
      className="rounded-[10px] border border-[var(--border)] bg-[var(--surface)] p-4 space-y-4"
      data-testid="decision-header"
    >
      {/* Top bar: trigger, decision_id, repeat button */}
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="space-y-1.5">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-[11px] font-medium uppercase tracking-wider text-[var(--text-muted)]">
              {d.operator.decisionTitle}
            </span>
            <code className="rounded-[6px] border border-[var(--border)] bg-[var(--bg)] px-2 py-0.5 font-mono text-[13px] text-[var(--accent)]">
              {decision.trigger.rule_id}
            </code>
            <span className="text-[13px] text-[var(--text-muted)]">
              ({decision.trigger.agents_involved.join(", ")})
            </span>
          </div>

          <div className="flex flex-wrap items-center gap-3 text-[13px] text-[var(--text-muted)]">
            <span>
              <span className="text-[11px] font-medium uppercase tracking-wider">
                decision_id:{" "}
              </span>
              <code
                className="font-mono text-[13px] text-[var(--text)]"
                data-testid="decision-id-value"
              >
                {decisionId}
              </code>
            </span>
            <span>
              <span className="text-[11px] font-medium uppercase tracking-wider">
                {d.operator.confidence}:{" "}
              </span>
              <code className="font-mono text-[13px] text-[var(--text)]">
                {formatPercent(decision.confidence)}
              </code>
            </span>
            <time dateTime={decision.timestamp} className="font-mono text-[13px]">
              {formatRomeDateTime(decision.timestamp, locale)}
            </time>
          </div>
        </div>

        <button
          type="button"
          onClick={onRepeat}
          disabled={repeatState.status === "loading"}
          data-testid="repeat-decision-button"
          className="rounded-[6px] border border-[var(--accent)] bg-[var(--accent-soft)] px-3.5 py-2 text-[13px] font-medium text-[var(--text)] hover:bg-[var(--accent)] hover:text-[var(--bg)] disabled:opacity-60 transition-colors duration-120"
        >
          {repeatState.status === "loading" ? d.operator.repeatLoading : d.operator.repeatButton}
        </button>
      </div>

      {/* Conflict or no_rules banner (FE-REQ-08) */}
      {decision.conflict.detected ? (
        <div
          className="rounded-[6px] border border-[#D06A32] bg-[var(--bg)] px-3.5 py-2.5 space-y-1"
          data-testid="conflict-box"
        >
          <div className="flex items-center gap-2">
            <svg
              width="12"
              height="12"
              viewBox="0 0 12 12"
              aria-hidden="true"
              className="shrink-0 text-[#D06A32]"
            >
              <polygon
                points="6,2 10.5,10 1.5,10"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.75"
              />
            </svg>
            <span className="text-[11px] font-medium uppercase tracking-wider text-[#D06A32]">
              {d.operator.conflictDetected}
            </span>
          </div>
          <p className="text-[15px] text-[var(--text)]">{decision.conflict.description}</p>
        </div>
      ) : (
        <NoRulesBanner description={decision.conflict.description} locale={locale} />
      )}

      {/* Determinism check result row (FE-REQ-26, API-CLIENT.md §7) */}
      {repeatState.status === "done" && (
        <div
          className="flex flex-wrap items-center gap-2 rounded-[6px] border border-[var(--border)] bg-[var(--bg)] px-3 py-2 font-mono text-[13px]"
          data-testid="repeat-result"
        >
          <span
            className={
              repeatState.same ? "font-semibold text-[#5B8C6E]" : "font-semibold text-[#C2382F]"
            }
          >
            {repeatState.same ? d.operator.repeatSame : d.operator.repeatDifferent}
          </span>
          {repeatState.same ? (
            <span className="text-[var(--text)]">{repeatState.firstId}</span>
          ) : (
            <span className="text-[var(--text)]">
              {repeatState.firstId} ≠ {repeatState.secondId}
            </span>
          )}
        </div>
      )}

      {repeatState.status === "error" && (
        <div
          role="status"
          className="rounded-[6px] border border-[#C2382F] bg-[var(--bg)] px-3 py-2 text-[13px] text-[var(--text)]"
        >
          {repeatState.detail}
        </div>
      )}

      {/* Observable metrics strictly computed from existing contract fields (FE-REQ-28) */}
      <dl className="grid grid-cols-2 gap-3 border-t border-[var(--border)] pt-3 sm:grid-cols-5">
        <div>
          <dt className="text-[11px] font-medium uppercase tracking-wider text-[var(--text-muted)]">
            {d.operator.metricSteps}
          </dt>
          <dd className="font-mono text-[13px] text-[var(--text)]">
            {decision.reasoning_log.length}
          </dd>
        </div>
        <div>
          <dt className="text-[11px] font-medium uppercase tracking-wider text-[var(--text-muted)]">
            {d.operator.metricTargets}
          </dt>
          <dd className="font-mono text-[13px] text-[var(--text)]">{distinctTargets}/3</dd>
        </div>
        <div>
          <dt className="text-[11px] font-medium uppercase tracking-wider text-[var(--text-muted)]">
            {d.operator.metricActions}
          </dt>
          <dd className="font-mono text-[13px] text-[var(--text)]">{decision.plan.length}</dd>
        </div>
        <div>
          <dt className="text-[11px] font-medium uppercase tracking-wider text-[var(--text-muted)]">
            {d.operator.metricSimulated}
          </dt>
          <dd className="font-mono text-[13px] text-[var(--text)]">
            {simulatedCount}/{findings.length}
          </dd>
        </div>
        {latencyLabel !== undefined && (
          <div>
            <dt className="text-[11px] font-medium uppercase tracking-wider text-[var(--text-muted)]">
              {d.operator.metricLatency}
            </dt>
            <dd className="font-mono text-[13px] text-[var(--text)]">{latencyLabel}</dd>
          </div>
        )}
      </dl>
    </section>
  );
}
