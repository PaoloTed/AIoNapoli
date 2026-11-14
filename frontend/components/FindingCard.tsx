"use client";

import clsx from "clsx";
import {
  congestion,
  density,
  expectedAttendance,
  heavyRain,
  zoneId,
  type AgentName,
  type Finding,
  type Refusal,
} from "@/lib/contracts";
import { formatPercent, formatRomeDateTime, type Locale } from "@/lib/format";
import { getDict } from "@/lib/i18n";
import { ProvenanceChip } from "./ProvenanceChip";
import { SeverityBadge } from "./SeverityBadge";

type FindingCardProps = {
  agent: AgentName;
  finding?: Finding | undefined;
  findingRef?: string | undefined;
  refusal?: Refusal | undefined;
  errorNotice?: string | undefined;
  locale?: Locale;
};

export function FindingCard({
  agent,
  finding,
  findingRef,
  refusal,
  errorNotice,
  locale = "it",
}: FindingCardProps) {
  const d = getDict(locale);
  const agentLabel = d.agents[agent];

  // Missing finding -> partial state card (DESIGN.md §2.3, FE-REQ-07, FE-REQ-20)
  if (!finding) {
    return (
      <article
        className="rounded-[10px] border border-dashed border-[var(--border)] bg-[var(--surface)] p-4 opacity-60 space-y-2.5"
        data-testid={`finding-card-${agent}`}
        data-finding-state="missing"
      >
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <span className="text-[11px] font-medium uppercase tracking-wider text-[var(--text-muted)]">
              {agentLabel}
            </span>
            <code className="font-mono text-[13px] text-[var(--text-muted)]">{agent}</code>
          </div>
          <ProvenanceChip variant="unavailable" locale={locale} />
        </div>

        <p className="text-[15px] text-[var(--text)]">
          {errorNotice ?? d.operator.missingCardNote}
        </p>

        {refusal && (
          <div className="space-y-1 pt-1 text-[13px] text-[var(--text-muted)]">
            <div>
              <span className="text-[11px] font-medium uppercase tracking-wider">
                reason_code:{" "}
              </span>
              <code className="font-mono text-[13px] text-[var(--text)]">
                {refusal.reason_code}
              </code>
            </div>
            {refusal.detail && <p>{refusal.detail}</p>}
          </div>
        )}
      </article>
    );
  }

  // Read content ONLY via the 5 contract accessors (FE-REQ-03)
  const densityVal = density(finding);
  const congestionVal = congestion(finding);
  const zoneVal = zoneId(finding);
  const rainVal = heavyRain(finding);
  const attendanceVal = expectedAttendance(finding);

  const hasContentMetrics =
    densityVal !== undefined ||
    congestionVal !== undefined ||
    zoneVal !== undefined ||
    rainVal !== undefined ||
    attendanceVal !== undefined;

  return (
    <article
      className={clsx(
        "rounded-[10px] bg-[var(--surface)] p-4 space-y-3 transition-colors duration-120",
        finding.is_simulated
          ? "border border-dashed border-[var(--border)]"
          : "border border-solid border-[var(--border)]",
      )}
      data-testid={`finding-card-${finding.agent}`}
      data-finding-state={finding.is_simulated ? "simulated" : "real"}
    >
      {/* Header row */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-[11px] font-medium uppercase tracking-wider text-[var(--text-muted)]">
            {agentLabel}
          </span>
          <code className="font-mono text-[13px] text-[var(--text)]">{finding.type}</code>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <ProvenanceChip variant={finding.is_simulated ? "simulated" : "real"} locale={locale} />
          <SeverityBadge severity={finding.severity} locale={locale} />
        </div>
      </div>

      {/* Extracted content accessors (never default to 0 when undefined) */}
      {hasContentMetrics && (
        <dl className="grid grid-cols-2 gap-x-4 gap-y-2 sm:grid-cols-3 text-[13px]">
          {zoneVal !== undefined && (
            <div>
              <dt className="text-[11px] font-medium uppercase tracking-wider text-[var(--text-muted)]">
                {d.operator.zone}
              </dt>
              <dd className="font-mono text-[13px] text-[var(--text)]">{zoneVal}</dd>
            </div>
          )}
          {densityVal !== undefined && (
            <div>
              <dt className="text-[11px] font-medium uppercase tracking-wider text-[var(--text-muted)]">
                {d.operator.density}
              </dt>
              <dd className="font-mono text-[13px] text-[var(--text)]">
                {densityVal.toFixed(2)} ({formatPercent(densityVal)})
              </dd>
            </div>
          )}
          {congestionVal !== undefined && (
            <div>
              <dt className="text-[11px] font-medium uppercase tracking-wider text-[var(--text-muted)]">
                {d.operator.congestion}
              </dt>
              <dd className="font-mono text-[13px] text-[var(--text)]">
                {congestionVal.toFixed(2)} ({formatPercent(congestionVal)})
              </dd>
            </div>
          )}
          {rainVal !== undefined && (
            <div>
              <dt className="text-[11px] font-medium uppercase tracking-wider text-[var(--text-muted)]">
                {d.operator.heavyRain}
              </dt>
              <dd className="text-[14px] text-[var(--text)]">
                {rainVal ? d.operator.yes : d.operator.no}
              </dd>
            </div>
          )}
          {attendanceVal !== undefined && (
            <div>
              <dt className="text-[11px] font-medium uppercase tracking-wider text-[var(--text-muted)]">
                {d.operator.attendance}
              </dt>
              <dd className="font-mono text-[13px] text-[var(--text)]">
                {attendanceVal.toLocaleString(locale === "en" ? "en-GB" : "it-IT")}
              </dd>
            </div>
          )}
        </dl>
      )}

      {/* Provenance & technical metadata */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-t border-[var(--border)] pt-2.5 text-[13px] text-[var(--text-muted)]">
        <div className="flex flex-wrap items-center gap-3">
          <span>
            <span className="text-[11px] font-medium uppercase tracking-wider">
              {d.operator.source}:{" "}
            </span>
            <code className="font-mono text-[13px] text-[var(--text)]">{finding.source_id}</code>
          </span>
          <span>
            <span className="text-[11px] font-medium uppercase tracking-wider">
              {d.operator.confidence}:{" "}
            </span>
            <code className="font-mono text-[13px] text-[var(--text)]">
              {formatPercent(finding.confidence)}
            </code>
          </span>
          {findingRef && (
            <span>
              <span className="text-[11px] font-medium uppercase tracking-wider">ref: </span>
              <code className="font-mono text-[13px] text-[var(--text)]">{findingRef}</code>
            </span>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <code
            className="font-mono text-[13px] truncate max-w-[260px]"
            title={finding.data_reference}
          >
            {finding.data_reference}
          </code>
          <time dateTime={finding.timestamp} className="font-mono text-[13px]">
            {formatRomeDateTime(finding.timestamp, locale)}
          </time>
        </div>
      </div>

      {errorNotice && (
        <p className="text-[13px] text-[#D06A32]" role="status">
          {errorNotice}
        </p>
      )}
    </article>
  );
}
