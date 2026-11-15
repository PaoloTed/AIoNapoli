/**
 * @purpose Scheda di citazione verificabile verso reasoning, piano o finding
 * @contracts ReasoningStep, PlanItem, Finding, TraceEvent
 * @tokens operator
 * @verified 2026-11-15
 */

"use client";

import { operatorTokens as t } from "@/styles/design-tokens-operator";
import { Badge } from "@/components/ui/Badge";
import type { RetrievalResult } from "./retrieval";
import { summarizeResult } from "./retrieval";

const TYPE_LABEL: Record<RetrievalResult["type"], string> = {
  reasoning: "Reasoning",
  finding: "Finding",
  plan: "Piano",
  trace: "Trace",
};

export function CitationCard({
  result,
  onNavigate,
}: {
  result: RetrievalResult;
  onNavigate: (result: RetrievalResult) => void;
}) {
  return (
    <button
      type="button"
      onClick={() => onNavigate(result)}
      style={{
        display: "block",
        width: "100%",
        textAlign: "left",
        background: t.color.bg.panelAlt,
        border: `1px solid ${t.color.border.subtle}`,
        borderRadius: t.radius.md,
        padding: t.space[3],
        cursor: "pointer",
        color: t.color.text.primary,
      }}
    >
      <span style={{ display: "flex", alignItems: "center", gap: t.space[2], marginBottom: t.space[1] }}>
        <Badge tone="accent">{TYPE_LABEL[result.type]}</Badge>
        <strong style={{ fontSize: t.font.size.sm }}>{result.label}</strong>
      </span>
      <span style={{ display: "block", fontSize: t.font.size.base, color: t.color.text.secondary }}>
        {summarizeResult(result)}
      </span>
      <span style={{ display: "block", marginTop: t.space[2], fontSize: t.font.size.xs, color: t.color.accent.primary }}>
        Vedi nella timeline →
      </span>
    </button>
  );
}
