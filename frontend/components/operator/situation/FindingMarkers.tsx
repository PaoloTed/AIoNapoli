/**
 * @purpose Marker di zona aggregati, proiettati sulla mappa reale
 * @contracts Finding
 * @tokens operator
 * @verified 2026-11-15
 */

"use client";

import { operatorTokens as t } from "@/styles/design-tokens-operator";
import type { Finding } from "@/lib/types/contracts";
import type { MapProjection } from "@/components/map/SlippyMap";
import { aggregateByZone, zoneLabel } from "./geo";

export function FindingMarkers({
  findings,
  project,
  onMarkerClick,
}: {
  findings: Finding[];
  project: MapProjection;
  onMarkerClick: (zoneId: string) => void;
}) {
  return (
    <>
      {aggregateByZone(findings).map((zone) => {
        const { x, y } = project(zone.center.lat, zone.center.lng);
        const size = 30 + Math.min(zone.findings.length, 5) * 3;
        const color = t.color.severity[zone.maxSeverity];
        const pulsing = zone.density > 0.8;

        return (
          <button
            key={zone.zoneId}
            type="button"
            onClick={() => onMarkerClick(zone.zoneId)}
            aria-label={`Zona ${zoneLabel(zone.zoneId)}, ${zone.findings.length} evidenze, severità ${zone.maxSeverity}`}
            style={{
              position: "absolute",
              left: `${x}px`,
              top: `${y}px`,
              transform: "translate(-50%, -50%)",
              width: `${size}px`,
              height: `${size}px`,
              padding: 0,
              border: `2px solid ${color}`,
              borderRadius: "50%",
              background: `${color}3D`,
              color: t.color.text.primary,
              display: "grid",
              placeItems: "center",
              fontSize: t.font.size.sm,
              fontWeight: t.font.weight.bold,
              cursor: "pointer",
              pointerEvents: "auto",
              boxShadow: `0 0 0 4px ${color}22, 0 2px 8px rgba(0,0,0,0.45)`,
              backdropFilter: "blur(2px)",
            }}
          >
            {pulsing ? (
              <span
                aria-hidden="true"
                style={{
                  position: "absolute",
                  inset: "-10px",
                  borderRadius: "50%",
                  border: `2px solid ${color}`,
                  animation: "operator-pulse 1.8s ease-out infinite",
                }}
              />
            ) : null}
            <span aria-hidden="true">{zone.findings.length}</span>
            <span
              style={{
                position: "absolute",
                top: "calc(100% + 4px)",
                left: "50%",
                transform: "translateX(-50%)",
                fontSize: "10px",
                fontWeight: t.font.weight.semibold,
                color: t.color.text.primary,
                background: "rgba(11,16,22,0.78)",
                border: `1px solid ${t.color.border.subtle}`,
                borderRadius: "4px",
                padding: "1px 6px",
                whiteSpace: "nowrap",
                pointerEvents: "none",
              }}
            >
              {zoneLabel(zone.zoneId)} · {zone.maxSeverity}
            </span>
          </button>
        );
      })}
    </>
  );
}
