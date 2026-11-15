import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { RouteRequestAssistant } from "@/components/RouteRequestAssistant";
import { getDict } from "@/lib/i18n";
import { getConfiguredScenarios, getDefaultScenarioId } from "@/lib/scenarios";

const SCENARIO_LABELS: Record<string, string> = {
  bagnoli: "Regata America's Cup · Linea 2 ferma",
  garibaldi: "Congestione Garibaldi",
  sciopero: "Sciopero ANM 24h",
};

export default function HomePage() {
  const d = getDict("it");
  const defaultScenario = getDefaultScenarioId();
  const availableScenarios = getConfiguredScenarios();

  // If scenario is passed via query param, use it
  const cards = [
    {
      key: "operator" as const,
      href: `/operator?scenario=${encodeURIComponent(defaultScenario)}`,
      tag: "Superficie 1 · Sala Operativa",
      title: d.home.cards.operator.title,
      description: d.home.cards.operator.description,
      cta: d.home.cards.operator.cta,
      themeTag: "Registro Scuro #0B1016 · Telemetria SSE",
    },
    {
      key: "tourist" as const,
      href: `/tourist?scenario=${encodeURIComponent(defaultScenario)}`,
      tag: "Superficie 2A · Guida Turista",
      title: d.home.cards.tourist.title,
      description: d.home.cards.tourist.description,
      cta: d.home.cards.tourist.cta,
      themeTag: "Registro Chiaro #FAFAF8 · IT / EN",
    },
    {
      key: "citizen" as const,
      href: `/citizen?scenario=${encodeURIComponent(defaultScenario)}`,
      tag: "Superficie 2B · Guida Cittadino",
      title: d.home.cards.citizen.title,
      description: d.home.cards.citizen.description,
      cta: d.home.cards.citizen.cta,
      themeTag: "Registro Chiaro #FAFAF8 · Servizio Pubblico",
    },
    {
      key: "verify" as const,
      href: `/verify?scenario=${encodeURIComponent(defaultScenario)}`,
      tag: "Superficie 3 · Verifica Formale",
      title: "Verifica e Idempotenza",
      description:
        "Audit crittografico SHA-256, prova di replay bit-for-bit, metriche oggettive e limiti operativi dichiarati.",
      cta: "Apri verifica",
      themeTag: "Verifica Idempotenza · RFC 9457",
    },
  ];

  return (
    <AppShell theme="light" scenarioId={defaultScenario} health="live">
      <div className="mx-auto max-w-5xl space-y-8 py-4">
        {/* Header Hero */}
        <header className="space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <span className="rounded-[4px] bg-[#D06A32]/15 px-2 py-0.5 text-[11px] font-bold uppercase tracking-wider text-[#D06A32]">
              Architettura Multi-Agente Resiliente
            </span>
            <span className="text-[11px] font-medium text-[var(--text-muted)]">
              {d.home.scenarioActive}:{" "}
              <code className="rounded-[4px] border border-[var(--border)] bg-[var(--surface)] px-1.5 py-0.2 font-mono text-[12px] text-[var(--text)]">
                {defaultScenario}
              </code>
            </span>
          </div>

          <h1 className="text-[28px] sm:text-[36px] font-semibold tracking-tight text-[var(--text)]">
            {d.home.heading}
          </h1>
          <p className="max-w-3xl text-[15px] sm:text-[16px] text-[var(--text-muted)] leading-relaxed">
            {d.home.subheading}
          </p>

          {/* Scenario Quick Selector Pills */}
          <div className="flex flex-wrap items-center gap-2 pt-1">
            <span className="text-[11px] font-medium uppercase tracking-wider text-[var(--text-muted)]">
              Scenari Disponibili:
            </span>
            {availableScenarios.map((sId) => (
              <Link
                key={sId}
                href={`/operator?scenario=${encodeURIComponent(sId)}`}
                className="group inline-flex items-center gap-1.5 rounded-[6px] border border-[var(--border)] bg-[var(--surface)] px-2.5 py-1 text-[12px] font-medium text-[var(--text)] hover:border-[var(--accent)] transition-colors"
              >
                <code className="font-mono text-[11px] text-[var(--accent)]">{sId}</code>
                <span className="text-[var(--text-muted)] group-hover:text-[var(--text)] text-[11px]">
                  · {SCENARIO_LABELS[sId] ?? sId}
                </span>
              </Link>
            ))}
          </div>
        </header>

        {/* 4 Surface Cards Grid */}
        <section aria-label="Superfici di Accesso" className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {cards.map((card) => (
            <Link
              key={card.key}
              href={card.href}
              data-testid={`role-card-${card.key}`}
              className="group flex flex-col justify-between rounded-[10px] border border-[var(--border)] bg-[var(--surface)] p-4 sm:p-5 shadow-xs hover:border-[var(--accent)] hover:shadow-md transition-all duration-120 space-y-4"
            >
              <div className="space-y-2.5">
                <div className="flex items-center justify-between gap-1 text-[10px] font-medium uppercase tracking-wider text-[var(--text-muted)]">
                  <span>{card.tag}</span>
                </div>
                <h2 className="text-[18px] font-semibold text-[var(--text)] group-hover:text-[var(--accent)] transition-colors duration-120">
                  {card.title}
                </h2>
                <p className="text-[13px] text-[var(--text-muted)] leading-relaxed">{card.description}</p>
              </div>

              <div className="pt-2 border-t border-[var(--border)] flex items-center justify-between">
                <span className="font-mono text-[10px] text-[var(--text-muted)]">{card.themeTag}</span>
                <span className="inline-flex items-center gap-1 text-[13px] font-medium text-[var(--accent)] group-hover:translate-x-0.5 transition-transform">
                  <span>{card.cta}</span>
                  <svg width="12" height="12" viewBox="0 0 14 14" aria-hidden="true">
                    <path
                      d="M3 7h8m0 0L7.5 3.5M11 7l-3.5 3.5"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="1.5"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                </span>
              </div>
            </Link>
          ))}
        </section>

        {/* Key System Invariants Telemetry Strip */}
        <section aria-label="Garanzie di Sistema" className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-center">
          <div className="rounded-[8px] border border-[var(--border)] bg-[var(--surface)] p-3">
            <span className="font-mono text-[16px] font-bold text-[#2D8A4E]">100%</span>
            <p className="text-[11px] font-semibold text-[var(--text)]">Deterministico</p>
            <p className="text-[10px] text-[var(--text-muted)]">Zero allucinazioni LLM</p>
          </div>

          <div className="rounded-[8px] border border-[var(--border)] bg-[var(--surface)] p-3">
            <span className="font-mono text-[16px] font-bold text-[#4FB3D9]">SHA-256</span>
            <p className="text-[11px] font-semibold text-[var(--text)]">Immutabile</p>
            <p className="text-[10px] text-[var(--text-muted)]">Audit trail verificabile</p>
          </div>

          <div className="rounded-[8px] border border-[var(--border)] bg-[var(--surface)] p-3">
            <span className="font-mono text-[16px] font-bold text-[#D06A32]">2 Registri</span>
            <p className="text-[11px] font-semibold text-[var(--text)]">Design System</p>
            <p className="text-[10px] text-[var(--text-muted)]">Dark regia vs Light tascabile</p>
          </div>

          <div className="rounded-[8px] border border-[var(--border)] bg-[var(--surface)] p-3">
            <span className="font-mono text-[16px] font-bold text-[#9B51E0]">3 Target</span>
            <p className="text-[11px] font-semibold text-[var(--text)]">Isolamento Piani</p>
            <p className="text-[10px] text-[var(--text-muted)]">Scarto ordini verificabile</p>
          </div>
        </section>

        {/* Architecture & Flow Topology Visual Card */}
        <section
          aria-label="Topologia del Sistema"
          className="rounded-[10px] border border-[var(--border)] bg-[var(--surface)] p-5 space-y-4"
        >
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <span className="text-[10px] font-bold uppercase tracking-wider text-[#D06A32]">
                Pipeline di Decisione Determinista
              </span>
              <h3 className="text-[16px] font-semibold text-[var(--text)]">
                Flusso Operativo da Sensori a Decisione Immutabile
              </h3>
            </div>
            <span className="font-mono text-[11px] text-[var(--text-muted)]">
              Contratto v1.0.0 · Hash SHA-256
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-5 gap-2.5 text-center text-[12px]">
            <div className="rounded-[6px] border border-[var(--border)] bg-[var(--bg)] p-3 space-y-1 relative">
              <span className="font-mono text-[10px] text-[#2D8A4E] font-bold">1. FONTI DATI</span>
              <p className="font-semibold text-[var(--text)]">Sensori & Scraper</p>
              <p className="text-[11px] text-[var(--text-muted)]">Sensori IR, ANM RSS hash, OpenMeteo</p>
            </div>

            <div className="rounded-[6px] border border-[var(--border)] bg-[var(--bg)] p-3 space-y-1 relative">
              <span className="font-mono text-[10px] text-[#4FB3D9] font-bold">2. SUPERVISORI L2</span>
              <p className="font-semibold text-[var(--text)]">Blackboard</p>
              <p className="text-[11px] text-[var(--text-muted)]">Mobilità, Affollamento, Contesto</p>
            </div>

            <div className="rounded-[6px] border border-[var(--border)] bg-[var(--bg)] p-3 space-y-1 relative">
              <span className="font-mono text-[10px] text-[#D06A32] font-bold">3. NEGOZIAZIONE</span>
              <p className="font-semibold text-[var(--text)]">Ciclo Circolare</p>
              <p className="text-[11px] text-[var(--text-muted)]">Mobilità ⇄ Imprevisti (max 3 turni)</p>
            </div>

            <div className="rounded-[6px] border border-[var(--border)] bg-[var(--bg)] p-3 space-y-1 relative">
              <span className="font-mono text-[10px] text-[#9B51E0] font-bold">4. ENGINE REGOLE</span>
              <p className="font-semibold text-[var(--text)]">Zero Allucinazioni</p>
              <p className="text-[11px] text-[var(--text-muted)]">Regole R1-R4, priorità deterministiche</p>
            </div>

            <div className="rounded-[6px] border border-[var(--border)] bg-[var(--bg)] p-3 space-y-1 relative">
              <span className="font-mono text-[10px] text-[#D06A32] font-bold">5. CONTRATTI</span>
              <p className="font-semibold text-[var(--text)]">Hash Immutabile</p>
              <p className="text-[11px] text-[var(--text-muted)]">Piani target con scarto verificabile</p>
            </div>
          </div>
        </section>

        {/* Embedded Live Route Request Assistant */}
        <section aria-label="Assistente di Viaggio" className="space-y-3">
          <RouteRequestAssistant theme="light" locale="it" />
        </section>
      </div>
    </AppShell>
  );
}
