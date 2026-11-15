/**
 * @purpose Messaggio chat recipient: bolla utente e card operative assistente
 * @contracts PlanItem, NarrativeItem
 * @tokens recipient
 * @verified 2026-11-15
 */

"use client";

import { recipientTokens as t } from "@/styles/design-tokens-recipient";
import type { Target } from "@/lib/types/contracts";
import type { Locale } from "@/lib/state/store";
import { PlanCard } from "./PlanCard";
import type { RecipientRetrievalItem } from "./retrieval";

export type RecipientChatMessage = {
  id: string;
  role: "user" | "assistant";
  text: string;
  plans?: RecipientRetrievalItem[];
};

export function ChatMessage({
  message,
  target,
  lang,
}: {
  message: RecipientChatMessage;
  target: Target;
  lang: Locale;
}) {
  const accent = target === "tourist" ? t.color.accent.tourist : t.color.accent.citizen;

  if (message.role === "user") {
    return (
      <div style={{ display: "flex", justifyContent: "flex-end" }}>
        <p
          style={{
            margin: 0,
            maxWidth: "85%",
            background: accent,
            color: t.color.text.inverse,
            borderRadius: "20px 20px 6px 20px",
            padding: "12px 16px",
            fontSize: t.font.size.sm,
            boxShadow: t.shadow.soft,
          }}
        >
          {message.text}
        </p>
      </div>
    );
  }

  return (
    <div style={{ display: "grid", gap: t.space[2] }}>
      <p style={{ margin: 0, fontSize: t.font.size.sm, color: t.color.text.secondary }}>{message.text}</p>
      {message.plans?.map((plan) => (
        <PlanCard
          key={`${message.id}-${plan.planIndex}`}
          item={plan.item}
          narrative={plan.narrative}
          lang={lang}
          target={target}
        />
      ))}
    </div>
  );
}
