/**
 * @purpose Pulsanti rapidi deterministici della chat operatore
 * @contracts nessuno
 * @tokens operator
 * @verified 2026-11-15
 */

"use client";

import { operatorTokens as t } from "@/styles/design-tokens-operator";
import { operatorQuickActions } from "./intents";

export function QuickActions({ onSelect }: { onSelect: (query: string) => void }) {
  return (
    <div style={{ display: "flex", flexWrap: "wrap", gap: t.space[2] }}>
      {operatorQuickActions.map((label) => (
        <button
          key={label}
          type="button"
          onClick={() => onSelect(label)}
          style={{
            border: `1px solid ${t.color.border.strong}`,
            background: t.color.bg.panel,
            color: t.color.text.secondary,
            borderRadius: t.radius.pill,
            padding: `${t.space[1]} ${t.space[3]}`,
            fontSize: t.font.size.sm,
            cursor: "pointer",
          }}
        >
          {label}
        </button>
      ))}
    </div>
  );
}
