/**
 * @purpose Header arioso con logo, switch target, lingua e stato generale
 * @contracts Target
 * @tokens recipient
 * @verified 2026-11-15
 */

"use client";

import { recipientTokens as t } from "@/styles/design-tokens-recipient";
import type { Target } from "@/lib/types/contracts";
import type { Locale, StreamStatus } from "@/lib/state/store";
import { BrandLogo } from "@/components/brand/BrandLogo";
import { TargetSwitch } from "./TargetSwitch";

const STATUS_LABEL: Record<StreamStatus, string> = {
  idle: "Aggiornato",
  connected: "In aggiornamento",
  reconnecting: "Riconnessione",
  disconnected: "Offline",
};

export function RecipientHeader({
  target,
  onTargetChange,
  lang,
  onLangChange,
  status,
  simulated,
}: {
  target: Target;
  onTargetChange: (target: Target) => void;
  lang: Locale;
  onLangChange: (lang: Locale) => void;
  status: StreamStatus;
  simulated: boolean;
}) {
  return (
    <header
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        gap: t.space[4],
        padding: `${t.space[4]} ${t.space[6]}`,
        flexWrap: "wrap",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: t.space[4] }}>
        <BrandLogo variant="full" height={42} priority />
        <span style={{ fontSize: t.font.size.sm, color: t.color.text.secondary, maxWidth: "320px" }}>
          La città che ti parla: mobilità, affollamento e meteo in un unico consiglio.
        </span>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: t.space[3], flexWrap: "wrap" }}>
        {simulated ? (
          <span
            style={{
              fontSize: t.font.size.xs,
              color: t.color.severity.medium,
              border: `1px solid ${t.color.severity.medium}55`,
              background: `${t.color.severity.medium}12`,
              borderRadius: t.radius.pill,
              padding: "4px 10px",
            }}
          >
            dati simulati
          </span>
        ) : null}
        <span style={{ fontSize: t.font.size.xs, color: t.color.text.muted }}>{STATUS_LABEL[status]}</span>
        <TargetSwitch value={target} onChange={onTargetChange} />
        <div
          role="group"
          aria-label="Lingua"
          style={{
            display: "inline-flex",
            border: `1px solid ${t.color.border.subtle}`,
            borderRadius: t.radius.pill,
            overflow: "hidden",
          }}
        >
          {(["it", "en"] as const).map((code) => (
            <button
              key={code}
              type="button"
              aria-pressed={lang === code}
              onClick={() => onLangChange(code)}
              style={{
                border: "none",
                padding: "8px 14px",
                fontSize: t.font.size.xs,
                fontWeight: t.font.weight.semibold,
                cursor: "pointer",
                background: lang === code ? t.color.bg.panel : "transparent",
                color: lang === code ? t.color.text.primary : t.color.text.muted,
              }}
            >
              {code.toUpperCase()}
            </button>
          ))}
        </div>
      </div>
    </header>
  );
}
