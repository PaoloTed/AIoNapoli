/**
 * @purpose Marker di zona aggregati per severità e densità
 * @contracts Finding
 * @tokens operator
 * @verified 2026-11-15
 */

"use client";

import { operatorTokens as t } from "@/styles/design-tokens-operator";
import type { Finding } from "@/lib/types/contracts";
import { aggregateByZone, zoneLabel } from "./geo";

export function FindingMarkers({
  findings,
  onMarkerClick,
}: {
  findings: Finding[];
  onMarkerClick: (zoneId: string) => void;
}) {
  return (
    <g>
      {aggregateByZone(findings).map((zone) => {
        const radius = 12 + Math.min(zone.findings.length, 5) * 2.5;
        const color = t.color.severity[zone.maxSeverity];
        const pulsing = zone.density > 0.8;
        return (
          <g
            key={zone.zoneId}
            role="button"
            tabIndex={0}
            aria-label={`Zona ${zoneLabel(zone.zoneId)}, ${zone.findings.length} evidenze, severità ${zone.maxSeverity}`}
            onClick={() => onMarkerClick(zone.zoneId)}
            onKeyDown={(event) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                onMarkerClick(zone.zoneId);
              }
            }}
            style={{ cursor: "pointer" }}
          >
            {pulsing ? (
              <circle
                cx={zone.center[0]}
                cy={zone.center[1]}
                r={radius + 10}
                fill="none"
                stroke={color}
                strokeOpacity={0.5}
                strokeWidth={2}
                style={{ animation: "operator-pulse 1.8s ease-out infinite", transformOrigin: `${zone.center[0]}px ${zone.center[1]}px` }}
              />
            ) : null}
            <circle cx={zone.center[0]} cy={zone.center[1]} r={radius} fill={`${color}26`} stroke={color} strokeWidth={2} />
            <circle cx={zone.center[0]} cy={zone.center[1]} r={4} fill={color} />
            <text
              x={zone.center[0]}
              y={zone.center[1] - radius - 8}
              textAnchor="middle"
              fill={t.color.text.primary}
              fontSize={12}
              fontWeight={600}
            >
              {zoneLabel(zone.zoneId)}
            </text>
            <text
              x={zone.center[0]}
              y={zone.center[1] + radius + 15}
              textAnchor="middle"
              fill={color}
              fontSize={11}
              fontWeight={700}
            >
              {zone.findings.length} · {zone.maxSeverity.toUpperCase()}
            </text>
          </g>
        );
      })}
    </g>
  );
}
