/**
 * @purpose Bootstrap e provider della superficie recipient
 * @contracts ScenarioSnapshot, DecisionResponse
 * @tokens recipient
 * @verified 2026-11-15
 */

"use client";

import { StoreProvider, useAppStore } from "@/lib/state/store";
import { useBootstrapScenario } from "@/lib/state/useBootstrap";
import { useSSEStream } from "@/lib/sse/useSSEStream";
import { RecipientShell } from "./RecipientShell";

function RecipientSurface({ scenarioId }: { scenarioId: string }) {
  const { isSimulated } = useAppStore();
  const { loading } = useBootstrapScenario(scenarioId);
  useSSEStream(scenarioId, { enabled: !loading, simulated: isSimulated });
  return <RecipientShell />;
}

export function RecipientApp({ scenarioId }: { scenarioId: string }) {
  return (
    <StoreProvider>
      <RecipientSurface scenarioId={scenarioId} />
    </StoreProvider>
  );
}
