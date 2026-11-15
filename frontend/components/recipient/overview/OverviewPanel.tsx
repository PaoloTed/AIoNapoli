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
  onStartDemo,
}: {
  target: Target;
  findings: Finding[];
  decision: DecisionResponse | null;
  onOpenChat: () => void;
  onStartDemo: (target: Target) => void;
}) {
  const accent = target === "tourist" ? t.color.accent.tourist : t.color.accent.citizen;

  const demos: Array<{ value: "citizen" | "tourist"; label: string; icon: string }> = [
    { value: "citizen", label: "Cittadino · casa-ufficio", icon: "👤" },
    { value: "tourist", label: "Turista · visita senza folla", icon: "🧭" },
  ];

  return (
    <div style={{ display: "grid", gap: t.space[6] }}>
      <OverviewHeader findings={findings} target={target} />
      <StatusCardsRow findings={findings} target={target} />

      <section
        aria-label="Conversazioni simulate"
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
        <div style={{ display: "grid", gap: "4px", maxWidth: "420px" }}>
          <span
            style={{
              fontSize: t.font.size.xs,
              textTransform: "uppercase",
              letterSpacing: "0.1em",
              color: accent,
              fontWeight: t.font.weight.semibold,
            }}
          >
            Demo guidata
          </span>
          <strong style={{ fontSize: t.font.size.md, color: t.color.text.primary }}>
            Prova una conversazione simulata
          </strong>
          <span style={{ fontSize: t.font.size.sm, color: t.color.text.secondary, lineHeight: t.font.lineHeight.relaxed }}>
            Scegli uno use case: la chat risponde con i dati dello scenario, senza chiamate al backend.
          </span>
        </div>

        <div style={{ display: "flex", gap: t.space[2], flexWrap: "wrap" }}>
          {demos.map((demo) => {
            const color = demo.value === "tourist" ? t.color.accent.tourist : t.color.accent.citizen;
            const light = demo.value === "tourist" ? t.color.accent.touristLight : t.color.accent.citizenLight;
            const active = target === demo.value;
            return (
              <button
                key={demo.value}
                type="button"
                onClick={() => onStartDemo(demo.value)}
                aria-label={`Avvia demo ${demo.label}`}
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: "6px",
                  border: `1px solid ${color}55`,
                  borderRadius: t.radius.pill,
                  background: active ? color : light,
                  color: active ? t.color.text.inverse : color,
                  padding: "10px 16px",
                  fontSize: t.font.size.sm,
                  fontWeight: t.font.weight.semibold,
                  cursor: "pointer",
                }}
              >
                <span aria-hidden="true">{demo.icon}</span>
                {demo.label}
              </button>
            );
          })}
        </div>
      </section>

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
