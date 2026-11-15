/**
 * @purpose Retrieval client-side dei PlanItem pertinenti per target
 * @contracts DecisionResponse, PlanItem, NarrativeItem
 * @tokens recipient
 * @verified 2026-11-15
 */

import type { DecisionResponse, NarrativeItem, PlanItem, Target } from "@/lib/types/contracts";

export type RecipientRetrievalItem = {
  planIndex: number;
  item: PlanItem;
  narrative?: NarrativeItem | undefined;
};

function normalize(value: string): string {
  return value
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^\p{L}\p{N}\s]/gu, " ")
    .replace(/\s+/g, " ")
    .trim();
}

const STOPWORDS = new Set(["come", "cosa", "dove", "posso", "oggi", "del", "della", "che", "per", "con", "gli", "non"]);

export function retrieve(
  query: string,
  target: Target,
  context: { decision: DecisionResponse | null },
): RecipientRetrievalItem[] {
  const decision = context.decision;
  if (!decision) return [];

  const narrativeByIndex = new Map(decision.narrative.items.map((item) => [item.plan_index, item]));
  const candidates = decision.decision.plan
    .map((item, planIndex) => ({ item, planIndex, narrative: narrativeByIndex.get(planIndex) }))
    .filter((entry) => entry.item.target === target);

  const normalizedQuery = normalize(query);
  const tokens = normalizedQuery.split(" ").filter((token) => token.length > 2 && !STOPWORDS.has(token));

  if (tokens.length === 0) {
    return candidates.sort((a, b) => a.item.priority - b.item.priority).slice(0, 3);
  }

  const scored = candidates
    .map((entry) => {
      const text = normalize(
        `${entry.item.action} ${entry.item.rationale} ${entry.narrative?.texts.it ?? ""} ${entry.narrative?.texts.en ?? ""}`,
      );
      const score = tokens.reduce((sum, token) => (text.includes(token) ? sum + 1 : sum), 0);
      return { entry, score };
    })
    .filter((entry) => entry.score > 0)
    .sort((a, b) => b.score - a.score || a.entry.item.priority - b.entry.item.priority)
    .map((entry) => entry.entry);

  if (scored.length > 0) return scored.slice(0, 3);

  // Richiesta generale: mostra le azioni più rilevanti per il target.
  return candidates.sort((a, b) => a.item.priority - b.item.priority).slice(0, 2);
}
