/**
 * @purpose Layout del route group recipient: provider e bootstrap della superficie pubblica
 * @contracts nessuno
 * @tokens recipient
 * @verified 2026-11-15
 */

import type { ReactNode } from "react";
import { StoreProvider } from "@/lib/state/store";
import { RecipientBootstrap } from "@/components/recipient/RecipientBootstrap";
import { getDefaultScenarioId } from "@/lib/scenarios";

export default function RecipientLayout({ children }: { children: ReactNode }) {
  return (
    <StoreProvider>
      <RecipientBootstrap scenarioId={getDefaultScenarioId()}>{children}</RecipientBootstrap>
    </StoreProvider>
  );
}
