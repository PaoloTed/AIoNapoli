"use client";

import { useEffect, useState, type ReactNode } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import clsx from "clsx";
import { EXPECTED_CONTRACT_VERSION } from "@/lib/contracts";
import { formatRomeDateTime, type Locale } from "@/lib/format";
import { getDict } from "@/lib/i18n";
import { getConfiguredScenarios, getDefaultScenarioId } from "@/lib/scenarios";
import { isSoundEnabled, playSound, setSoundEnabled } from "@/lib/sound";
import { SystemStatusBar, type SystemHealth } from "./SystemStatusBar";

type AppShellProps = {
  theme: "dark" | "light";
  scenarioId?: string;
  scenarioTitle?: string | undefined;
  health?: SystemHealth;
  contractVersion?: string;
  contractMismatch?: boolean;
  locale?: Locale;
  onLocaleChange?: (next: Locale) => void;
  showLanguageSwitcher?: boolean;
  children: ReactNode;
};

export function AppShell({
  theme,
  scenarioId,
  scenarioTitle,
  health = "live",
  contractVersion = EXPECTED_CONTRACT_VERSION,
  contractMismatch = false,
  locale = "it",
  onLocaleChange,
  showLanguageSwitcher = false,
  children,
}: AppShellProps) {
  const d = getDict(locale);
  const pathname = usePathname();
  const router = useRouter();
  const scenarios = getConfiguredScenarios();
  const activeScenario = scenarioId ?? getDefaultScenarioId();
  const [clockText, setClockText] = useState<string>("");
  const [soundOn, setSoundOn] = useState<boolean>(true);

  useEffect(() => {
    setSoundOn(isSoundEnabled());
  }, []);

  useEffect(() => {
    const updateClock = () => {
      setClockText(formatRomeDateTime(new Date().toISOString(), locale));
    };
    updateClock();
    const timer = window.setInterval(updateClock, 1000);
    return () => window.clearInterval(timer);
  }, [locale]);

  const handleScenarioSelect = (nextScenario: string) => {
    if (pathname === "/operator" || pathname === "/tourist" || pathname === "/citizen") {
      router.push(`${pathname}?scenario=${encodeURIComponent(nextScenario)}`);
    } else {
      router.push(`/operator?scenario=${encodeURIComponent(nextScenario)}`);
    }
  };

  const navHref = (route: string) =>
    scenarioId && scenarioId !== getDefaultScenarioId()
      ? `${route}?scenario=${encodeURIComponent(scenarioId)}`
      : route;

  return (
    <div
      data-theme={theme}
      className={clsx(
        "min-h-screen flex flex-col bg-[var(--bg)] text-[var(--text)] transition-colors duration-120",
        theme === "dark" ? "theme-operator" : "theme-pocket",
      )}
    >
      <header className="border-b border-[var(--border)] bg-[var(--surface)]">
        <div className="mx-auto flex max-w-[1440px] flex-col md:flex-row md:items-center md:justify-between gap-3 px-4 py-3 sm:px-6">
          {/* Brand & Scenario Identity (Top row on mobile, left block on desktop) */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 min-w-0">
            <div className="space-y-0.5 min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <Link
                  href="/"
                  className="text-[15px] font-semibold tracking-tight text-[var(--text)] hover:text-[var(--accent)] transition-colors duration-120"
                >
                  {d.appName}
                </Link>
                <code
                  className="rounded-[6px] border border-[var(--border)] bg-[var(--bg)] px-2 py-0.5 font-mono text-[11px] text-[var(--text-muted)]"
                  data-testid="shell-scenario-id"
                >
                  {activeScenario}
                </code>
                {clockText && (
                  <time
                    className="font-mono text-[11px] text-[var(--text-muted)]"
                    title={d.shell.timeLabel}
                  >
                    {clockText}
                  </time>
                )}
              </div>
              {scenarioTitle && (
                <p className="truncate text-[12px] text-[var(--text-muted)]">{scenarioTitle}</p>
              )}
            </div>

            {/* Mobile Status Bar (visible only < md) */}
            <div className="flex md:hidden items-center gap-2 pt-1">
              <SystemStatusBar
                health={health}
                contractVersion={contractVersion}
                contractMismatch={contractMismatch}
                locale={locale}
              />
            </div>
          </div>

          {/* Navigation across the 4 views (Full-width grid on mobile, inline on desktop) */}
          <nav
            aria-label="Views"
            className="grid grid-cols-4 md:flex items-center gap-1 w-full md:w-auto"
          >
            {(
              [
                { href: "/operator", label: d.nav.operator },
                { href: "/tourist", label: d.nav.tourist },
                { href: "/citizen", label: d.nav.citizen },
                { href: "/verify", label: d.nav.verify },
              ] as const
            ).map((item) => {
              const active = pathname === item.href;
              return (
                <Link
                  key={item.href}
                  href={navHref(item.href)}
                  aria-current={active ? "page" : undefined}
                  className={clsx(
                    "rounded-[6px] border px-2 sm:px-3 py-1.5 text-center text-[12px] sm:text-[13px] font-medium transition-colors duration-120 truncate",
                    active
                      ? "border-[var(--accent)] bg-[var(--accent-soft)] text-[var(--text)]"
                      : "border-transparent text-[var(--text-muted)] hover:border-[var(--border)] hover:text-[var(--text)]",
                  )}
                >
                  {item.label}
                </Link>
              );
            })}
          </nav>

          {/* Controls: Scenario selector, optional IT/EN toggle, Desktop SystemStatusBar */}
          <div className="flex items-center justify-between md:justify-end gap-3 pt-2 md:pt-0 border-t md:border-t-0 border-[var(--border)]">
            <label className="inline-flex items-center gap-1.5 text-[11px] font-medium uppercase tracking-wider text-[var(--text-muted)]">
              <span>{d.shell.scenarioLabel}</span>
              <select
                aria-label={d.shell.scenarioLabel}
                value={scenarios.includes(activeScenario) ? activeScenario : ""}
                onChange={(e) => {
                  if (e.target.value) handleScenarioSelect(e.target.value);
                }}
                className="rounded-[6px] border border-[var(--border)] bg-[var(--bg)] px-2 py-1 font-mono text-[11px] normal-case tracking-normal text-[var(--text)]"
              >
                {!scenarios.includes(activeScenario) && <option value="">{activeScenario}</option>}
                {scenarios.map((id) => (
                  <option key={id} value={id}>
                    {id}
                  </option>
                ))}
              </select>
            </label>

            <div className="flex items-center gap-2">
              {showLanguageSwitcher && onLocaleChange && (
                <div
                  className="inline-flex rounded-[6px] border border-[var(--border)] bg-[var(--bg)] p-0.5"
                  role="group"
                  aria-label={d.shell.languageLabel}
                >
                  {(["it", "en"] as const).map((code) => (
                    <button
                      key={code}
                      type="button"
                      onClick={() => onLocaleChange(code)}
                      aria-pressed={locale === code}
                      data-testid={`lang-${code}`}
                      className={clsx(
                        "rounded-[4px] px-2 py-0.5 text-[11px] font-medium uppercase tracking-wider transition-colors duration-120 cursor-pointer",
                        locale === code
                          ? "bg-[var(--accent-soft)] text-[var(--accent)]"
                          : "text-[var(--text-muted)] hover:text-[var(--text)]",
                      )}
                    >
                      {code}
                    </button>
                  ))}
                </div>
              )}

              <button
                type="button"
                onClick={() => {
                  const next = !soundOn;
                  setSoundOn(next);
                  setSoundEnabled(next);
                  if (next) playSound("click");
                }}
                className="rounded-[6px] border border-[var(--border)] bg-[var(--bg)] px-2 py-1 font-mono text-[11px] text-[var(--text-muted)] hover:text-[var(--text)] transition-colors cursor-pointer"
                title={soundOn ? "Effetti audio attivi (clicca per mutare)" : "Effetti audio mutati (clicca per attivare)"}
                aria-label="Toggle effetti audio"
                data-testid="sound-toggle-btn"
              >
                {soundOn ? "🔊 FX" : "🔇 FX"}
              </button>

              {/* Desktop Status Bar (hidden < md) */}
              <div className="hidden md:flex items-center gap-2">
                <SystemStatusBar
                  health={health}
                  contractVersion={contractVersion}
                  contractMismatch={contractMismatch}
                  locale={locale}
                />
              </div>
            </div>
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-[1440px] flex-1 px-4 py-6 sm:px-6">{children}</main>
    </div>
  );
}
