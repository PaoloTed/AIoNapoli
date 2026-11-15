/**
 * @purpose Toggle animato Cittadino/Turista con cambio palette d'accento
 * @contracts Target
 * @tokens recipient
 * @verified 2026-11-15
 */

"use client";

import { recipientTokens as t } from "@/styles/design-tokens-recipient";
import type { Target } from "@/lib/types/contracts";

const OPTIONS: Array<{ value: "citizen" | "tourist"; label: string }> = [
  { value: "citizen", label: "Cittadino" },
  { value: "tourist", label: "Turista" },
];

export function TargetSwitch({ value, onChange }: { value: Target; onChange: (target: Target) => void }) {
  const active = value === "tourist" ? "tourist" : "citizen";
  const accent = active === "citizen" ? t.color.accent.citizen : t.color.accent.tourist;

  return (
    <div
      role="tablist"
      aria-label="Seleziona il destinatario"
      style={{
        display: "inline-flex",
        background: t.color.bg.panel,
        border: `1px solid ${t.color.border.subtle}`,
        borderRadius: t.radius.pill,
        padding: "4px",
        gap: "4px",
      }}
    >
      {OPTIONS.map((option) => {
        const selected = active === option.value;
        return (
          <button
            key={option.value}
            role="tab"
            aria-selected={selected}
            type="button"
            onClick={() => onChange(option.value)}
            style={{
              border: "none",
              borderRadius: t.radius.pill,
              padding: "8px 18px",
              fontSize: t.font.size.sm,
              fontWeight: t.font.weight.semibold,
              cursor: "pointer",
              background: selected ? accent : "transparent",
              color: selected ? t.color.text.inverse : t.color.text.secondary,
              transition: "background 250ms ease, color 250ms ease",
            }}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}
