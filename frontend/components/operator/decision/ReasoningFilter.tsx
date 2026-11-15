/**
 * @purpose Toggle per isolare i soli step decisivi della timeline
 * @contracts nessuno
 * @tokens operator
 * @verified 2026-11-15
 */

"use client";

import { operatorTokens as t } from "@/styles/design-tokens-operator";

export function ReasoningFilter({
  decisiveOnly,
  onChange,
  total,
  decisive,
}: {
  decisiveOnly: boolean;
  onChange: (value: boolean) => void;
  total: number;
  decisive: number;
}) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: t.space[2], flexWrap: "wrap" }}>
      <button
        type="button"
        aria-pressed={decisiveOnly}
        onClick={() => onChange(!decisiveOnly)}
        style={{
          border: `1px solid ${decisiveOnly ? t.color.accent.primary : t.color.border.strong}`,
          background: decisiveOnly ? t.color.accent.muted : "transparent",
          color: decisiveOnly ? t.color.accent.primary : t.color.text.secondary,
          borderRadius: t.radius.pill,
          padding: `${t.space[1]} ${t.space[3]}`,
          fontSize: t.font.size.sm,
          cursor: "pointer",
        }}
      >
        Solo step decisivi
      </button>
      <span style={{ fontSize: t.font.size.xs, color: t.color.text.muted }}>
        {decisiveOnly ? `${decisive} di ${total}` : `${total} step`}
      </span>
    </div>
  );
}
