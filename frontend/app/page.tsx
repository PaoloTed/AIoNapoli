/**
 * @purpose Pagina pubblica AIoNapoli per cittadino e turista
 * @contracts ScenarioSnapshot, DecisionResponse
 * @tokens recipient
 * @verified 2026-11-15
 */

import { RecipientApp } from "@/components/recipient/RecipientApp";
import { getDefaultScenarioId } from "@/lib/scenarios";

export default function HomePage() {
  return <RecipientApp scenarioId={getDefaultScenarioId()} />;
}
