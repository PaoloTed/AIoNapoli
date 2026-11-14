"use client";

import { useState } from "react";
import { useDecision } from "@/hooks/useDecision";
import { useScenario } from "@/hooks/useScenario";
import { mapProblemToPresentation } from "@/lib/api";
import type { Locale } from "@/lib/format";
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

export function TouristView({ scenarioId }: { scenarioId?: string | undefined }) {
  const activeScenario = scenarioId?.trim() || getDefaultScenarioId();
  const [locale, setLocale] = useState<Locale>("it");
  const d = getDict(locale);

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
  const primaryTouristAction = decisionData?.decision.plan.find(
    (p) => p.target === "tourist",
  )?.action;

  return (
    <AppShell
      theme="light"
      scenarioId={activeScenario}
      scenarioTitle={scenario?.title}
      health={health}
      contractVersion={contractVersion}
      contractMismatch={contractMismatch}
      locale={locale}
      onLocaleChange={setLocale}
      showLanguageSwitcher
    >
      <div className="mx-auto max-w-2xl space-y-5">
        <header className="space-y-1">
          <h1 className="text-[24px] font-semibold text-[var(--text)]">{d.tourist.title}</h1>
          <p className="text-[15px] text-[var(--text-muted)]">{d.tourist.subtitle}</p>
        </header>

        {contractMismatch && (
          <ContractMismatchBanner receivedVersion={contractVersion} locale={locale} />
        )}

        {scenarioState.status === "loading" && <ConsumerSkeleton />}

        {scenarioState.status === "empty" && (
          <EmptyState requestedScenario={activeScenario} basePath="/tourist" locale={locale} />
        )}

        {scenarioState.status === "error" && scenarioState.problem && (
          <ErrorBanner
            problem={scenarioState.problem}
            onRetry={scenarioState.refetch}
            locale={locale}
          />
        )}

        {scenarioState.status === "degraded" && !scenario && (
          <DegradedBanner
            message={
              scenarioState.problem
                ? mapProblemToPresentation(scenarioState.problem, locale).headline
                : d.states.degradedBackend
            }
            onRetry={scenarioState.refetch}
            locale={locale}
          />
        )}

        {scenario && (
          <>
            {decisionState.status === "degraded" && (
              <DegradedBanner
                message={
                  decisionState.problem
                    ? mapProblemToPresentation(decisionState.problem, locale).headline
                    : d.states.degradedBackend
                }
                onRetry={decisionState.refetch}
                locale={locale}
              />
            )}

            {/* Primary message above map (DESIGN.md §5) */}
            {decisionState.status === "loading" && <DecisionSkeleton />}

            {decisionState.status === "error" && decisionState.problem && (
              <ErrorBanner
                problem={decisionState.problem}
                onRetry={decisionState.refetch}
                locale={locale}
              />
            )}

            {decisionData && (
              <ChatPanel
                target="tourist"
                findings={scenario.findings}
                decisionResponse={decisionData}
                locale={locale}
              />
            )}

            {/* Compact map below primary message; internal IDs hidden (FE-REQ-21) */}
            <MapPanel
              findings={scenario.findings}
              vehiclePositions={scenario.vehicle_positions}
              referenceTimeIso={decisionData?.decision.timestamp}
              alternativeSummary={primaryTouristAction}
              compact
              hideInternalIds
              theme="light"
              locale={locale}
            />
          </>
        )}
      </div>
    </AppShell>
  );
}
