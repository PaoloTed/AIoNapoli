"use client";

import { useState } from "react";
import clsx from "clsx";
import { useDecision } from "@/hooks/useDecision";
import { useDecisionStream } from "@/hooks/useDecisionStream";
import { useScenario } from "@/hooks/useScenario";
import { extractAgentFromField, mapProblemToPresentation } from "@/lib/api";
import {
  AGENT_ORDER,
  PLAN_TARGETS,
  type AgentName,
  type Finding,
  type PlanTarget,
} from "@/lib/contracts";
import { getDict } from "@/lib/i18n";
import { getDefaultScenarioId } from "@/lib/scenarios";
import { AppShell } from "./AppShell";
import { DecisionHeader } from "./DecisionHeader";
import { FindingCard } from "./FindingCard";
import { MapPanel } from "./MapPanel";
import { PlanColumn } from "./PlanColumn";
import { ReasoningList } from "./ReasoningList";
import { RuleTimeline } from "./RuleTimeline";
import type { SystemHealth } from "./SystemStatusBar";
import { ContractMismatchBanner, DegradedBanner } from "./states/DegradedBanner";
import { EmptyState } from "./states/EmptyState";
import { ErrorBanner } from "./states/ErrorBanner";
import { DecisionSkeleton, OperatorSkeleton } from "./states/Skeleton";

export function OperatorView({ scenarioId }: { scenarioId?: string | undefined }) {
  const activeScenario = scenarioId?.trim() || getDefaultScenarioId();
  const d = getDict("it");
  const [mobileTarget, setMobileTarget] = useState<PlanTarget>("operator");

  const scenarioState = useScenario(activeScenario);
  const scenario = scenarioState.scenario;

  const decisionState = useDecision(activeScenario, Boolean(scenario));
  const decisionSettled =
    Boolean(decisionState.decisionEnvelope) ||
    decisionState.status === "error" ||
    decisionState.status === "degraded";

  const streamState = useDecisionStream(activeScenario, Boolean(scenario) && decisionSettled);

  const contractMismatch =
    scenarioState.contractMismatch ||
    decisionState.contractMismatch ||
    streamState.contractMismatch;

  const contractVersion =
    decisionState.decisionEnvelope?.contractVersion ?? scenarioState.contractVersion;

  const health: SystemHealth = scenarioState.networkError
    ? "offline"
    : scenarioState.status === "degraded" ||
        decisionState.status === "degraded" ||
        streamState.status === "degraded"
      ? "degraded"
      : scenarioState.status === "error" || decisionState.status === "error"
        ? "degraded"
        : "live";

  const findingByAgent = new Map<AgentName, Finding>();
  if (scenario) {
    for (const f of scenario.findings) {
      findingByAgent.set(f.agent, f);
    }
  }

  const findingRefByAgent = new Map<string, string>();
  const decisionData = decisionState.decisionEnvelope?.data;
  if (decisionData) {
    for (const step of decisionData.decision.reasoning_log) {
      if (!findingRefByAgent.has(step.agent)) {
        findingRefByAgent.set(step.agent, step.finding_ref);
      }
    }
  }

  const refusalAgent = decisionState.problem?.refusal?.agent;
  const invalidAgent =
    decisionState.problem?.code === "invalid_finding" ||
    decisionState.problem?.code === "agent_mismatch"
      ? extractAgentFromField(decisionState.problem.field)
      : undefined;

  const operatorPlanItem = decisionData?.decision.plan.find((p) => p.target === "operator");

  return (
    <AppShell
      theme="dark"
      scenarioId={activeScenario}
      scenarioTitle={scenario?.title}
      health={health}
      contractVersion={contractVersion}
      contractMismatch={contractMismatch}
      locale="it"
    >
      <div className="space-y-6">
        {contractMismatch && (
          <ContractMismatchBanner receivedVersion={contractVersion} locale="it" />
        )}

        {/* Loading skeleton */}
        {scenarioState.status === "loading" && <OperatorSkeleton />}

        {/* Scenario not found -> EmptyState */}
        {scenarioState.status === "empty" && (
          <EmptyState requestedScenario={activeScenario} basePath="/operator" locale="it" />
        )}

        {/* Scenario fatal error */}
        {scenarioState.status === "error" && scenarioState.problem && (
          <ErrorBanner
            problem={scenarioState.problem}
            onRetry={scenarioState.refetch}
            locale="it"
          />
        )}

        {/* Scenario network/upstream degraded without data */}
        {scenarioState.status === "degraded" && !scenario && (
          <DegradedBanner
            message={
              scenarioState.problem
                ? mapProblemToPresentation(scenarioState.problem, "it").headline
                : d.states.degradedBackend
            }
            onRetry={scenarioState.refetch}
            locale="it"
          />
        )}

        {/* Scenario ready or partial */}
        {scenario && (
          <>
            {decisionState.status === "degraded" && (
              <DegradedBanner
                message={
                  decisionState.problem
                    ? mapProblemToPresentation(decisionState.problem, "it").headline
                    : d.states.degradedBackend
                }
                onRetry={decisionState.refetch}
                locale="it"
              />
            )}

            {/* Top two-column grid: Map + Findings/Timeline (SCREENS.md §3.1) */}
            <div className="grid gap-6 lg:grid-cols-12">
              <div className="lg:col-span-6">
                <MapPanel
                  findings={scenario.findings}
                  vehiclePositions={scenario.vehicle_positions}
                  referenceTimeIso={decisionData?.decision.timestamp}
                  alternativeSummary={operatorPlanItem?.action}
                  theme="dark"
                  locale="it"
                />
              </div>

              <div className="lg:col-span-6 space-y-4">
                <section aria-label={d.operator.findingsTitle} className="space-y-3">
                  <div className="flex items-center justify-between">
                    <h2 className="text-[11px] font-medium uppercase tracking-wider text-[var(--text-muted)]">
                      {d.operator.findingsTitle}
                    </h2>
                    <span className="font-mono text-[12px] text-[var(--text-muted)]">
                      {scenario.findings.length}/3
                    </span>
                  </div>

                  <div className="space-y-3">
                    {AGENT_ORDER.map((agent) => {
                      const f = findingByAgent.get(agent);
                      const agentRefusal =
                        refusalAgent === agent ? decisionState.problem?.refusal : undefined;
                      const agentErrorNotice =
                        invalidAgent === agent && decisionState.problem
                          ? mapProblemToPresentation(decisionState.problem, "it").detail
                          : undefined;
                      return (
                        <FindingCard
                          key={agent}
                          agent={agent}
                          finding={f}
                          findingRef={findingRefByAgent.get(agent)}
                          refusal={agentRefusal}
                          errorNotice={agentErrorNotice}
                          locale="it"
                        />
                      );
                    })}
                  </div>
                </section>

                <RuleTimeline
                  steps={streamState.steps}
                  status={streamState.status}
                  onRetry={streamState.reconnect}
                  locale="it"
                />
              </div>
            </div>

            {/* Decision loading skeleton while scenario is already visible (FE-REQ-06) */}
            {decisionState.status === "loading" && <DecisionSkeleton />}

            {/* Decision error */}
            {decisionState.status === "error" && decisionState.problem && (
              <ErrorBanner
                problem={decisionState.problem}
                onRetry={decisionState.refetch}
                locale="it"
              />
            )}

            {/* Decision ready / no_rules */}
            {decisionData && (
              <div className="space-y-6">
                <DecisionHeader
                  decisionId={decisionData.decision_id}
                  decision={decisionData.decision}
                  findings={scenario.findings}
                  onRepeat={decisionState.repeatCheck}
                  repeatState={decisionState.repeatState}
                  locale="it"
                />

                <div className="space-y-4">
                  {/* Mobile tabs (< 768px) per DESIGN.md §5 */}
                  <div
                    role="tablist"
                    aria-label={d.operator.planTitle}
                    className="grid grid-cols-3 gap-1 rounded-[10px] border border-[var(--border)] bg-[var(--surface)] p-1 md:hidden"
                  >
                    {PLAN_TARGETS.map((target) => (
                      <button
                        key={target}
                        type="button"
                        role="tab"
                        aria-selected={mobileTarget === target}
                        onClick={() => setMobileTarget(target)}
                        className={clsx(
                          "rounded-[6px] px-2 py-1.5 text-[12px] font-medium transition-colors duration-120",
                          mobileTarget === target
                            ? "bg-[var(--accent-soft)] text-[var(--accent)]"
                            : "text-[var(--text-muted)]",
                        )}
                      >
                        {d.targets[target]}
                      </button>
                    ))}
                  </div>

                  {/* Desktop 3-column plan & relevance; mobile renders only active tab via hidden/md:block */}
                  <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
                    {PLAN_TARGETS.map((target) => (
                      <PlanColumn
                        key={target}
                        target={target}
                        plan={decisionData.decision.plan}
                        targetRelevance={decisionData.relevance.targets[target]}
                        rounding={decisionData.relevance.rounding}
                        narrative={decisionData.narrative}
                        locale="it"
                        className={mobileTarget === target ? "block" : "hidden md:block"}
                      />
                    ))}
                  </div>
                </div>

                {/* Reasoning log shown ONLY on /operator (FE-REQ-21) */}
                <ReasoningList steps={decisionData.decision.reasoning_log} locale="it" />
              </div>
            )}
          </>
        )}
      </div>
    </AppShell>
  );
}
