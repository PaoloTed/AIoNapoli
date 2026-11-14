"use client";

import { useDecision } from "@/hooks/useDecision";
import { useScenario } from "@/hooks/useScenario";
import { mapProblemToPresentation } from "@/lib/api";
import { getDict } from "@/lib/i18n";
import { getDefaultScenarioId } from "@/lib/scenarios";
import { AppShell } from "./AppShell";
import { ChatPanel } from "./ChatPanel";
import { MapPanel } from "./MapPanel";
import type { SystemHealth } from "./SystemStatusBar";
import { ContractMismatchBanner, DegradedBanner } from "./states/DegradedBanner";
import { EmptyState } from "./states/EmptyState";
import { ErrorBanner } from "./states/ErrorBanner";
import { ConsumerSkeleton, DecisionSkeleton } from "./states/Skeleton";

export function CitizenView({ scenarioId }: { scenarioId?: string | undefined }) {
  const activeScenario = scenarioId?.trim() || getDefaultScenarioId();
  const d = getDict("it");

  const scenarioState = useScenario(activeScenario);
  const scenario = scenarioState.scenario;
  const decisionState = useDecision(activeScenario, Boolean(scenario));

  const contractMismatch = scenarioState.contractMismatch || decisionState.contractMismatch;
  const contractVersion =
    decisionState.decisionEnvelope?.contractVersion ?? scenarioState.contractVersion;

  const health: SystemHealth = scenarioState.networkError
    ? "offline"
    : scenarioState.status === "degraded" || decisionState.status === "degraded"
      ? "degraded"
      : scenarioState.status === "error" || decisionState.status === "error"
        ? "degraded"
        : "live";

  const decisionData = decisionState.decisionEnvelope?.data;
  const primaryCitizenAction = decisionData?.decision.plan.find(
    (p) => p.target === "citizen",
  )?.action;

  return (
    <AppShell
      theme="light"
      scenarioId={activeScenario}
      scenarioTitle={scenario?.title}
      health={health}
      contractVersion={contractVersion}
      contractMismatch={contractMismatch}
      locale="it"
    >
      <div className="mx-auto max-w-2xl space-y-5">
        <header className="space-y-1">
          <h1 className="text-[24px] font-semibold text-[var(--text)]">{d.citizen.title}</h1>
          <p className="text-[15px] text-[var(--text-muted)]">{d.citizen.subtitle}</p>
        </header>

        {contractMismatch && (
          <ContractMismatchBanner receivedVersion={contractVersion} locale="it" />
        )}

        {scenarioState.status === "loading" && <ConsumerSkeleton />}

        {scenarioState.status === "empty" && (
          <EmptyState requestedScenario={activeScenario} basePath="/citizen" locale="it" />
        )}

        {scenarioState.status === "error" && scenarioState.problem && (
          <ErrorBanner
            problem={scenarioState.problem}
            onRetry={scenarioState.refetch}
            locale="it"
          />
        )}

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

            {decisionState.status === "loading" && <DecisionSkeleton />}

            {decisionState.status === "error" && decisionState.problem && (
              <ErrorBanner
                problem={decisionState.problem}
                onRetry={decisionState.refetch}
                locale="it"
              />
            )}

            {decisionData && (
              <ChatPanel
                target="citizen"
                findings={scenario.findings}
                decisionResponse={decisionData}
                locale="it"
              />
            )}

            <MapPanel
              findings={scenario.findings}
              vehiclePositions={scenario.vehicle_positions}
              referenceTimeIso={decisionData?.decision.timestamp}
              alternativeSummary={primaryCitizenAction}
              compact
              hideInternalIds
              theme="light"
              locale="it"
            />
          </>
        )}
      </div>
    </AppShell>
  );
}
