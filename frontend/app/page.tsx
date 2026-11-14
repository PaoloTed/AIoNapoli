import Link from "next/link";
import { AppShell } from "@/components/AppShell";
import { getDict } from "@/lib/i18n";
import { getDefaultScenarioId } from "@/lib/scenarios";

export default function HomePage() {
  const d = getDict("it");
  const defaultScenario = getDefaultScenarioId();

  const cards = [
    {
      key: "operator" as const,
      href: `/operator?scenario=${encodeURIComponent(defaultScenario)}`,
      tag: "Desktop · Sala operativa",
      data: d.home.cards.operator,
    },
    {
      key: "tourist" as const,
      href: `/tourist?scenario=${encodeURIComponent(defaultScenario)}`,
      tag: "Mobile-first · IT / EN",
      data: d.home.cards.tourist,
    },
    {
      key: "citizen" as const,
      href: `/citizen?scenario=${encodeURIComponent(defaultScenario)}`,
      tag: "Mobile-first · Servizio pubblico",
      data: d.home.cards.citizen,
    },
  ];

  return (
    <AppShell theme="light" scenarioId={defaultScenario} health="live">
      <div className="mx-auto max-w-4xl space-y-8 py-4">
        <header className="space-y-2">
          <p className="text-[11px] font-medium uppercase tracking-wider text-[var(--text-muted)]">
            {d.home.scenarioActive}:{" "}
            <code className="font-mono text-[13px] text-[var(--text)]">{defaultScenario}</code>
          </p>
          <h1 className="text-[28px] sm:text-[32px] font-semibold leading-tight text-[var(--text)]">
            {d.home.heading}
          </h1>
          <p className="text-[15px] text-[var(--text-muted)]">{d.home.subheading}</p>
        </header>

        <section aria-label={d.home.heading} className="grid gap-4 md:grid-cols-3">
          {cards.map((card) => (
            <Link
              key={card.key}
              href={card.href}
              data-testid={`role-card-${card.key}`}
              className="group flex flex-col justify-between rounded-[10px] border border-[var(--border)] bg-[var(--surface)] p-5 shadow-[0_1px_3px_rgba(20,26,32,0.08)] hover:border-[var(--accent)] transition-colors duration-120 space-y-4"
            >
              <div className="space-y-2">
                <p className="text-[11px] font-medium uppercase tracking-wider text-[var(--text-muted)]">
                  {card.tag}
                </p>
                <h2 className="text-[20px] font-semibold text-[var(--text)] group-hover:text-[var(--accent)] transition-colors duration-120">
                  {card.data.title}
                </h2>
                <p className="text-[15px] text-[var(--text-muted)]">{card.data.description}</p>
              </div>

              <span className="inline-flex items-center gap-1.5 text-[14px] font-medium text-[var(--accent)]">
                <span>{card.data.cta}</span>
                <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true">
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
            </Link>
          ))}
        </section>
      </div>
    </AppShell>
  );
}
