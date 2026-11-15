/**
 * @purpose Pill di risposta rapida profilate per target
 * @contracts Target
 * @tokens recipient
 * @verified 2026-11-15
 */

"use client";

import { recipientTokens as t } from "@/styles/design-tokens-recipient";
import type { Target } from "@/lib/types/contracts";
import { citizenQuickActions, touristQuickActions } from "./intents";

export function QuickActions({ target, onSelect }: { target: Target; onSelect: (query: string) => void }) {
  const actions = target === "tourist" ? touristQuickActions : citizenQuickActions;
  const accent = target === "tourist" ? t.color.accent.tourist : t.color.accent.citizen;
  const light = target === "tourist" ? t.color.accent.touristLight : t.color.accent.citizenLight;

  return (
    <div style={{ display: "flex", gap: t.space[2], flexWrap: "wrap" }}>
      {actions.map((action) => (
        <button
          key={action}
          type="button"
          onClick={() => onSelect(action)}
          style={{
            border: `1px solid ${accent}33`,
            background: light,
            color: accent,
            borderRadius: t.radius.pill,
            padding: "8px 14px",
            fontSize: t.font.size.xs,
            fontWeight: t.font.weight.semibold,
            cursor: "pointer",
          }}
        >
          {action}
        </button>
      ))}
    </div>
  );
}
