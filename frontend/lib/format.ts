import type { Severity } from "./contracts";

export type Locale = "it" | "en";

const ROME_TZ = "Europe/Rome";

export function formatRomeDateTime(iso: string, locale: Locale = "it"): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return iso;
  }
  return new Intl.DateTimeFormat(locale === "en" ? "en-GB" : "it-IT", {
    timeZone: ROME_TZ,
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(date);
}

export function formatRomeTime(iso: string, locale: Locale = "it"): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) {
    return iso;
  }
  return new Intl.DateTimeFormat(locale === "en" ? "en-GB" : "it-IT", {
    timeZone: ROME_TZ,
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(date);
}

export function formatPercent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

export function formatScore(value: number, decimals = 4): string {
  return value.toFixed(decimals);
}

const SEVERITY_LABELS: Record<Locale, Record<Severity, string>> = {
  it: {
    low: "Bassa",
    medium: "Media",
    high: "Alta",
    critical: "Critica",
  },
  en: {
    low: "Low",
    medium: "Medium",
    high: "High",
    critical: "Critical",
  },
};

export function severityText(severity: Severity, locale: Locale = "it"): string {
  return SEVERITY_LABELS[locale][severity];
}

export function formatAgeSeconds(
  observedIso: string,
  referenceIso: string,
  locale: Locale = "it",
): string | undefined {
  const observed = Date.parse(observedIso);
  const reference = Date.parse(referenceIso);
  if (Number.isNaN(observed) || Number.isNaN(reference)) {
    return undefined;
  }
  const diffSec = Math.max(0, Math.round((reference - observed) / 1000));
  if (diffSec < 60) {
    return locale === "en" ? `${diffSec}s ago` : `${diffSec} s fa`;
  }
  const mins = Math.floor(diffSec / 60);
  const secs = diffSec % 60;
  return locale === "en" ? `${mins}m ${secs}s ago` : `${mins} min ${secs} s fa`;
}

export function extractEstimatedTimeFromAction(action: string): string | undefined {
  const match = action.match(/\b(\d+\s*(?:min(?:uti|utes)?|h))\b/i);
  return match ? match[1] : undefined;
}
