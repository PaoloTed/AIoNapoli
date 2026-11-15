/**
 * @purpose Pagina pubblica AIoNapoli per cittadino e turista
 * @contracts ScenarioSnapshot, DecisionResponse
 * @tokens recipient
 * @verified 2026-11-15
 */

import { RecipientShell } from "@/components/recipient/RecipientShell";

export default function HomePage() {
  return <RecipientShell />;
}
