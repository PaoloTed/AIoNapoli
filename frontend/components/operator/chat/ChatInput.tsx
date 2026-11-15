/**
 * @purpose Campo di input chat con invio su Enter e nuova riga su Shift+Enter
 * @contracts nessuno
 * @tokens operator
 * @verified 2026-11-15
 */

"use client";

import { useState } from "react";
import { operatorTokens as t } from "@/styles/design-tokens-operator";

export function ChatInput({ onSend }: { onSend: (text: string) => void }) {
  const [value, setValue] = useState("");

  const submit = () => {
    const trimmed = value.trim();
    if (!trimmed) return;
    onSend(trimmed);
    setValue("");
  };

  return (
    <div style={{ display: "flex", gap: t.space[2], alignItems: "flex-end" }}>
      <textarea
        value={value}
        onChange={(event) => setValue(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === "Enter" && !event.shiftKey) {
            event.preventDefault();
            submit();
          }
        }}
        rows={2}
        placeholder="Chiedi del piano, degli scarti o delle evidenze…"
        aria-label="Domanda per l'assistente operativo"
        style={{
          flex: 1,
          resize: "none",
          background: t.color.bg.panel,
          border: `1px solid ${t.color.border.strong}`,
          borderRadius: t.radius.md,
          color: t.color.text.primary,
          padding: t.space[2],
          fontSize: t.font.size.base,
          fontFamily: "inherit",
        }}
      />
      <button
        type="button"
        onClick={submit}
        disabled={value.trim().length === 0}
        style={{
          background: t.color.accent.primary,
          color: t.color.text.inverse,
          border: "none",
          borderRadius: t.radius.md,
          padding: `${t.space[3]} ${t.space[4]}`,
          fontWeight: t.font.weight.semibold,
          cursor: value.trim().length === 0 ? "not-allowed" : "pointer",
          opacity: value.trim().length === 0 ? 0.5 : 1,
        }}
      >
        Invia
      </button>
    </div>
  );
}
