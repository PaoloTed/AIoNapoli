/**
 * @purpose Scheda d'azione recipient con narrativa localizzata e tempo stimato
 * @contracts PlanItem, NarrativeItem
 * @tokens recipient
 * @verified 2026-11-15
 */

"use client";

import { useState } from "react";
import { recipientTokens as t } from "@/styles/design-tokens-recipient";
import { extractEstimatedTimeFromAction, formatPercent } from "@/lib/format";
import type { PlanItem, NarrativeItem } from "@/lib/types/contracts";
import type { Locale } from "@/lib/state/store";
import type { Target } from "@/lib/types/contracts";

export function PlanCard({
  item,
  narrative,
  lang,
  target,
}: {
  item: PlanItem;
  narrative?: NarrativeItem | undefined;
  lang: Locale;
  target: Target;
}) {
  const [accepted, setAccepted] = useState(false);
  const accent = target === "tourist" ? t.color.accent.tourist : t.color.accent.citizen;
  const text = narrative?.texts[lang] ?? narrative?.texts.it ?? item.action;
  const secondary = narrative && narrative.texts.it !== text ? narrative.texts.it : undefined;
  const estimate = extractEstimatedTimeFromAction(`${item.action} ${text}`);

  return (
    <article
      style={{
        background: t.color.bg.elevated,
        border: `1px solid ${t.color.border.subtle}`,
        borderLeft: `4px solid ${accent}`,
        borderRadius: t.radius.lg,
        padding: t.space[4],
        boxShadow: t.shadow.soft,
        display: "grid",
        gap: t.space[2],
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", gap: t.space[2], alignItems: "start" }}>
        <strong style={{ fontSize: t.font.size.md, color: t.color.text.primary, lineHeight: 1.4 }}>{text}</strong>
        <span
          style={{
            flexShrink: 0,
            fontSize: t.font.size.xs,
            fontWeight: t.font.weight.semibold,
            color: accent,
            background: target === "tourist" ? t.color.accent.touristLight : t.color.accent.citizenLight,
            borderRadius: t.radius.pill,
            padding: "4px 10px",
          }}
        >
          priorità {item.priority}
        </span>
      </div>

      <p style={{ margin: 0, fontSize: t.font.size.sm, color: t.color.text.secondary }}>{item.rationale}</p>
      {secondary ? (
        <p style={{ margin: 0, fontSize: t.font.size.xs, color: t.color.text.muted }} lang="it">
          {secondary}
        </p>
      ) : null}

      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: t.space[2], flexWrap: "wrap" }}>
        <span style={{ fontSize: t.font.size.xs, color: t.color.text.muted }}>
          {estimate ? `tempo stimato ${estimate}` : `confidenza piano ${formatPercent(item.priority === 1 ? 0.9 : 0.8)}`}
        </span>
        <button
          type="button"
          onClick={() => setAccepted((value) => !value)}
          style={{
            border: "none",
            borderRadius: t.radius.pill,
            padding: "10px 18px",
            fontSize: t.font.size.sm,
            fontWeight: t.font.weight.semibold,
            cursor: "pointer",
            background: accepted ? t.color.bg.panel : accent,
            color: accepted ? accent : t.color.text.inverse,
            boxShadow: accepted ? "none" : t.shadow.soft,
          }}
        >
          {accepted ? "✓ Percorso accettato" : "Accetta percorso"}
        </button>
      </div>
    </article>
  );
}
