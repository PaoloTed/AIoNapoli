/**
 * @purpose Copioni delle conversazioni simulate per Cittadino e Turista
 * @contracts DecisionResponse, Target, RecipientChatMessage
 * @tokens recipient
 * @verified 2026-11-15
 */

import type { DecisionResponse, PlanItem, Target } from "@/lib/types/contracts";
import type { Locale } from "@/lib/state/store";
import type { RecipientChatMessage } from "./ChatMessage";
import type { RecipientRetrievalItem } from "./retrieval";

type DemoStep = {
  role: "user" | "assistant";
  it: string;
  en: string;
  planCount?: number;
};

const SCRIPTS: Record<"citizen" | "tourist", DemoStep[]> = {
  citizen: [
    {
      role: "user",
      it: "Devo andare in ufficio in centro: come arrivo da Bagnoli?",
      en: "I need to get to the office in the city centre: how do I get there from Bagnoli?",
    },
    {
      role: "assistant",
      it: "Oggi la Linea 2 è sospesa per cantiere. Questo è il percorso che ti consiglio, con i tempi aggiornati:",
      en: "Line 2 is suspended today due to construction. This is the route I recommend, with updated travel times:",
      planCount: 1,
    },
    {
      role: "user",
      it: "Quanto tempo ci vuole?",
      en: "How long does it take?",
    },
    {
      role: "assistant",
      it: "Circa 15 minuti: segui il percorso nella scheda qui sopra. Ho escluso la Linea 2 perché risulta bloccata.",
      en: "About 15 minutes: follow the route in the card above. I ruled out Line 2 because it is currently blocked.",
    },
    {
      role: "user",
      it: "Perché non posso usare la Linea 2?",
      en: "Why can't I use Line 2?",
    },
    {
      role: "assistant",
      it: "Perché è chiusa tra Campi Flegrei e Bagnoli per cantiere ANM: il sistema la scarta in anticipo e ti propone l'alternativa più sicura.",
      en: "Because it is closed between Campi Flegrei and Bagnoli for ANM works: the system discards it in advance and offers the safest alternative.",
    },
  ],
  tourist: [
    {
      role: "user",
      it: "Sono a Bagnoli per la regata: cosa posso visitare senza folla?",
      en: "I'm in Bagnoli for the regatta: what can I visit away from the crowds?",
    },
    {
      role: "assistant",
      it: "Bagnoli è molto affollata fino alle 20:00. Ti propongo l'alternativa più tranquilla, lontano dalla folla:",
      en: "Bagnoli is very crowded until 8 pm. Here is the calmest alternative, away from the crowds:",
      planCount: 1,
    },
    {
      role: "user",
      it: "Come ci arrivo?",
      en: "How do I get there?",
    },
    {
      role: "assistant",
      it: "Segui il percorso nella scheda: ho scelto l'opzione che evita la zona più affollata. Evita la Linea 2: è sospesa.",
      en: "Follow the route in the card: I picked the option that avoids the busiest area. Avoid Line 2: it is suspended.",
    },
    {
      role: "user",
      it: "C'è qualcosa da vedere vicino al porto?",
      en: "Is there anything to see near the port?",
    },
    {
      role: "assistant",
      it: "Sì: Municipio e Castel Nuovo sono raggiungibili a piedi da Mergellina. In alternativa, il centro storico è servito dal bus 151.",
      en: "Yes: Municipio and Castel Nuovo are within walking distance from Mergellina. Alternatively, bus 151 serves the historic centre.",
    },
  ],
};

function planEntries(decision: DecisionResponse | null, target: Target): RecipientRetrievalItem[] {
  if (!decision) return [];
  const narrativeByIndex = new Map(decision.narrative.items.map((item) => [item.plan_index, item]));
  const all = decision.decision.plan.map((item: PlanItem, planIndex: number) => ({
    item,
    planIndex,
    narrative: narrativeByIndex.get(planIndex),
  }));
  const forTarget = all.filter((entry) => entry.item.target === target);
  const pool = forTarget.length > 0 ? forTarget : all;
  return pool.sort((a, b) => a.item.priority - b.item.priority);
}

export function buildDemoMessages(
  target: "citizen" | "tourist",
  decision: DecisionResponse | null,
  lang: Locale,
): RecipientChatMessage[] {
  const pool = planEntries(decision, target);
  let cursor = 0;

  return SCRIPTS[target].map((step, index) => {
    const base: RecipientChatMessage = {
      id: `demo-${target}-${index}`,
      role: step.role,
      text: lang === "en" ? step.en : step.it,
    };
    if (step.planCount && step.planCount > 0) {
      const plans = pool.slice(cursor, cursor + step.planCount);
      cursor += plans.length;
      if (plans.length > 0) {
        return { ...base, plans };
      }
    }
    return base;
  });
}
