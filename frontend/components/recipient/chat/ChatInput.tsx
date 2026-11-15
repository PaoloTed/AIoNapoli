/**
 * @purpose Campo di input della chat recipient con segnaposto per target
 * @contracts Target
 * @tokens recipient
 * @verified 2026-11-15
 */

"use client";

import { useState } from "react";
import { recipientTokens as t } from "@/styles/design-tokens-recipient";
import type { Target } from "@/lib/types/contracts";

export function ChatInput({ target, onSend }: { target: Target; onSend: (text: string) => void }) {
  const [value, setValue] = useState("");
  const accent = target === "tourist" ? t.color.accent.tourist : t.color.accent.citizen;
  const placeholder =
    target === "tourist"
      ? "Chiedi cosa visitare o percorsi panoramici…"
      : "Chiedi come raggiungere un luogo o orari linee…";

  const submit = () => {
    const trimmed = value.trim();
    if (!trimmed) return;
    onSend(trimmed);
    setValue("");
  };

  return (
    <div
      style={{
        display: "flex",
        gap: t.space[2],
        alignItems: "center",
        background: t.color.bg.panel,
        border: `1px solid ${t.color.border.subtle}`,
        borderRadius: t.radius.pill,
        padding: "6px 6px 6px 16px",
      }}
    >
      <input
        value={value}
        onChange={(event) => setValue(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter") {
            event.preventDefault();
            submit();
          }
        }}
        placeholder={placeholder}
        aria-label="Messaggio per l'assistente"
        style={{
          flex: 1,
          border: "none",
          outline: "none",
          background: "transparent",
          color: t.color.text.primary,
          fontSize: t.font.size.sm,
          fontFamily: "inherit",
          minHeight: "32px",
        }}
      />
      <button
        type="button"
        onClick={submit}
        aria-label="Invia messaggio"
        style={{
          border: "none",
          borderRadius: "50%",
          width: "38px",
          height: "38px",
          background: accent,
          color: t.color.text.inverse,
          cursor: "pointer",
          fontSize: "16px",
        }}
      >
        ↑
      </button>
    </div>
  );
}
