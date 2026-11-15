/**
 * @purpose Riga orizzontale scorrevole di status card
 * @contracts Finding, Target
 * @tokens recipient
 * @verified 2026-11-15
 */

"use client";

import { recipientTokens as t } from "@/styles/design-tokens-recipient";
import type { Finding, Target } from "@/lib/types/contracts";
import { StatusCard } from "./StatusCard";
import { deriveStatusCards } from "./derive";

export function StatusCardsRow({ findings, target }: { findings: Finding[]; target: Target }) {
  const cards = deriveStatusCards(findings, target);
  return (
    <div
      style={{
        display: "flex",
        gap: t.space[3],
        overflowX: "auto",
        paddingBottom: t.space[1],
        scrollSnapType: "x mandatory",
      }}
      aria-label="Stato della città"
    >
      {cards.map((card) => (
        <div key={card.title} style={{ scrollSnapAlign: "start", display: "flex", flex: "1 1 220px" }}>
          <StatusCard {...card} />
        </div>
      ))}
    </div>
  );
}
