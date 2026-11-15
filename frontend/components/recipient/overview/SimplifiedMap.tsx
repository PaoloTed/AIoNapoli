/**
 * @purpose Mappa recipient semplificata senza layer tecnici
 * @contracts Finding
 * @tokens recipient
 * @verified 2026-11-15
 */

"use client";

import { useMemo, useState } from "react";
import { recipientTokens as t } from "@/styles/design-tokens-recipient";
import { NAPLES_ZONES } from "@/lib/scenarios";
import type { Finding, Severity } from "@/lib/types/contracts";

const WIDTH = 700;
const HEIGHT = 380;
const BBOX = { minLon: 14.1, maxLon: 14.4, minLat: 40.75, maxLat: 40.95 };

function project(lon: number, lat: number): [number, number] {
  return [
    ((lon - BBOX.minLon) / (BBOX.maxLon - BBOX.minLon)) * WIDTH,
    HEIGHT - ((lat - BBOX.minLat) / (BBOX.maxLat - BBOX.minLat)) * HEIGHT,
  ];
}

const SHORT_LABEL: Record<string, string> = {
  Z_BAGNOLI: "Bagnoli",
  Z_FUORIGROTTA: "Fuorigrotta",
  Z_MERGELLINA: "Mergellina",
  Z_MUNICIPIO: "Municipio",
  Z_CENTRO: "Centro",
  Z_GARIBALDI: "Garibaldi",
};

const LABEL_OFFSET: Record<string, { dx: number; dy: number }> = {
  Z_FUORIGROTTA: { dx: -18, dy: 4 },
  Z_MERGELLINA: { dx: -12, dy: -14 },
  Z_MUNICIPIO: { dx: 24, dy: 30 },
  Z_CENTRO: { dx: 40, dy: -22 },
  Z_GARIBALDI: { dx: 34, dy: 14 },
};

const RANK: Record<Severity, number> = { low: 1, medium: 2, high: 3, critical: 4 };

function zoneTone(severity: Severity | undefined): { color: string; label: string } {
  if (!severity || RANK[severity] <= 1) return { color: t.color.severity.low, label: "Mobilità fluida" };
  if (RANK[severity] === 2) return { color: t.color.severity.medium, label: "Rallentamenti" };
  return { color: t.color.severity.critical, label: "Zona critica" };
}

export function SimplifiedMap({ findings }: { findings: Finding[] }) {
  const [selected, setSelected] = useState<string | null>(null);

  const zones = useMemo(() => {
    const severityByZone = new Map<string, Severity>();
    const notesByZone = new Map<string, string>();
    for (const finding of findings) {
      const zoneId = finding.content.zone_id;
      if (!zoneId) continue;
      const current = severityByZone.get(zoneId);
      if (!current || RANK[finding.severity] > RANK[current]) {
        severityByZone.set(zoneId, finding.severity);
      }
      if (finding.content.note && !notesByZone.has(zoneId)) {
        notesByZone.set(zoneId, finding.content.note);
      }
    }
    return Object.values(NAPLES_ZONES).map((zone) => {
      const [x, y] = project(zone.center[0], zone.center[1]);
      const severity = severityByZone.get(zone.zone_id);
      return {
        zoneId: zone.zone_id,
        label: zone.label,
        x,
        y,
        tone: zoneTone(severity),
        note: notesByZone.get(zone.zone_id),
      };
    });
  }, [findings]);

  const selectedZone = zones.find((zone) => zone.zoneId === selected) ?? null;

  return (
    <section
      style={{
        position: "relative",
        background: "linear-gradient(180deg, #F1F5F9 0%, #E2E8F0 100%)",
        border: `1px solid ${t.color.border.subtle}`,
        borderRadius: t.radius.lg,
        overflow: "hidden",
        boxShadow: t.shadow.soft,
      }}
      aria-label="Mappa semplificata di Napoli"
    >
      <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img" aria-label="Zone della città" style={{ width: "100%", display: "block" }}>
        <path
          d={`M0 ${HEIGHT} C 120 ${HEIGHT - 90}, 220 ${HEIGHT - 30}, 340 ${HEIGHT - 20} L 340 ${HEIGHT} Z`}
          fill="#BAE6FD"
          opacity="0.55"
        />
        {zones.map((zone) => (
          <g
            key={zone.zoneId}
            role="button"
            tabIndex={0}
            aria-label={`${zone.label}: ${zone.tone.label}`}
            onClick={() => setSelected(zone.zoneId)}
            onKeyDown={(event) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                setSelected(zone.zoneId);
              }
            }}
            style={{ cursor: "pointer" }}
          >
            <circle cx={zone.x} cy={zone.y} r="20" fill={`${zone.tone.color}22`} stroke={zone.tone.color} strokeWidth="2" />
            <circle cx={zone.x} cy={zone.y} r="7" fill={zone.tone.color} />
            <text
              x={zone.x + (LABEL_OFFSET[zone.zoneId]?.dx ?? 0)}
              y={zone.y - 28 + (LABEL_OFFSET[zone.zoneId]?.dy ?? 0)}
              textAnchor="middle"
              fontSize="12"
              fontWeight="600"
              fill={t.color.text.primary}
              stroke="#FFFFFF"
              strokeWidth="3"
              paintOrder="stroke"
            >
              {SHORT_LABEL[zone.zoneId] ?? zone.label}
            </text>
          </g>
        ))}
      </svg>

      <footer
        style={{
          display: "flex",
          gap: t.space[4],
          padding: `${t.space[2]} ${t.space[4]}`,
          fontSize: t.font.size.xs,
          color: t.color.text.secondary,
          background: "rgba(255,255,255,0.7)",
          flexWrap: "wrap",
        }}
      >
        <span style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}>
          <span style={{ width: 8, height: 8, borderRadius: "50%", background: t.color.severity.low }} /> Mobilità fluida
        </span>
        <span style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}>
          <span style={{ width: 8, height: 8, borderRadius: "50%", background: t.color.severity.medium }} /> Rallentamenti
        </span>
        <span style={{ display: "inline-flex", alignItems: "center", gap: "6px" }}>
          <span style={{ width: 8, height: 8, borderRadius: "50%", background: t.color.severity.critical }} /> Blocchi
        </span>
      </footer>

      {selectedZone ? (
        <div
          role="status"
          style={{
            position: "absolute",
            left: t.space[4],
            top: t.space[4],
            background: t.color.bg.elevated,
            border: `1px solid ${t.color.border.subtle}`,
            borderRadius: t.radius.md,
            padding: t.space[3],
            boxShadow: t.shadow.elevated,
            maxWidth: "260px",
            display: "grid",
            gap: "4px",
          }}
        >
          <strong style={{ fontSize: t.font.size.sm, color: t.color.text.primary }}>{selectedZone.label}</strong>
          <span style={{ fontSize: t.font.size.xs, color: selectedZone.tone.color, fontWeight: 600 }}>
            {selectedZone.tone.label}
          </span>
          <span style={{ fontSize: t.font.size.xs, color: t.color.text.secondary }}>
            {selectedZone.note ?? "Nessuna segnalazione specifica per questa zona."}
          </span>
          <button
            type="button"
            onClick={() => setSelected(null)}
            style={{
              justifySelf: "start",
              border: "none",
              background: "transparent",
              color: t.color.accent.citizen,
              fontSize: t.font.size.xs,
              cursor: "pointer",
              padding: 0,
            }}
          >
            Chiudi
          </button>
        </div>
      ) : null}
    </section>
  );
}
