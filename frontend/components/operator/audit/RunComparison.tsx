/**
 * @purpose Confronto strutturale tra decisione originale e riesecuzione
 * @contracts DecisionResponse
 * @tokens operator
 * @verified 2026-11-15
 */

import { operatorTokens as t } from "@/styles/design-tokens-operator";
import { Badge } from "@/components/ui/Badge";
import { formatPercent } from "@/lib/format";
import type { DecisionResponse } from "@/lib/types/contracts";

function fingerprint(payload: DecisionResponse): string {
  return JSON.stringify({
    trigger: payload.decision.trigger,
    conflict: payload.decision.conflict,
    plan: payload.decision.plan,
    reasoning: payload.decision.reasoning_log,
    confidence: payload.decision.confidence,
  });
}

function ComparisonRow({ label, original, rerun, same }: { label: string; original: string; rerun: string; same: boolean }) {
  const color = same ? t.color.severity.low : t.color.severity.critical;
  return (
    <tr>
      <th scope="row" style={{ textAlign: "left", padding: t.space[2], color: t.color.text.secondary, fontWeight: 500 }}>
        {label}
      </th>
      <td style={{ padding: t.space[2], color: t.color.text.primary }}>{original}</td>
      <td style={{ padding: t.space[2], color: t.color.text.primary }}>{rerun}</td>
      <td style={{ padding: t.space[2], color, fontWeight: 600 }}>{same ? "identico" : "diverso"}</td>
    </tr>
  );
}

export function RunComparison({ original, rerun }: { original: DecisionResponse; rerun: DecisionResponse }) {
  const planA = original.decision.plan.map((item) => `${item.priority}:${item.target}:${item.action}`).join(" | ");
  const planB = rerun.decision.plan.map((item) => `${item.priority}:${item.target}:${item.action}`).join(" | ");
  const reasoningA = original.decision.reasoning_log.map((step) => `${step.step}:${step.rule_applied}`).join(" | ");
  const reasoningB = rerun.decision.reasoning_log.map((step) => `${step.step}:${step.rule_applied}`).join(" | ");
  const identical = fingerprint(original) === fingerprint(rerun);

  return (
    <section
      style={{
        background: t.color.bg.panel,
        border: `1px solid ${identical ? `${t.color.severity.low}66` : `${t.color.severity.critical}66`}`,
        borderRadius: t.radius.md,
        padding: t.space[4],
        display: "grid",
        gap: t.space[3],
      }}
      aria-label="Confronto deterministico"
    >
      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: t.space[2], flexWrap: "wrap" }}>
        <h3 style={{ margin: 0, fontSize: t.font.size.lg }}>Originale vs riesecuzione</h3>
        <Badge tone="severity" severity={identical ? "low" : "critical"}>
          {identical ? "Identico (Deterministico)" : "Differenza rilevata"}
        </Badge>
      </header>
      <table style={{ width: "100%", borderCollapse: "collapse", fontSize: t.font.size.sm }}>
        <thead>
          <tr style={{ borderBottom: `1px solid ${t.color.border.subtle}` }}>
            <th scope="col" style={{ textAlign: "left", padding: t.space[2], color: t.color.text.muted }}>Campo</th>
            <th scope="col" style={{ textAlign: "left", padding: t.space[2], color: t.color.text.muted }}>Originale</th>
            <th scope="col" style={{ textAlign: "left", padding: t.space[2], color: t.color.text.muted }}>Rerun</th>
            <th scope="col" style={{ textAlign: "left", padding: t.space[2], color: t.color.text.muted }}>Esito</th>
          </tr>
        </thead>
        <tbody>
          <ComparisonRow label="decision_id" original={original.decision_id} rerun={rerun.decision_id} same={original.decision_id === rerun.decision_id} />
          <ComparisonRow label="Piano" original={planA} rerun={planB} same={planA === planB} />
          <ComparisonRow label="Reasoning" original={reasoningA} rerun={reasoningB} same={reasoningA === reasoningB} />
          <ComparisonRow
            label="Confidenza"
            original={formatPercent(original.decision.confidence)}
            rerun={formatPercent(rerun.decision.confidence)}
            same={original.decision.confidence === rerun.decision.confidence}
          />
        </tbody>
      </table>
    </section>
  );
}
