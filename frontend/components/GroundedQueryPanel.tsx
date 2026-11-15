"use client";

import { useState } from "react";
import type { DecisionResponse, Finding, Refusal } from "@/lib/contracts";
import type { Locale } from "@/lib/format";

export type GroundedQueryPanelProps = {
  decisionResponse?: DecisionResponse | undefined;
  findings: Finding[];
  refusal?: Refusal | undefined;
  locale?: Locale;
};

export type GroundedCitation = {
  source: string;
  field: string;
  value: string;
};

export type QueryResult = {
  matched: boolean;
  intent: string;
  answer: string;
  citations: GroundedCitation[];
};

export function evaluateGroundedQuery(
  rawQuery: string,
  decisionResponse: DecisionResponse | undefined,
  findings: Finding[],
  refusal: Refusal | undefined,
): QueryResult {
  const query = rawQuery.toLowerCase().trim();
  const decision = decisionResponse?.decision;

  if (!query) {
    return {
      matched: false,
      intent: "empty",
      answer: "Digita una domanda sui dati a schermo o seleziona una richiesta predefinita.",
      citations: [],
    };
  }

  // Intent 1: Scarto / Conflitto / Linea
  if (
    query.includes("scart") ||
    query.includes("conflitto") ||
    query.includes("perche") ||
    query.includes("perché") ||
    query.includes("linea")
  ) {
    if (decision?.conflict.detected) {
      return {
        matched: true,
        intent: "conflict_resolution",
        answer: `La linea originaria è stata scartata: ${decision.conflict.description}. È stato applicato il ricalcolo di deflusso prioritario.`,
        citations: [
          { source: "decision.conflict", field: "description", value: decision.conflict.description },
          { source: "decision.trigger", field: "rule_id", value: decision.trigger.rule_id },
          {
            source: "decision.trigger",
            field: "agents_involved",
            value: decision.trigger.agents_involved.join(", "),
          },
        ],
      };
    }
    return {
      matched: true,
      intent: "no_conflict",
      answer: "Nessun percorso è stato scartato: le soglie operative rientrano nella norma e il piano è nominale.",
      citations: [
        { source: "decision.conflict", field: "detected", value: "false" },
      ],
    };
  }

  // Intent 2: Dati mancanti / Rifiuti / Simulati
  if (
    query.includes("mancan") ||
    query.includes("rifiut") ||
    query.includes("simulat") ||
    query.includes("attendibil") ||
    query.includes("fonti")
  ) {
    const simCount = findings.filter((f) => f.is_simulated).length;
    const citations: GroundedCitation[] = findings.map((f) => ({
      source: f.source_id,
      field: `${f.agent}.is_simulated`,
      value: f.is_simulated ? "SIMULATO" : "REALE",
    }));

    if (refusal) {
      citations.push({
        source: `refusal.${refusal.agent}`,
        field: "reason_code",
        value: refusal.reason_code,
      });
      return {
        matched: true,
        intent: "missing_data_refusal",
        answer: `L'agente ${refusal.agent} ha rifiutato la valutazione (motivo: ${refusal.reason_code}). Presenti ${simCount} finding simulati su ${findings.length} totali.`,
        citations,
      };
    }

    return {
      matched: true,
      intent: "simulated_data_summary",
      answer: `Tutti gli agenti hanno risposto. ${simCount} finding su ${findings.length} sono contrassegnati come simulati con bordo tratteggiato.`,
      citations,
    };
  }

  // Intent 3: Tempo / Latenza / Durata
  if (
    query.includes("tempo") ||
    query.includes("quant") ||
    query.includes("latenza") ||
    query.includes("secondi") ||
    query.includes("ora")
  ) {
    if (decision && findings.length > 0) {
      const decMs = Date.parse(decision.timestamp);
      const findingTimes = findings.map((f) => Date.parse(f.timestamp)).filter((t) => !Number.isNaN(t));
      const latestMs = findingTimes.length > 0 ? Math.max(...findingTimes) : decMs;
      const deltaMs = Math.max(0, decMs - latestMs);
      const latencyStr = deltaMs < 1000 ? `${deltaMs} ms` : `${(deltaMs / 1000).toFixed(2)} s`;

      return {
        matched: true,
        intent: "latency_metric",
        answer: `Latenza della decisione: ${latencyStr} tra il finding più recente e il timestamp di consolidamento della trace.`,
        citations: [
          { source: "decision", field: "timestamp", value: decision.timestamp },
          { source: "findings", field: "latest_timestamp", value: new Date(latestMs).toISOString() },
        ],
      };
    }
  }

  // Intent 4: Limiti del sistema / fermate / percorsi
  if (
    query.includes("limit") ||
    query.includes("cosa non") ||
    query.includes("fermat") ||
    query.includes("percorso") ||
    query.includes("mappa")
  ) {
    return {
      matched: true,
      intent: "system_boundaries",
      answer: "I percorsi continui e le fermate intermedie non sono inclusi nel contratto v1.0.0: il sistema applica filtri e penalità ad albero sulle zone e sui mezzi, senza dedurre geometrie lato client.",
      citations: [
        { source: "OPERATIONS.md", field: "section", value: "3.1 Limiti noti" },
        { source: "UI-REQUIREMENTS.md", field: "rule", value: "FE-REQ-02, FE-REQ-10" },
      ],
    };
  }

  // Intent 5: Fuori perimetro (Out of bounds)
  return {
    matched: false,
    intent: "out_of_bounds",
    answer: "Dato non disponibile nei campi verificati del contratto v1.0.0. Questo sistema non genera risposte allucinate: risponde unicamente su evidenze strutturate e tracciate.",
    citations: [
      { source: "Contratto", field: "status", value: "Dato assente nel modello" },
    ],
  };
}

export function GroundedQueryPanel({
  decisionResponse,
  findings,
  refusal,
}: GroundedQueryPanelProps) {
  const [query, setQuery] = useState("");
  const [activeResult, setActiveResult] = useState<QueryResult | null>(null);

  const presets = [
    "Perché hai scartato la linea?",
    "Quali dati mancano o sono simulati?",
    "Quanto ci ha messo a decidere?",
    "Quali sono i limiti del sistema?",
  ];

  const handleAsk = (textToAsk: string) => {
    const q = textToAsk.trim();
    if (!q) return;
    setQuery(q);
    const result = evaluateGroundedQuery(q, decisionResponse, findings, refusal);
    setActiveResult(result);
  };

  return (
    <section
      className="rounded-[10px] border border-[var(--border)] bg-[var(--surface)] p-4 space-y-4"
      data-testid="grounded-query-panel"
      aria-label="Interrogazione Grounded"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <span className="text-[11px] font-medium uppercase tracking-wider text-[var(--accent)]">
            Interrogazione Grounded
          </span>
          <span className="rounded-[4px] border border-[var(--border)] bg-[var(--bg)] px-2 py-0.5 font-mono text-[11px] text-[var(--text-muted)]">
            Zero Allucinazioni
          </span>
        </div>
        <span className="text-[12px] text-[var(--text-muted)]">
          Ancorata ai dati del contratto v1.0.0
        </span>
      </div>

      {/* Preset question pills */}
      <div className="flex flex-wrap gap-2">
        {presets.map((p) => (
          <button
            key={p}
            type="button"
            onClick={() => handleAsk(p)}
            className="rounded-[6px] border border-[var(--border)] bg-[var(--bg)] px-2.5 py-1 text-[12px] text-[var(--text-muted)] hover:border-[var(--accent)] hover:text-[var(--text)] transition-colors"
          >
            {p}
          </button>
        ))}
      </div>

      {/* Query form */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          handleAsk(query);
        }}
        className="flex gap-2"
      >
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Fai una domanda specifica sui dati a schermo..."
          data-testid="grounded-query-input"
          className="flex-1 rounded-[6px] border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-[14px] text-[var(--text)] placeholder-[var(--text-muted)] focus:outline-hidden"
        />
        <button
          type="submit"
          data-testid="grounded-query-submit"
          className="rounded-[6px] border border-[var(--accent)] bg-[var(--accent-soft)] px-4 py-2 text-[13px] font-medium text-[var(--text)] hover:bg-[var(--accent)] hover:text-[var(--bg)] transition-colors"
        >
          Interroga
        </button>
      </form>

      {/* Result container */}
      {activeResult && (
        <div
          className={`rounded-[6px] border p-4 space-y-3 ${
            activeResult.matched
              ? "border-[var(--border)] bg-[var(--bg)]"
              : "border border-dashed border-[var(--border)] bg-[var(--bg)] opacity-90"
          }`}
          data-testid="grounded-query-result"
        >
          <div className="flex items-center justify-between">
            <span
              className={`text-[11px] font-medium uppercase tracking-wider ${
                activeResult.matched ? "text-[#5B8C6E]" : "text-[var(--text-muted)]"
              }`}
            >
              {activeResult.matched ? "RISPOSTA CON VALIDAZIONE E CITAZIONE FONTE" : "RISPOSTA DETERMINISTICA (FUORI PERIMETRO)"}
            </span>
            <code className="font-mono text-[11px] text-[var(--text-muted)]">
              intent: {activeResult.intent}
            </code>
          </div>

          <p className="text-[15px] font-medium text-[var(--text)] leading-relaxed" data-testid="grounded-answer-text">
            {activeResult.answer}
          </p>

          {activeResult.citations.length > 0 && (
            <div className="pt-2 border-t border-[var(--border)] space-y-1.5" data-testid="grounded-citations">
              <span className="text-[11px] font-medium uppercase tracking-wider text-[var(--text-muted)]">
                Fonti ed evidenze citate:
              </span>
              <div className="flex flex-wrap gap-2">
                {activeResult.citations.map((c, i) => (
                  <span
                    key={`${c.source}-${c.field}-${i}`}
                    className="inline-flex items-center gap-1 rounded-[4px] border border-[var(--border)] bg-[var(--surface)] px-2 py-0.5 font-mono text-[11px]"
                  >
                    <span className="text-[var(--accent)] font-semibold">{c.source}</span>
                    <span className="text-[var(--text-muted)]">.{c.field}=</span>
                    <span className="text-[var(--text)] truncate max-w-[200px]">{c.value}</span>
                  </span>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
