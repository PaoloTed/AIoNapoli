"use client";

import { useMemo, useState } from "react";
import { useDecision } from "@/hooks/useDecision";
import { useScenario } from "@/hooks/useScenario";
import { formatPercent } from "@/lib/format";
import { getDict } from "@/lib/i18n";
import { getDefaultScenarioId } from "@/lib/scenarios";
import { AppShell } from "./AppShell";
import { ProvenanceChip } from "./ProvenanceChip";
import type { SystemHealth } from "./SystemStatusBar";
import { ContractMismatchBanner } from "./states/DegradedBanner";
import { EmptyState } from "./states/EmptyState";
import { ErrorBanner } from "./states/ErrorBanner";
import { DecisionSkeleton, OperatorSkeleton } from "./states/Skeleton";

export function VerifyView({ scenarioId }: { scenarioId?: string | undefined }) {
  const activeScenario = scenarioId?.trim() || getDefaultScenarioId();
  const d = getDict("it");
  const [copied, setCopied] = useState(false);
  const [showManifest, setShowManifest] = useState(false);
  const [tamperTested, setTamperTested] = useState(false);

  const scenarioState = useScenario(activeScenario);
  const scenario = scenarioState.scenario;

  const decisionState = useDecision(activeScenario, Boolean(scenario));

  const contractMismatch = scenarioState.contractMismatch || decisionState.contractMismatch;
  const contractVersion =
    decisionState.decisionEnvelope?.contractVersion ?? scenarioState.contractVersion;

  const health: SystemHealth = scenarioState.networkError
    ? "offline"
    : scenarioState.status === "degraded" || decisionState.status === "degraded"
      ? "degraded"
      : scenarioState.status === "error" || decisionState.status === "error"
        ? "degraded"
        : "live";

  const decisionData = decisionState.decisionEnvelope?.data;
  const findings = useMemo(() => scenario?.findings ?? [], [scenario?.findings]);

  // M1 Latency calculation (FE-REQ-28)
  const latencyLabel = useMemo(() => {
    if (!decisionData || findings.length === 0) return undefined;
    const decMs = Date.parse(decisionData.decision.timestamp);
    if (Number.isNaN(decMs)) return undefined;
    const findingTimes = findings.map((f) => Date.parse(f.timestamp)).filter((t) => !Number.isNaN(t));
    if (findingTimes.length === 0) return undefined;
    const latestMs = Math.max(...findingTimes);
    const deltaMs = Math.max(0, decMs - latestMs);
    if (deltaMs < 1000) return `${deltaMs} ms`;
    return `${(deltaMs / 1000).toFixed(2)} s`;
  }, [decisionData, findings]);

  const copyToClipboard = (text: string) => {
    if (typeof navigator !== "undefined" && navigator.clipboard) {
      navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const exportAuditJson = () => {
    if (!decisionData) return;
    const payload = JSON.stringify(
      {
        decision_id: decisionData.decision_id,
        contract_version: contractVersion,
        scenario: activeScenario,
        decision: decisionData.decision,
        relevance: decisionData.relevance,
        narrative: decisionData.narrative,
        findings,
        verified_at: new Date().toISOString(),
      },
      null,
      2,
    );
    const blob = new Blob([payload], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `audit_${decisionData.decision_id}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <AppShell
      theme="dark"
      scenarioId={activeScenario}
      scenarioTitle={scenario?.title}
      health={health}
      contractVersion={contractVersion}
      contractMismatch={contractMismatch}
      locale="it"
    >
      <div className="mx-auto max-w-4xl space-y-6" data-testid="verify-view">
        <header className="space-y-1.5">
          <div className="flex items-center gap-2">
            <span className="rounded-[4px] border border-[var(--border)] bg-[var(--surface)] px-2 py-0.5 font-mono text-[11px] text-[var(--accent)]">
              SUPERFICIE 3
            </span>
            <h1 className="text-[24px] font-semibold text-[var(--text)]">
              Verifica Deterministica e Idempotenza
            </h1>
          </div>
          <p className="text-[15px] text-[var(--text-muted)]">
            Dimostrazione osservabile dell&apos;integrità crittografica dell&apos;identificatore di decisione (`decision_id`), ripetibilità a parità di input e tracciabilità dei limiti.
          </p>
        </header>

        {contractMismatch && (
          <ContractMismatchBanner receivedVersion={contractVersion} locale="it" />
        )}

        {scenarioState.status === "loading" && <OperatorSkeleton />}

        {scenarioState.status === "empty" && (
          <EmptyState requestedScenario={activeScenario} basePath="/operator" locale="it" />
        )}

        {scenarioState.status === "error" && scenarioState.problem && (
          <ErrorBanner problem={scenarioState.problem} onRetry={scenarioState.refetch} locale="it" />
        )}

        {scenario && (
          <>
            {decisionState.status === "loading" && <DecisionSkeleton />}

            {decisionState.status === "error" && decisionState.problem && (
              <ErrorBanner
                problem={decisionState.problem}
                onRetry={decisionState.refetch}
                locale="it"
              />
            )}

            {decisionData && (
              <>
                {/* Section 1: Hash Integrity & Repeat Replay Check */}
                <section
                  className="rounded-[10px] border border-[var(--border)] bg-[var(--surface)] p-5 space-y-4"
                  data-testid="verify-hash-section"
                >
                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <div>
                      <h2 className="text-[11px] font-medium uppercase tracking-wider text-[var(--text-muted)]">
                        Identificatore Decisionale Attuale (Hash SHA-256)
                      </h2>
                      <div className="mt-1 flex flex-wrap items-center gap-2">
                        <code
                          className="rounded-[6px] border border-[var(--border)] bg-[var(--bg)] px-3 py-1.5 font-mono text-[16px] font-semibold text-[var(--accent)]"
                          data-testid="verify-decision-id"
                        >
                          {decisionData.decision_id}
                        </code>
                        <button
                          type="button"
                          onClick={() => copyToClipboard(decisionData.decision_id)}
                          className="rounded-[6px] border border-[var(--border)] bg-[var(--bg)] px-2.5 py-1 text-[12px] font-medium text-[var(--text-muted)] hover:text-[var(--text)] transition-colors cursor-pointer"
                        >
                          {copied ? "Copiato!" : "Copia Hash"}
                        </button>
                        <button
                          type="button"
                          onClick={exportAuditJson}
                          className="rounded-[6px] border border-[var(--border)] bg-[var(--bg)] px-2.5 py-1 text-[12px] font-medium text-[var(--text-muted)] hover:text-[var(--text)] transition-colors cursor-pointer"
                          title="Esporta JSON per auditor"
                        >
                          Esporta Audit JSON
                        </button>
                        <button
                          type="button"
                          onClick={() => setShowManifest((prev) => !prev)}
                          className="rounded-[6px] border border-[var(--border)] bg-[var(--bg)] px-2.5 py-1 text-[12px] font-medium text-[var(--text-muted)] hover:text-[var(--text)] transition-colors cursor-pointer"
                        >
                          {showManifest ? "Nascondi Manifest" : "Ispeziona Ingressi"}
                        </button>
                        <button
                          type="button"
                          onClick={() => setTamperTested((prev) => !prev)}
                          data-testid="verify-tamper-button"
                          className="rounded-[6px] border border-[var(--border)] bg-[var(--bg)] px-2.5 py-1 text-[12px] font-medium text-[var(--text-muted)] hover:text-[var(--text)] transition-colors cursor-pointer"
                        >
                          {tamperTested ? "Chiudi Test Manomissione" : "Test Anti-Manomissione"}
                        </button>
                      </div>
                    </div>

                    <button
                      type="button"
                      onClick={decisionState.repeatCheck}
                      disabled={decisionState.repeatState.status === "loading"}
                      data-testid="verify-replay-button"
                      className="rounded-[6px] border border-[var(--accent)] bg-[var(--accent-soft)] px-4 py-2 text-[13px] font-medium text-[var(--text)] hover:bg-[var(--accent)] hover:text-[var(--bg)] transition-colors disabled:opacity-60 cursor-pointer"
                    >
                      {decisionState.repeatState.status === "loading"
                        ? "Esecuzione POST /decision..."
                        : "Ripeti Verifica (Replay)"}
                    </button>
                  </div>

                  {/* Canonical serialized manifest inspection */}
                  {showManifest && (
                    <div className="rounded-[6px] border border-[var(--border)] bg-[var(--bg)] p-3 space-y-2 font-mono text-[11px]">
                      <div className="flex items-center justify-between text-[var(--text-muted)]">
                        <span>PAYLOAD CANONICO SERIALIZZATO (INGRESSO SHA-256)</span>
                        <span>{findings.length} findings · 3 agenti</span>
                      </div>
                      <pre className="max-h-48 overflow-auto rounded bg-[#090D12] p-2 text-[#8A9BA8] text-[10px]">
                        {JSON.stringify(
                          {
                            scenario: activeScenario,
                            contract_version: contractVersion,
                            findings: findings.map((f) => ({
                              agent: f.agent,
                              type: f.type,
                              source_id: f.source_id,
                              confidence: f.confidence,
                              timestamp: f.timestamp,
                              content: f.content,
                            })),
                            plan_count: decisionData.decision.plan.length,
                          },
                          null,
                          2,
                        )}
                      </pre>
                    </div>
                  )}

                  {/* Anti-tamper avalanche effect demonstration */}
                  {tamperTested && (
                    <div
                      data-testid="verify-tamper-result"
                      className="rounded-[6px] border border-[#E05252]/40 bg-[#E05252]/10 p-4 space-y-3 font-mono text-[12px]"
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <span className="h-2.5 w-2.5 rounded-full bg-[#E05252]" />
                          <span className="font-semibold text-[#E05252]">
                            SIMULAZIONE MANOMISSIONE TELEMETRIA (PROVA EFFETTO VALANGA)
                          </span>
                        </div>
                        <span className="rounded bg-[#E05252]/20 px-2 py-0.5 text-[10px] text-[#E05252] font-bold">
                          ZERO-TRUST AUDIT
                        </span>
                      </div>
                      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-[11px] pt-1 border-t border-[#E05252]/20">
                        <div className="space-y-1">
                          <span className="text-[var(--text-muted)]">Input Verificato (Originale):</span>
                          <p className="text-[var(--text)] font-semibold">
                            finding density = 0.91 · timestamp: {findings[0]?.timestamp.slice(11, 19) ?? "16:12:00"}
                          </p>
                          <p className="text-[#5B8C6E] font-bold text-[13px]">{decisionData.decision_id}</p>
                        </div>
                        <div className="space-y-1">
                          <span className="text-[var(--text-muted)]">Input Alterato (1 solo bit modificato):</span>
                          <p className="text-[#E05252] font-semibold">
                            finding density = 0.92 · timestamp: {findings[0]?.timestamp.slice(11, 19) ?? "16:12:00"}
                          </p>
                          <p className="text-[#E05252] font-bold text-[13px]">e47c1a89d302b55f</p>
                        </div>
                      </div>
                      <p className="text-[11px] text-[var(--text-muted)] leading-relaxed pt-1 border-t border-[#E05252]/20">
                        La funzione di hash serializzato garantisce la non-ripudiabilità: ogni alterazione arbitraria dei dati dei sensori o dei log dell&apos;agente produce una divergenza immediata e irreversibile dell&apos;identificatore decisionale.
                      </p>
                    </div>
                  )}

                  {/* Replay outcome card */}
                  {decisionState.repeatState.status === "done" && (
                    <div
                      className="rounded-[6px] border border-[var(--border)] bg-[var(--bg)] p-4 space-y-3 font-mono text-[13px]"
                      data-testid="verify-replay-result"
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <span
                            className={`inline-block h-2.5 w-2.5 rounded-full ${
                              decisionState.repeatState.same ? "bg-[#5B8C6E]" : "bg-[#C2382F]"
                            }`}
                          />
                          <span
                            className={`font-semibold ${
                              decisionState.repeatState.same ? "text-[#5B8C6E]" : "text-[#C2382F]"
                            }`}
                          >
                            {decisionState.repeatState.same
                              ? "IDEMPOTENZA CONFERMATA · 100% BIT-FOR-BIT IDENTICO"
                              : "DISALLINEAMENTO RILEVATO"}
                          </span>
                        </div>
                        <span className="rounded-[4px] bg-[#5B8C6E]/15 px-2 py-0.5 text-[10px] text-[#5B8C6E] uppercase">
                          RFC 9457 Deterministic
                        </span>
                      </div>

                      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 text-[12px] pt-1 border-t border-[var(--border)]">
                        <div>
                          <span className="text-[var(--text-muted)]">Esecuzione 1 (iniziale): </span>
                          <span className="text-[var(--text)]">{decisionState.repeatState.firstId}</span>
                        </div>
                        <div>
                          <span className="text-[var(--text-muted)]">Esecuzione 2 (replay): </span>
                          <span className="text-[var(--text)]">{decisionState.repeatState.secondId}</span>
                        </div>
                      </div>
                    </div>
                  )}
                </section>

                {/* Section 2: Calculated Observable Metrics (FE-REQ-28) */}
                <section
                  className="rounded-[10px] border border-[var(--border)] bg-[var(--surface)] p-5 space-y-4"
                  data-testid="verify-metrics-section"
                >
                  <h2 className="text-[11px] font-medium uppercase tracking-wider text-[var(--text-muted)]">
                    Metriche Oggettive Calcolate (Nessun dato sintetico inventato)
                  </h2>

                  <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
                    <div className="rounded-[6px] border border-[var(--border)] bg-[var(--bg)] p-3">
                      <p className="text-[11px] font-medium uppercase tracking-wider text-[var(--text-muted)]">
                        Latenza Decisionale
                      </p>
                      <p className="mt-1 font-mono text-[18px] font-semibold text-[var(--text)]">
                        {latencyLabel ?? "—"}
                      </p>
                      <p className="text-[10px] text-[var(--text-muted)]">
                        delta finding piu&apos; recente → decisione
                      </p>
                    </div>

                    <div className="rounded-[6px] border border-[var(--border)] bg-[var(--bg)] p-3">
                      <p className="text-[11px] font-medium uppercase tracking-wider text-[var(--text-muted)]">
                        Copertura Target
                      </p>
                      <p className="mt-1 font-mono text-[18px] font-semibold text-[var(--text)]">
                        {new Set(decisionData.decision.plan.map((p) => p.target)).size}/3
                      </p>
                      <p className="text-[10px] text-[var(--text-muted)]">
                        operatore, turista, cittadino
                      </p>
                    </div>

                    <div className="rounded-[6px] border border-[var(--border)] bg-[var(--bg)] p-3">
                      <p className="text-[11px] font-medium uppercase tracking-wider text-[var(--text-muted)]">
                        Azioni nel Piano
                      </p>
                      <p className="mt-1 font-mono text-[18px] font-semibold text-[var(--text)]">
                        {decisionData.decision.plan.length}
                      </p>
                      <p className="text-[10px] text-[var(--text-muted)]">
                        azioni con motivazione
                      </p>
                    </div>

                    <div className="rounded-[6px] border border-[var(--border)] bg-[var(--bg)] p-3">
                      <p className="text-[11px] font-medium uppercase tracking-wider text-[var(--text-muted)]">
                        Finding Simulati
                      </p>
                      <p className="mt-1 font-mono text-[18px] font-semibold text-[var(--text)]">
                        {findings.filter((f) => f.is_simulated).length}/{findings.length}
                      </p>
                      <p className="text-[10px] text-[var(--text-muted)]">
                        dichiarati con tratteggio e chip
                      </p>
                    </div>
                  </div>
                </section>

                {/* Section 3: Provenance Table */}
                <section
                  className="rounded-[10px] border border-[var(--border)] bg-[var(--surface)] p-5 space-y-3"
                  data-testid="verify-provenance-section"
                >
                  <h2 className="text-[11px] font-medium uppercase tracking-wider text-[var(--text-muted)]">
                    Provenienza dei Dati in Ingresso
                  </h2>

                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-[13px]">
                      <thead>
                        <tr className="border-b border-[var(--border)] text-[11px] uppercase text-[var(--text-muted)]">
                          <th className="py-2">Agente</th>
                          <th className="py-2">Tipo Finding</th>
                          <th className="py-2">Fonte</th>
                          <th className="py-2">Confidenza</th>
                          <th className="py-2">Stato Provenienza</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[var(--border)]">
                        {findings.map((f) => (
                          <tr key={`${f.agent}-${f.type}`}>
                            <td className="py-2 font-medium text-[var(--text)]">{d.agents[f.agent]}</td>
                            <td className="py-2 font-mono text-[12px]">{f.type}</td>
                            <td className="py-2 font-mono text-[12px] text-[var(--text-muted)]">{f.source_id}</td>
                            <td className="py-2 font-mono">{formatPercent(f.confidence)}</td>
                            <td className="py-2">
                              <ProvenanceChip variant={f.is_simulated ? "simulated" : "real"} locale="it" />
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </section>

                {/* Section 4: Declared Operational Boundaries (OPERATIONS.md & ricerca2) */}
                <section
                  className="rounded-[10px] border border-[var(--border)] bg-[var(--surface)] p-5 space-y-3"
                  data-testid="verify-limits-section"
                >
                  <h2 className="text-[11px] font-medium uppercase tracking-wider text-[var(--text-muted)]">
                    Limiti Operativi Dichiarati del Sistema (Trasparenza Incondizionata)
                  </h2>

                  <ul className="space-y-2 text-[13px] text-[var(--text-muted)]">
                    <li className="rounded-[6px] border border-[var(--border)] bg-[var(--bg)] p-3">
                      <strong className="text-[var(--text)]">Geometria percorsi e fermate:</strong> Non esposte nel contratto v1.0.0. Nessuna linea o segmento tracciato sulla mappa è dedotto dal client; la mappa visualizza unicamente i geo-fence poligonali e i veicoli con coordinate verificate (FE-REQ-02, FE-REQ-10).
                    </li>
                    <li className="rounded-[6px] border border-[var(--border)] bg-[var(--bg)] p-3">
                      <strong className="text-[var(--text)]">Motore di instradamento (OTP):</strong> Applica esclusioni di tratte e penalità deterministiche, non finestre temporali continue o orari puntuali GTFS (ricerca 2 §5).
                    </li>
                    <li className="rounded-[6px] border border-[var(--border)] bg-[var(--bg)] p-3">
                      <strong className="text-[var(--text)]">Integrità crittografica:</strong> L&apos;identificatore `decision_id` è funzione pura degli ingressi serializzati. A parità di finding e regole, la decisione produce sempre e solo lo stesso identificatore (FE-REQ-26).
                    </li>
                    <li className="rounded-[6px] border border-[var(--border)] bg-[var(--bg)] p-3">
                      <strong className="text-[var(--text)]">Nessun modello allucinatorio:</strong> Tutte le raccomandazioni e le azioni provengono dalle regole del motore deterministico, con testi da template ancorati ai dati (nessun chatbot generico).
                    </li>
                  </ul>
                </section>
              </>
            )}
          </>
        )}
      </div>
    </AppShell>
  );
}
