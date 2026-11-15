/**
 * @purpose Retrieval locale deterministico sui dati dello store per la chat operatore
 * @contracts ReasoningStep, Finding, PlanItem, TraceEvent, DecisionResponse
 * @tokens operator
 * @verified 2026-11-15
 */

import type { DecisionResponse, Finding, PlanItem, ReasoningStep } from "@/lib/types/contracts";
import type { TraceEvent } from "@/lib/types/trace";

export interface RetrievalResult {
  type: "reasoning" | "finding" | "plan" | "trace";
  label: string;
  ref: string;
  source: ReasoningStep | Finding | PlanItem | TraceEvent;
}

function normalize(value: string): string {
  return value
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^\p{L}\p{N}\s]/gu, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function tokenize(query: string): string[] {
  return normalize(query)
    .split(" ")
    .filter((token) => token.length > 2);
}

function scoreText(queryTokens: string[], text: string): number {
  const normalized = normalize(text);
  let score = 0;
  for (const token of queryTokens) {
    if (normalized.includes(token)) {
      score += normalized.startsWith(token) ? 2 : 1;
    }
  }
  return score;
}

export function retrieve(
  query: string,
  context: { decision: DecisionResponse | null; findings: Finding[]; traceEvents: TraceEvent[] },
): RetrievalResult[] {
  const tokens = tokenize(query);
  if (tokens.length === 0) return [];

  const scored: Array<{ score: number; result: RetrievalResult }> = [];

  const plan = context.decision?.decision.plan ?? [];
  plan.forEach((item, index) => {
    const score = scoreText(tokens, `${item.action} ${item.rationale} ${item.target}`);
    if (score > 0) {
      scored.push({
        score,
        result: {
          type: "plan",
          label: `Azione ${index + 1} · ${item.target}`,
          ref: `plan-${index}`,
          source: item,
        },
      });
    }
  });

  const reasoning = context.decision?.decision.reasoning_log ?? [];
  reasoning.forEach((step) => {
    const score = scoreText(tokens, `${step.outcome} ${step.rule_applied} ${step.agent}`);
    if (score > 0) {
      scored.push({
        score,
        result: {
          type: "reasoning",
          label: `Step ${step.step} · ${step.rule_applied}`,
          ref: `step-${step.step}`,
          source: step,
        },
      });
    }
  });

  context.findings.forEach((finding) => {
    const content = Object.values(finding.content).join(" ");
    const score = scoreText(tokens, `${finding.agent} ${finding.type} ${content}`);
    if (score > 0) {
      scored.push({
        score,
        result: {
          type: "finding",
          label: `Evidenza ${finding.agent} · ${finding.severity}`,
          ref: finding.data_reference,
          source: finding,
        },
      });
    }
  });

  context.traceEvents.forEach((event) => {
    const score = scoreText(tokens, `${event.event_type} ${JSON.stringify(event.data)}`);
    if (score > 0) {
      scored.push({
        score,
        result: {
          type: "trace",
          label: `Evento #${event.seq} · ${event.event_type}`,
          ref: `trace-${event.seq}`,
          source: event,
        },
      });
    }
  });

  return scored
    .sort((a, b) => b.score - a.score || a.result.label.localeCompare(b.result.label))
    .slice(0, 6)
    .map((entry) => entry.result);
}

export function summarizeResult(result: RetrievalResult): string {
  switch (result.type) {
    case "plan": {
      const item = result.source as PlanItem;
      return `${item.action}. Motivazione: ${item.rationale}`;
    }
    case "reasoning": {
      const step = result.source as ReasoningStep;
      return `${step.agent} ha applicato ${step.rule_applied}: ${step.outcome}`;
    }
    case "finding": {
      const finding = result.source as Finding;
      return `Evidenza ${finding.agent} (${finding.severity}, confidenza ${Math.round(finding.confidence * 100)}%).`;
    }
    default: {
      const event = result.source as TraceEvent;
      return `Evento ${event.event_type} alla sequenza ${event.seq}.`;
    }
  }
}
