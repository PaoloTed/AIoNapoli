"use client";

import type { StreamStatus } from "@/hooks/useDecisionStream";
import type { StreamEvent } from "@/lib/contracts";
import { getDict, type Locale } from "@/lib/i18n";
import { RuleRow } from "./RuleRow";

type RuleTimelineProps = {
  steps: StreamEvent[];
  status: StreamStatus;
  onRetry?: () => void;
  locale?: Locale;
};

export function RuleTimeline({ steps, status, onRetry, locale = "it" }: RuleTimelineProps) {
  const d = getDict(locale);

  return (
    <section
      className="rounded-[10px] border border-[var(--border)] bg-[var(--surface)] p-4 space-y-3"
      data-testid="rule-timeline"
      data-stream-status={status}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-[11px] font-medium uppercase tracking-wider text-[var(--text-muted)]">
          {d.operator.timelineTitle}
        </h3>
        <span className="rounded-[6px] border border-[var(--border)] px-2 py-0.5 font-mono text-[11px] uppercase tracking-wider text-[var(--text-muted)]">
          {status}
        </span>
      </div>

      {status === "degraded" && (
        <div
          role="status"
          className="flex flex-wrap items-center justify-between gap-2 rounded-[6px] border border-dashed border-[#C79A3A] px-3 py-2 text-[13px] text-[var(--text)]"
        >
          <span>{d.operator.streamUnavailable}</span>
          {onRetry && (
            <button
              type="button"
              onClick={onRetry}
              className="rounded-[6px] border border-[var(--border)] px-2.5 py-1 text-[12px] font-medium text-[var(--text)] hover:border-[var(--accent)] transition-colors duration-120"
            >
              {d.operator.streamRetry}
            </button>
          )}
        </div>
      )}

      {/* aria-live="polite" without stealing focus (FE-REQ-30) */}
      <ol aria-live="polite" className="space-y-2">
        {steps.length === 0 && status !== "degraded" && (
          <li className="text-[14px] text-[var(--text-muted)]">{d.operator.streamEmpty}</li>
        )}

        {steps.map((step, index) => {
          if (step.event === "rule_evaluated") {
            return (
              <RuleRow
                key={`rule-${index}-${step.data.rule_id}`}
                rule={step.data}
                locale={locale}
              />
            );
          }

          if (step.event === "phase") {
            return (
              <li
                key={`phase-${index}-${step.data.phase}`}
                className="flex items-center justify-between rounded-[6px] border border-[var(--border)] bg-[var(--bg)] px-3 py-1.5 text-[13px] text-[var(--text-muted)] transition-opacity duration-200 motion-reduce:transition-none"
              >
                <span className="text-[11px] font-medium uppercase tracking-wider">
                  phase {step.data.index}
                </span>
                <code className="font-mono text-[13px] text-[var(--text)]">{step.data.phase}</code>
              </li>
            );
          }

          if (step.event === "conflict_detected") {
            return (
              <li
                key={`conflict-${index}`}
                className="rounded-[6px] border border-[#D06A32] bg-[var(--bg)] px-3 py-2 text-[13px] space-y-0.5 transition-opacity duration-200 motion-reduce:transition-none"
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-[11px] font-medium uppercase tracking-wider text-[#D06A32]">
                    conflict_detected
                  </span>
                  {step.data.zone_id && (
                    <code className="font-mono text-[13px] text-[var(--text)]">
                      {step.data.zone_id}
                    </code>
                  )}
                </div>
                <p className="text-[14px] text-[var(--text)]">{step.data.description}</p>
              </li>
            );
          }

          if (step.event === "priority_applied") {
            return (
              <li
                key={`priority-${index}`}
                className="flex flex-wrap items-center justify-between gap-2 rounded-[6px] border border-[var(--border)] bg-[var(--bg)] px-3 py-1.5 text-[13px] transition-opacity duration-200 motion-reduce:transition-none"
              >
                <span className="text-[11px] font-medium uppercase tracking-wider text-[var(--text-muted)]">
                  priority_applied
                </span>
                <span className="font-mono text-[13px] text-[var(--text)]">
                  {step.data.priority} → {step.data.winner}
                </span>
              </li>
            );
          }

          if (step.event === "plan_item_created") {
            return (
              <li
                key={`plan-${index}-${step.data.action_ref}`}
                className="flex flex-wrap items-center justify-between gap-2 rounded-[6px] border border-[var(--border)] bg-[var(--bg)] px-3 py-1.5 text-[13px] transition-opacity duration-200 motion-reduce:transition-none"
              >
                <span className="text-[11px] font-medium uppercase tracking-wider text-[var(--text-muted)]">
                  plan_item_created ({step.data.target})
                </span>
                <code className="font-mono text-[13px] text-[var(--text)]">
                  {step.data.action_ref}
                </code>
              </li>
            );
          }

          if (step.event === "decision") {
            return (
              <li
                key={`decision-${index}`}
                className="flex flex-wrap items-center justify-between gap-2 rounded-[6px] border border-[var(--accent)] bg-[var(--accent-soft)] px-3 py-2 text-[13px] transition-opacity duration-200 motion-reduce:transition-none"
              >
                <span className="text-[11px] font-medium uppercase tracking-wider text-[var(--accent)]">
                  decision
                </span>
                <code className="font-mono text-[13px] text-[var(--text)]">
                  {step.data.decision_id}
                </code>
              </li>
            );
          }

          if (step.event === "start") {
            return (
              <li
                key={`start-${index}`}
                className="flex items-center justify-between rounded-[6px] border border-[var(--border)] bg-[var(--bg)] px-3 py-1.5 text-[13px] text-[var(--text-muted)]"
              >
                <span className="text-[11px] font-medium uppercase tracking-wider">start</span>
                <code className="font-mono text-[13px] text-[var(--text)]">
                  {step.data.scenario_id}
                </code>
              </li>
            );
          }

          return (
            <li
              key={`err-${index}`}
              className="rounded-[6px] border border-[#C2382F] bg-[var(--bg)] px-3 py-2 text-[13px] text-[var(--text)]"
            >
              <code className="font-mono">{step.data.code}</code>: {step.data.detail}
            </li>
          );
        })}
      </ol>
    </section>
  );
}
