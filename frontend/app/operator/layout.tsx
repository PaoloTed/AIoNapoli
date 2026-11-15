/**
 * @purpose Layout della superficie operatore: provider di stato e shell persistente
 * @contracts nessuno
 * @tokens operator
 * @verified 2026-11-15
 */

import type { ReactNode } from "react";
import { StoreProvider } from "@/lib/state/store";
import { OperatorShell } from "@/components/operator/shell/OperatorShell";
import { getDefaultScenarioId } from "@/lib/scenarios";

export default function OperatorLayout({ children }: { children: ReactNode }) {
  const scenarioId = getDefaultScenarioId();
  return (
    <StoreProvider>
      <OperatorShell scenarioId={scenarioId}>{children}</OperatorShell>
    </StoreProvider>
  );
}
