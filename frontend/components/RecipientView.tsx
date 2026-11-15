"use client";

import { useState } from "react";
import { useDecision } from "@/hooks/useDecision";
import { useScenario } from "@/hooks/useScenario";
import { mapProblemToPresentation } from "@/lib/api";
import type { Locale } from "@/lib/format";
import { getDict } from "@/lib/i18n";
import { getDefaultScenarioId } from "@/lib/scenarios";
import { RECIPIENT_PROFILES, type RecipientProfile, type RecipientTarget } from "@/lib/recipients";
import { AppShell } from "./AppShell";
import { ChatPanel } from "./ChatPanel";
import { MapPanel } from "./MapPanel";
import { RouteRequestAssistant } from "./RouteRequestAssistant";
import type { SystemHealth } from "./SystemStatusBar";
import { ContractMismatchBanner, DegradedBanner } from "./states/DegradedBanner";
import { EmptyState } from "./states/EmptyState";
import { ErrorBanner } from "./states/ErrorBanner";
import { ConsumerSkeleton, DecisionSkeleton } from "./states/Skeleton";

export type RecipientViewProps = {
  profile?: RecipientProfile;
  target?: RecipientTarget;
  scenarioId?: string | undefined;
};

export function RecipientView({ profile: profileProp, target = "tourist", scenarioId }: RecipientViewProps) {
  const profile = profileProp ?? RECIPIENT_PROFILES[target];
  const activeScenario = scenarioId?.trim() || getDefaultScenarioId();
  const [locale, setLocale] = useState<Locale>(profile.defaultLocale);
  const [selectedZoneId, setSelectedZoneId] = useState<string | null>(null);
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
  const primaryAction = decisionData?.decision.plan.find(
    (p) => p.target === profile.target,
  )?.action;

  const handleLocationSelected = (_lat: number, _lon: number, label: string) => {
    const lower = label.toLowerCase();
    if (lower.includes("bagnoli")) setSelectedZoneId("Z_BAGNOLI");
    else if (lower.includes("garibaldi")) setSelectedZoneId("Z_GARIBALDI");
    else if (lower.includes("centro")) setSelectedZoneId("Z_CENTRO");
    else if (lower.includes("municipio") || lower.includes("beverello")) setSelectedZoneId("Z_MUNICIPIO");
    else if (lower.includes("fuorigrotta")) setSelectedZoneId("Z_FUORIGROTTA");
    else if (lower.includes("mergellina")) setSelectedZoneId("Z_MERGELLINA");
  };

  const dictSection = d[profile.dictKey];

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
      showLanguageSwitcher={profile.showLanguageSwitcher}
    >
      <div className="mx-auto max-w-2xl space-y-5">
        <header className="space-y-1">
          <h1 className="text-[24px] font-semibold text-[var(--text)]">{dictSection.title}</h1>
          <p className="text-[15px] text-[var(--text-muted)]">{dictSection.subtitle}</p>
        </header>

        {contractMismatch && (
          <ContractMismatchBanner receivedVersion={contractVersion} locale={locale} />
        )}

        {scenarioState.status === "loading" && <ConsumerSkeleton />}

        {scenarioState.status === "empty" && (
          <EmptyState requestedScenario={activeScenario} basePath={profile.basePath} locale={locale} />
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
                target={profile.target}
                findings={scenario.findings}
                decisionResponse={decisionData}
                locale={locale}
              />
            )}

            <MapPanel
              findings={scenario.findings}
              vehiclePositions={scenario.vehicle_positions}
              referenceTimeIso={decisionData?.decision.timestamp}
              alternativeSummary={primaryAction}
              compact
              hideInternalIds
              theme="light"
              locale={locale}
              selectedZoneId={selectedZoneId}
              onSelectZone={setSelectedZoneId}
            />

            {/* Practical Transit Helper Cards (Fares & Accessibility) */}
            <div className="grid gap-3 sm:grid-cols-2 text-[12px]">
              <div className="rounded-[8px] border border-[#E5E3DE] bg-[#FFFFFF] p-3 space-y-1">
                <div className="flex items-center gap-1.5 font-semibold text-[#141A20]">
                  <span className="text-[#D06A32]">💳</span>
                  <span>{locale === "en" ? "Fares & Payment" : "Titoli di Viaggio & Pagamenti"}</span>
                </div>
                <p className="text-[var(--text-muted)] leading-relaxed">
                  {locale === "en"
                    ? "Single ticket ANM €1.50 (90 min valid). Tap&Go contactless payment enabled on all metro turnstiles and on-board buses."
                    : "Biglietto Corsa Singola ANM 1,50€ (valido 90 min). Tap&Go contactless attivo su tutti i tornelli e sui bus."}
                </p>
              </div>

              <div className="rounded-[8px] border border-[#E5E3DE] bg-[#FFFFFF] p-3 space-y-1">
                <div className="flex items-center gap-1.5 font-semibold text-[#141A20]">
                  <span className="text-[#2D8A4E]">♿</span>
                  <span>{locale === "en" ? "Accessibility" : "Accessibilità & Servizi"}</span>
                </div>
                <p className="text-[var(--text-muted)] leading-relaxed">
                  {locale === "en"
                    ? "Metro Line 1 stations equipped with accessible elevators and tactile paving. Intermodal connection at Garibaldi & Municipio."
                    : "Stazioni Metro Linea 1 dotate di ascensori e percorsi tattili. Interscambio facilitato a Garibaldi e Municipio."}
                </p>
              </div>
            </div>

            {/* Interactive Deterministic Route Request Planner */}
            <div className="pt-2">
              <RouteRequestAssistant
                theme="light"
                locale={locale}
                compact
                onLocationSelected={handleLocationSelected}
              />
            </div>
          </>
        )}
      </div>
    </AppShell>
  );
}
