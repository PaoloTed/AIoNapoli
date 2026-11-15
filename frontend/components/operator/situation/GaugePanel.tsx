/**
 * @purpose Indicatori radiali di densità media, saturazione linee e confidenza
 * @contracts nessuno
 * @tokens operator
 * @verified 2026-11-15
 */

import { operatorTokens as t } from "@/styles/design-tokens-operator";
import { formatPercent } from "@/lib/format";

function Gauge({ value, label, color }: { value: number; label: string; color: string }) {
  const clamped = Math.max(0, Math.min(1, value));
  const radius = 30;
  const circumference = 2 * Math.PI * radius;
  const dash = circumference * clamped;

  return (
    <div style={{ display: "grid", justifyItems: "center", gap: t.space[1] }}>
      <svg width="76" height="76" viewBox="0 0 76 76" role="img" aria-label={`${label}: ${formatPercent(clamped)}`}>
        <circle cx="38" cy="38" r={radius} fill="none" stroke={t.color.bg.panelAlt} strokeWidth="7" />
        <circle
          cx="38"
          cy="38"
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth="7"
          strokeLinecap="round"
          strokeDasharray={`${dash} ${circumference - dash}`}
          transform="rotate(-90 38 38)"
        />
        <text x="38" y="42" textAnchor="middle" fill={t.color.text.primary} fontSize="15" fontWeight="700">
          {formatPercent(clamped)}
        </text>
      </svg>
      <span style={{ fontSize: t.font.size.xs, color: t.color.text.muted, textAlign: "center" }}>{label}</span>
    </div>
  );
}

export function GaugePanel({
  density,
  saturation,
  confidence,
}: {
  density: number;
  saturation: number;
  confidence: number;
}) {
  return (
    <section
      style={{
        background: t.color.bg.panel,
        border: `1px solid ${t.color.border.subtle}`,
        borderRadius: t.radius.md,
        padding: t.space[3],
      }}
      aria-label="Indicatori sintetici"
    >
      <h3 style={{ margin: `0 0 ${t.space[3]}`, fontSize: t.font.size.sm, color: t.color.text.secondary, textTransform: "uppercase", letterSpacing: "0.08em" }}>
        Indicatori sintetici
      </h3>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: t.space[2] }}>
        <Gauge value={density} label="Densità media" color={density >= 0.8 ? t.color.severity.critical : t.color.severity.medium} />
        <Gauge value={saturation} label="Saturazione linee" color={saturation >= 0.8 ? t.color.severity.high : t.color.accent.primary} />
        <Gauge value={confidence} label="Confidenza media" color={t.color.severity.low} />
      </div>
    </section>
  );
}
