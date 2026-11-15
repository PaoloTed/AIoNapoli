/**
 * @purpose Bootstrap client della superficie recipient (scenario, decisione, stream)
 * @contracts ScenarioSnapshot, DecisionResponse
 * @tokens recipient
 * @verified 2026-11-15
 */

"use client";

import type { ReactNode } from "react";
import { useAppStore } from "@/lib/state/store";
import { useBootstrapScenario } from "@/lib/state/useBootstrap";
import { useSSEStream } from "@/lib/sse/useSSEStream";

export function RecipientBootstrap({
  scenarioId,
  children,
}: {
  scenarioId: string;
  children: ReactNode;
}) {
  const { isSimulated } = useAppStore();
  const { loading } = useBootstrapScenario(scenarioId);
  useSSEStream(scenarioId, { enabled: !loading, simulated: isSimulated });
  return <>{children}</>;
}
