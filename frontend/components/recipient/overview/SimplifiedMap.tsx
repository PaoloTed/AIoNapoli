/**
 * @purpose Mappa recipient reale e semplificata, senza layer tecnici
 * @contracts Finding
 * @tokens recipient
 * @verified 2026-11-15
 */

"use client";

import { useMemo, useState } from "react";
import { recipientTokens as t } from "@/styles/design-tokens-recipient";
import { NAPLES_ZONES } from "@/lib/scenarios";
import { SlippyMap } from "@/components/map/SlippyMap";
import type { Finding, Severity } from "@/lib/types/contracts";

const MAP_CENTER = { lat: 40.84, lng: 14.2 };
const MAP_BOUNDS = { minLon: 14.1, maxLon: 14.4, minLat: 40.75, maxLat: 40.95 };

const SHORT_LABEL: Record<string, string> = {
  Z_BAGNOLI: "Bagnoli",
  Z_FUORIGROTTA: "Fuorigrotta",
  Z_MERGELLINA: "Mergellina",
  Z_MUNICIPIO: "Municipio",
  Z_CENTRO: "Centro",
  Z_GARIBALDI: "Garibaldi",
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
      const [lng, lat] = zone.center;
      const severity = severityByZone.get(zone.zone_id);
      return {
        zoneId: zone.zone_id,
        label: zone.label,
        shortLabel: SHORT_LABEL[zone.zone_id] ?? zone.label,
        lat,
        lng,
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
        height: "420px",
        background: "#E2E8F0",
        border: `1px solid ${t.color.border.subtle}`,
        borderRadius: t.radius.lg,
        overflow: "hidden",
        boxShadow: t.shadow.soft,
      }}
      aria-label="Mappa semplificata di Napoli"
    >
      <SlippyMap
        center={MAP_CENTER}
        zoom={12}
        minZoom={11}
        maxZoom={15}
        theme="light"
        bounds={MAP_BOUNDS}
        controls={false}
        ariaLabel="Mappa reale di Napoli per cittadino e turista"
      >
        {(project) =>
          zones.map((zone) => {
            const { x, y } = project(zone.lat, zone.lng);
            return (
              <button
                key={zone.zoneId}
                type="button"
                onClick={() => setSelected(zone.zoneId)}
                aria-label={`${zone.label}: ${zone.tone.label}`}
                style={{
                  position: "absolute",
                  left: `${x}px`,
                  top: `${y}px`,
                  transform: "translate(-50%, -50%)",
                  display: "grid",
                  justifyItems: "center",
                  gap: "3px",
                  background: "transparent",
                  border: "none",
                  padding: 0,
                  cursor: "pointer",
                  pointerEvents: "auto",
                }}
              >
                <span
                  aria-hidden="true"
                  style={{
                    width: "22px",
                    height: "22px",
                    borderRadius: "50%",
                    background: zone.tone.color,
                    border: "3px solid #FFFFFF",
                    boxShadow: "0 2px 8px rgba(15,23,42,0.28)",
                  }}
                />
                <span
                  style={{
                    fontSize: "11px",
                    fontWeight: t.font.weight.semibold,
                    color: t.color.text.primary,
                    background: "rgba(255,255,255,0.94)",
                    border: `1px solid ${t.color.border.subtle}`,
                    borderRadius: t.radius.pill,
                    padding: "1px 7px",
                    whiteSpace: "nowrap",
                    boxShadow: "0 1px 4px rgba(15,23,42,0.12)",
                    pointerEvents: "none",
                  }}
                >
                  {zone.shortLabel}
                </span>
              </button>
            );
          })
        }
      </SlippyMap>

      <div
        style={{
          position: "absolute",
          left: t.space[3],
          bottom: t.space[3],
          display: "flex",
          gap: t.space[3],
          padding: `${t.space[1]} ${t.space[3]}`,
          fontSize: t.font.size.xs,
          color: t.color.text.secondary,
          background: "rgba(255,255,255,0.92)",
          border: `1px solid ${t.color.border.subtle}`,
          borderRadius: t.radius.pill,
          flexWrap: "wrap",
          pointerEvents: "none",
        }}
      >
        <span style={{ display: "inline-flex", alignItems: "center", gap: "5px" }}>
          <span style={{ width: 8, height: 8, borderRadius: "50%", background: t.color.severity.low }} /> Mobilità fluida
        </span>
        <span style={{ display: "inline-flex", alignItems: "center", gap: "5px" }}>
          <span style={{ width: 8, height: 8, borderRadius: "50%", background: t.color.severity.medium }} /> Rallentamenti
        </span>
        <span style={{ display: "inline-flex", alignItems: "center", gap: "5px" }}>
          <span style={{ width: 8, height: 8, borderRadius: "50%", background: t.color.severity.critical }} /> Blocchi
        </span>
      </div>

      {selectedZone ? (
        <div
          role="status"
          style={{
            position: "absolute",
            left: t.space[3],
            top: t.space[3],
            zIndex: 5,
            background: t.color.bg.elevated,
            border: `1px solid ${t.color.border.subtle}`,
            borderRadius: t.radius.md,
            padding: t.space[3],
            boxShadow: t.shadow.elevated,
            maxWidth: "280px",
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
