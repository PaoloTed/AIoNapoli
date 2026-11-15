/**
 * @purpose Overview recipient: messaggio contestuale, status card e mappa
 * @contracts Finding, DecisionResponse, Target
 * @tokens recipient
 * @verified 2026-11-15
 */

"use client";

import { recipientTokens as t } from "@/styles/design-tokens-recipient";
import type { DecisionResponse, Finding, Target } from "@/lib/types/contracts";
import { OverviewHeader } from "./OverviewHeader";
import { StatusCardsRow } from "./StatusCardsRow";
import { SimplifiedMap } from "./SimplifiedMap";

export function OverviewPanel({
  target,
  findings,
  decision,
  onOpenChat,
}: {
  target: Target;
  findings: Finding[];
  decision: DecisionResponse | null;
  onOpenChat: () => void;
}) {
  const accent = target === "tourist" ? t.color.accent.tourist : t.color.accent.citizen;

  return (
    <div style={{ display: "grid", gap: t.space[6] }}>
      <OverviewHeader findings={findings} target={target} />
      <StatusCardsRow findings={findings} target={target} />

      {decision?.decision.conflict.detected ? (
        <div
          style={{
            background: t.color.bg.panel,
            border: `1px solid ${t.color.border.subtle}`,
            borderRadius: t.radius.lg,
            padding: t.space[4],
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            gap: t.space[3],
            flexWrap: "wrap",
          }}
        >
          <span style={{ fontSize: t.font.size.sm, color: t.color.text.secondary }}>
            Gli agenti stanno gestendo una situazione complessa: chiedi come evitarla.
          </span>
          <button
            type="button"
            onClick={onOpenChat}
            style={{
              border: "none",
              borderRadius: t.radius.pill,
              background: accent,
              color: t.color.text.inverse,
              padding: "10px 18px",
              fontSize: t.font.size.sm,
              fontWeight: t.font.weight.semibold,
              cursor: "pointer",
            }}
          >
            Chiedi all&apos;assistente
          </button>
        </div>
      ) : null}

      <SimplifiedMap findings={findings} />
    </div>
  );
}
