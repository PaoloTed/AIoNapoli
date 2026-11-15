/**
 * @purpose Messaggio chat operatore con bolla utente e card assistente
 * @contracts RetrievalResult
 * @tokens operator
 * @verified 2026-11-15
 */

"use client";

import { operatorTokens as t } from "@/styles/design-tokens-operator";
import { BrandLogo } from "@/components/brand/BrandLogo";
import { CitationCard } from "./CitationCard";
import type { RetrievalResult } from "./retrieval";

export type OperatorChatMessage = {
  id: string;
  role: "user" | "assistant";
  text: string;
  citations?: RetrievalResult[];
};

export function ChatMessage({
  message,
  onNavigate,
}: {
  message: OperatorChatMessage;
  onNavigate: (result: RetrievalResult) => void;
}) {
  if (message.role === "user") {
    return (
      <div style={{ display: "flex", justifyContent: "flex-end" }}>
        <p
          style={{
            margin: 0,
            maxWidth: "85%",
            background: t.color.bg.elevated,
            border: `1px solid ${t.color.border.strong}`,
            borderRadius: `${t.radius.lg} ${t.radius.lg} ${t.radius.sm} ${t.radius.lg}`,
            padding: `${t.space[2]} ${t.space[3]}`,
            fontSize: t.font.size.base,
            color: t.color.text.primary,
          }}
        >
          {message.text}
        </p>
      </div>
    );
  }

  return (
    <article
      style={{
        background: t.color.bg.panelAlt,
        border: `1px solid ${t.color.border.subtle}`,
        borderRadius: t.radius.lg,
        padding: t.space[3],
        display: "grid",
        gap: t.space[2],
      }}
    >
      <header style={{ display: "flex", alignItems: "center", gap: t.space[2] }}>
        <BrandLogo variant="icon" height={18} />
        <strong style={{ fontSize: t.font.size.sm, color: t.color.text.primary }}>
          Assistente operativo
        </strong>
        <span style={{ fontSize: t.font.size.xs, color: t.color.text.muted }}>
          retrieval locale deterministico
        </span>
      </header>
      <p style={{ margin: 0, fontSize: t.font.size.base, color: t.color.text.secondary }}>
        {message.text}
      </p>
      {message.citations && message.citations.length > 0 ? (
        <div style={{ display: "grid", gap: t.space[2] }}>
          {message.citations.map((citation) => (
            <CitationCard key={`${citation.type}-${citation.ref}`} result={citation} onNavigate={onNavigate} />
          ))}
        </div>
      ) : null}
    </article>
  );
}
