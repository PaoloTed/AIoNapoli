"use client";

import { useState } from "react";
import clsx from "clsx";
import {
  congestion,
  density,
  type DecisionResponse,
  type Finding,
  type NarrativeItem,
  type PlanItem,
} from "@/lib/contracts";
import { extractEstimatedTimeFromAction, type Locale } from "@/lib/format";
import { getDict } from "@/lib/i18n";
import { ProvenanceChip, TemplateTextChip } from "./ProvenanceChip";

type ChatPanelProps = {
  target: "tourist" | "citizen";
  findings: Finding[];
  decisionResponse: DecisionResponse;
  locale: Locale;
};

type OrderedTargetEntry = {
  planIndex: number;
  item: PlanItem;
  narrative: NarrativeItem | undefined;
};

function computeZoneStatusLabel(findings: Finding[], locale: Locale): string | undefined {
  const d = getDict(locale);
  const readings: number[] = [];
  for (const f of findings) {
    const den = density(f);
    if (den !== undefined) readings.push(den);
    const cong = congestion(f);
    if (cong !== undefined) readings.push(cong);
  }
  if (readings.length === 0) return undefined;
  const maxVal = Math.max(...readings);
  if (maxVal > 0.85) return d.citizen.zoneVeryCrowded;
  if (maxVal >= 0.7) return d.citizen.zoneElevated;
  return d.citizen.zoneNormal;
}

function extractTransitBadges(actionText: string): { label: string; mode: string }[] {
  const badges: { label: string; mode: string }[] = [];
  const lower = actionText.toLowerCase();
  if (lower.includes("r2") || lower.includes("linea r2")) {
    badges.push({ label: "Bus R2", mode: "bus" });
  }
  if (lower.includes("151") || lower.includes("linea 151")) {
    badges.push({ label: "Bus 151", mode: "bus" });
  }
  if (lower.includes("linea 1") || lower.includes("metro 1")) {
    badges.push({ label: "Metro L1", mode: "metro" });
  }
  if (lower.includes("linea 2") || lower.includes("metro 2")) {
    badges.push({ label: "Metro L2", mode: "metro" });
  }
  if (lower.includes("cumana")) {
    badges.push({ label: "Treno Cumana", mode: "rail" });
  }
  if (lower.includes("funicolare")) {
    badges.push({ label: "Funicolare", mode: "funicular" });
  }
  return badges;
}

export function ChatPanel({ target, findings, decisionResponse, locale }: ChatPanelProps) {
  const [isSpeaking, setIsSpeaking] = useState(false);
  const effectiveLocale: Locale = target === "citizen" ? "it" : locale;
  const d = getDict(effectiveLocale);
  const { decision, relevance, narrative } = decisionResponse;

  const targetRelevance = relevance.targets[target];
  const narrativeMap = new Map(narrative.items.map((n) => [n.plan_index, n]));

  // Order strictly by relevance.targets[target].order (FE-REQ-22)
  const orderedIndices =
    targetRelevance.order.length > 0
      ? targetRelevance.order.filter((idx) => decision.plan[idx]?.target === target)
      : decision.plan
          .map((item, idx) => (item.target === target ? idx : -1))
          .filter((idx) => idx >= 0);

  const orderedEntries: OrderedTargetEntry[] = [];
  for (const idx of orderedIndices) {
    const item = decision.plan[idx];
    if (item && item.target === target) {
      orderedEntries.push({
        planIndex: idx,
        item,
        narrative: narrativeMap.get(idx),
      });
    }
  }

  // Tourist screen displays max 3 actions (FE-REQ-25)
  const visibleEntries = target === "tourist" ? orderedEntries.slice(0, 3) : orderedEntries;
  const remainingCount =
    target === "tourist" && orderedEntries.length > 3 ? orderedEntries.length - 3 : 0;

  const hasSimulatedFinding = findings.some((f) => f.is_simulated);
  const zoneStatusLabel =
    target === "citizen" ? computeZoneStatusLabel(findings, effectiveLocale) : undefined;

  const primaryEntry = visibleEntries[0];
  const secondaryEntries = visibleEntries.slice(1);

  const resolveDisplayText = (entry: OrderedTargetEntry): { text: string; textLang: Locale } => {
    if (entry.narrative) {
      if (effectiveLocale === "en" && entry.narrative.texts.en) {
        return { text: entry.narrative.texts.en, textLang: "en" };
      }
      return { text: entry.narrative.texts.it, textLang: "it" };
    }
    return { text: entry.item.action, textLang: "it" };
  };

  const handleSpeak = (textToSpeak: string, lang: Locale) => {
    if (typeof window === "undefined" || !("speechSynthesis" in window)) return;
    if (isSpeaking) {
      window.speechSynthesis.cancel();
      setIsSpeaking(false);
      return;
    }
    window.speechSynthesis.cancel();
    const utterance = new SpeechSynthesisUtterance(textToSpeak);
    utterance.lang = lang === "en" ? "en-US" : "it-IT";
    utterance.rate = 0.95;
    utterance.onend = () => setIsSpeaking(false);
    utterance.onerror = () => setIsSpeaking(false);
    setIsSpeaking(true);
    window.speechSynthesis.speak(utterance);
  };

  return (
    <section
      className="space-y-4"
      data-testid={`chat-panel-${target}`}
      aria-label={target === "tourist" ? d.tourist.title : d.citizen.title}
    >
      {/* Citizen qualitative zone status (SCREENS.md §5: never raw numbers) */}
      {target === "citizen" && zoneStatusLabel && (
        <div
          className="rounded-[10px] border border-[var(--border)] bg-[var(--surface)] px-4 py-3 shadow-[0_1px_3px_rgba(20,26,32,0.08)]"
          data-testid="citizen-zone-status"
        >
          <p className="text-[11px] font-medium uppercase tracking-wider text-[var(--text-muted)]">
            {d.citizen.zoneStateTitle}
          </p>
          <p className="mt-1 text-[15px] font-medium text-[var(--text)]">{zoneStatusLabel}</p>
        </div>
      )}

      {/* Primary assistant bubble */}
      {!primaryEntry ? (
        <div className="rounded-[10px] border border-[var(--border)] bg-[var(--surface)] p-4 text-[15px] text-[var(--text-muted)]">
          {target === "tourist" ? d.tourist.noActions : d.citizen.noActions}
        </div>
      ) : (
        (() => {
          const { text, textLang } = resolveDisplayText(primaryEntry);
          const estimatedTime = extractEstimatedTimeFromAction(
            `${text} ${primaryEntry.item.action}`,
          );
          const transitBadges = extractTransitBadges(text);

          return (
            <article
              className={clsx(
                "rounded-[10px] bg-[var(--surface)] p-5 space-y-3 shadow-[0_1px_3px_rgba(20,26,32,0.08)]",
                hasSimulatedFinding
                  ? "border border-dashed border-[var(--border)]"
                  : "border border-solid border-[var(--border)]",
              )}
              data-testid="primary-recommendation"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="text-[11px] font-medium uppercase tracking-wider text-[var(--accent)]">
                  {target === "tourist"
                    ? d.tourist.primaryRecommendation
                    : d.citizen.primaryRecommendation}
                </span>

                <div className="flex flex-wrap items-center gap-2">
                  <button
                    type="button"
                    onClick={() => handleSpeak(text, textLang)}
                    className="inline-flex items-center gap-1 rounded-[4px] border border-[var(--border)] bg-[var(--bg)] px-2 py-0.5 text-[11px] text-[var(--text-muted)] hover:text-[var(--text)] transition-colors cursor-pointer"
                    title={isSpeaking ? "Ferma lettura vocale" : "Ascolta indicazione vocale"}
                    aria-label={isSpeaking ? "Ferma lettura vocale" : "Ascolta indicazione vocale"}
                  >
                    <span>{isSpeaking ? "⏹ Ferma" : "🔊 Ascolta"}</span>
                  </button>
                  {hasSimulatedFinding && (
                    <ProvenanceChip variant="simulated" locale={effectiveLocale} />
                  )}
                  {narrative.mode !== "live" && <TemplateTextChip locale={effectiveLocale} />}
                </div>
              </div>

              <p
                lang={textLang}
                className="text-[20px] font-semibold leading-snug text-[var(--text)]"
                data-testid="primary-message-text"
              >
                {text}
              </p>

              {/* Transit modal badges extracted from recommendation */}
              {transitBadges.length > 0 && (
                <div className="flex flex-wrap items-center gap-1.5 pt-1">
                  <span className="text-[10px] font-medium uppercase tracking-wider text-[var(--text-muted)]">
                    {effectiveLocale === "en" ? "Transit modes:" : "Mezzi:"}
                  </span>
                  {transitBadges.map((b) => (
                    <span
                      key={b.label}
                      className="rounded-[4px] border border-[var(--border)] bg-[var(--bg)] px-2 py-0.5 font-mono text-[11px] font-semibold text-[var(--text)]"
                    >
                      {b.label}
                    </span>
                  ))}
                </div>
              )}

              {/* Show estimated time ONLY if present in action text (SCREENS.md §4) */}
              {estimatedTime && (
                <p className="text-[13px] text-[var(--text-muted)]">
                  <span className="text-[11px] font-medium uppercase tracking-wider">
                    {d.tourist.estimatedTime}:{" "}
                  </span>
                  <span className="font-medium text-[var(--text)]">{estimatedTime}</span>
                </p>
              )}

              {hasSimulatedFinding && (
                <p className="text-[13px] text-[var(--text-muted)]">
                  {target === "tourist" ? d.tourist.simulatedNotice : d.citizen.simulatedNotice}
                </p>
              )}
            </article>
          );
        })()
      )}

      {/* Alternatives / remaining items */}
      {secondaryEntries.length > 0 && (
        <div className="space-y-2.5" data-testid="alternatives-list">
          <h2 className="text-[11px] font-medium uppercase tracking-wider text-[var(--text-muted)]">
            {target === "tourist" ? d.tourist.alternativesTitle : d.citizen.moreServicesTitle}
          </h2>

          <ul className="space-y-2.5">
            {secondaryEntries.map((entry) => {
              const { text, textLang } = resolveDisplayText(entry);
              const estimatedTime = extractEstimatedTimeFromAction(`${text} ${entry.item.action}`);
              const transitBadges = extractTransitBadges(text);

              return (
                <li
                  key={entry.planIndex}
                  className={clsx(
                    "rounded-[10px] bg-[var(--surface)] p-4 space-y-2 shadow-[0_1px_3px_rgba(20,26,32,0.08)]",
                    hasSimulatedFinding
                      ? "border border-dashed border-[var(--border)]"
                      : "border border-solid border-[var(--border)]",
                  )}
                  data-testid="alternative-item"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="rounded-[6px] border border-[var(--border)] px-2 py-0.5 font-mono text-[12px] text-[var(--text-muted)]">
                      #{entry.item.priority}
                    </span>
                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => handleSpeak(text, textLang)}
                        className="rounded-[4px] border border-[var(--border)] bg-[var(--bg)] px-1.5 py-0.2 text-[10px] text-[var(--text-muted)] hover:text-[var(--text)] transition-colors cursor-pointer"
                        title="Ascolta indicazione vocale"
                      >
                        🔊
                      </button>
                      {estimatedTime && (
                        <span className="text-[13px] font-medium text-[var(--accent)]">
                          {estimatedTime}
                        </span>
                      )}
                    </div>
                  </div>
                  <p lang={textLang} className="text-[15px] text-[var(--text)]">
                    {text}
                  </p>
                  {transitBadges.length > 0 && (
                    <div className="flex flex-wrap items-center gap-1 pt-0.5">
                      {transitBadges.map((b) => (
                        <span
                          key={b.label}
                          className="rounded-[3px] border border-[var(--border)] bg-[var(--bg)] px-1.5 py-0.2 font-mono text-[10px] text-[var(--text-muted)]"
                        >
                          {b.label}
                        </span>
                      ))}
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
        </div>
      )}

      {/* Non-expandable overflow line for tourist when > 3 items (FE-REQ-25) */}
      {remainingCount > 0 && (
        <p
          className="rounded-[6px] border border-[var(--border)] bg-[var(--surface)] px-3 py-2 text-[13px] text-[var(--text-muted)]"
          data-testid="more-actions-notice"
        >
          {d.tourist.moreActions(remainingCount)}
        </p>
      )}
    </section>
  );
}
