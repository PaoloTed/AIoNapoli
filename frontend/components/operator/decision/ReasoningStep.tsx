/**
 * @purpose Nodo della timeline di reasoning con badge agente, regola ed esito
 * @contracts ReasoningStep
 * @tokens operator
 * @verified 2026-11-15
 */

import { operatorTokens as t } from "@/styles/design-tokens-operator";
import { Badge } from "@/components/ui/Badge";
import type { ReasoningStep as ReasoningStepModel } from "@/lib/types/contracts";

const DECISIVE_RULES = new Set(["P1", "P2", "P3", "R1_line2_crowding", "R2_conflict_route_vs_density", "R3_weather_capacity", "R4_event_surge"]);

export function isDecisive(step: ReasoningStepModel): boolean {
  return DECISIVE_RULES.has(step.rule_applied);
}

export function ReasoningStep({ step, last }: { step: ReasoningStepModel; last: boolean }) {
  const decisive = isDecisive(step);
  return (
    <li
      id={`step-${step.step}`}
      style={{
        position: "relative",
        paddingLeft: t.space[6],
        paddingBottom: last ? 0 : t.space[6],
        listStyle: "none",
      }}
    >
      <span
        aria-hidden="true"
        style={{
          position: "absolute",
          left: "7px",
          top: "4px",
          width: "12px",
          height: "12px",
          borderRadius: "50%",
          background: decisive ? t.color.accent.primary : t.color.bg.panelAlt,
          border: `2px solid ${decisive ? t.color.accent.primary : t.color.border.strong}`,
        }}
      />
      {!last ? (
        <span
          aria-hidden="true"
          style={{
            position: "absolute",
            left: "12px",
            top: "20px",
            bottom: 0,
            width: "2px",
            background: t.color.border.subtle,
          }}
        />
      ) : null}

      <article
        style={{
          display: "grid",
          gap: t.space[1],
          background: decisive ? t.color.accent.muted : t.color.bg.panel,
          border: `1px solid ${decisive ? `${t.color.accent.primary}55` : t.color.border.subtle}`,
          borderRadius: t.radius.md,
          padding: t.space[3],
        }}
      >
        <header style={{ display: "flex", alignItems: "center", gap: t.space[2], flexWrap: "wrap" }}>
          <span style={{ fontSize: t.font.size.xs, color: t.color.text.muted }}>STEP {step.step}</span>
          <Badge tone="neutral">{step.agent}</Badge>
          <code style={{ fontSize: t.font.size.xs, color: t.color.accent.primary }}>{step.rule_applied}</code>
        </header>
        <p style={{ margin: 0, fontSize: t.font.size.base, color: t.color.text.primary }}>{step.outcome}</p>
        <code style={{ fontSize: t.font.size.xs, color: t.color.text.muted }}>finding: {step.finding_ref}</code>
      </article>
    </li>
  );
}
