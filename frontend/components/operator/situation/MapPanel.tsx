/**
 * @purpose Mappa 2D operativa vincolata al bounding box di Napoli
 * @contracts Finding, VehiclePosition
 * @tokens operator
 * @verified 2026-11-15
 */

"use client";

import { useMemo } from "react";
import { operatorTokens as t } from "@/styles/design-tokens-operator";
import { NAPLES_ZONES } from "@/lib/scenarios";
import type { Finding, VehiclePosition } from "@/lib/types/contracts";
import { DensityLayer } from "./DensityLayer";
import { FindingMarkers } from "./FindingMarkers";
import { VehicleMarkers } from "./VehicleMarkers";
import { MapPopover } from "./MapPopover";
import { MAP_HEIGHT, MAP_WIDTH, NAPLES_BBOX, project, projectPoint, zonePolygonPoints } from "./geo";

const GRID_LON = [14.15, 14.2, 14.25, 14.3, 14.35];
const GRID_LAT = [40.78, 40.82, 40.86, 40.9, 40.94];

export function MapPanel({
  findings,
  vehicles,
  selectedZone,
  onMarkerClick,
  onClosePopover,
}: {
  findings: Finding[];
  vehicles: VehiclePosition[];
  selectedZone: string | null;
  onMarkerClick: (zoneId: string) => void;
  onClosePopover: () => void;
}) {
  const selectedFindings = useMemo(
    () => findings.filter((finding) => finding.content.zone_id === selectedZone),
    [findings, selectedZone],
  );

  return (
    <section
      style={{
        position: "relative",
        background: "linear-gradient(180deg, #0D1522 0%, #0B1016 100%)",
        border: `1px solid ${t.color.border.subtle}`,
        borderRadius: t.radius.md,
        overflow: "hidden",
        height: "100%",
        minHeight: "520px",
      }}
      aria-label="Mappa operativa di Napoli"
    >
      <header
        style={{
          position: "absolute",
          top: t.space[3],
          left: t.space[4],
          right: t.space[4],
          zIndex: 2,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: t.space[2],
          flexWrap: "wrap",
        }}
      >
        <h2 style={{ margin: 0, fontSize: t.font.size.lg, fontWeight: t.font.weight.semibold }}>
          Live City Operations Map
        </h2>
        <span
          style={{
            fontSize: "10px",
            color: t.color.text.muted,
            border: `1px solid ${t.color.border.subtle}`,
            borderRadius: t.radius.pill,
            padding: "1px 8px",
            whiteSpace: "nowrap",
          }}
        >
          bbox Napoli {NAPLES_BBOX.minLat}–{NAPLES_BBOX.maxLat} / {NAPLES_BBOX.minLon}–{NAPLES_BBOX.maxLon}
        </span>
      </header>

      <svg
        viewBox={`0 0 ${MAP_WIDTH} ${MAP_HEIGHT}`}
        role="img"
        aria-label="Mappa 2D con evidenze e flotta"
        style={{ width: "100%", height: "100%", display: "block" }}
      >
        <defs>
          <pattern id="op-grid" width="40" height="40" patternUnits="userSpaceOnUse">
            <path d="M 40 0 L 0 0 0 40" fill="none" stroke="#182335" strokeWidth="1" />
          </pattern>
        </defs>
        <rect width={MAP_WIDTH} height={MAP_HEIGHT} fill="url(#op-grid)" />

        {GRID_LON.map((lon) => {
          const [x] = project([lon, NAPLES_BBOX.minLat]);
          return <line key={`lon-${lon}`} x1={x} y1={0} x2={x} y2={MAP_HEIGHT} stroke="#16202F" strokeWidth={1} />;
        })}
        {GRID_LAT.map((lat) => {
          const [, y] = project([NAPLES_BBOX.minLon, lat]);
          return <line key={`lat-${lat}`} x1={0} y1={y} x2={MAP_WIDTH} y2={y} stroke="#16202F" strokeWidth={1} />;
        })}

        <g aria-label="Confini zone operative">
          {Object.keys(NAPLES_ZONES).map((zoneId) => {
            const points = zonePolygonPoints(zoneId);
            if (!points) return null;
            const [cx, cy] = project(NAPLES_ZONES[zoneId]?.center ?? [0, 0]);
            return (
              <g key={zoneId}>
                <polygon
                  points={points}
                  fill="#111C2C"
                  fillOpacity={0.55}
                  stroke={t.color.border.strong}
                  strokeWidth={1.2}
                  strokeDasharray="4 4"
                />
                <text x={cx} y={cy + 4} textAnchor="middle" fill={t.color.text.muted} fontSize={11}>
                  {zoneId}
                </text>
              </g>
            );
          })}
        </g>

        <DensityLayer findings={findings} />
        <VehicleMarkers vehicles={vehicles} />
        <FindingMarkers findings={findings} onMarkerClick={onMarkerClick} />

        {[
          { label: "Bagnoli", lat: 40.816, lon: 14.172 },
          { label: "Mergellina", lat: 40.829, lon: 14.219 },
          { label: "Municipio", lat: 40.84, lon: 14.253 },
          { label: "Garibaldi", lat: 40.853, lon: 14.272 },
        ].map((anchor) => {
          const [x, y] = projectPoint(anchor.lat, anchor.lon);
          return (
            <text key={anchor.label} x={x} y={y} fill={t.color.text.secondary} fontSize={11} textAnchor="middle">
              {anchor.label}
            </text>
          );
        })}
      </svg>

      <footer
        style={{
          position: "absolute",
          bottom: t.space[3],
          left: t.space[3],
          display: "flex",
          gap: t.space[3],
          background: t.color.overlay,
          border: `1px solid ${t.color.border.subtle}`,
          borderRadius: t.radius.sm,
          padding: `${t.space[1]} ${t.space[3]}`,
          fontSize: t.font.size.xs,
          color: t.color.text.secondary,
        }}
      >
        {(["low", "medium", "high", "critical"] as const).map((severity) => (
          <span key={severity} style={{ display: "inline-flex", alignItems: "center", gap: t.space[1] }}>
            <span
              style={{
                width: "8px",
                height: "8px",
                borderRadius: "50%",
                background: t.color.severity[severity],
              }}
            />
            {severity}
          </span>
        ))}
        <span style={{ display: "inline-flex", alignItems: "center", gap: t.space[1] }}>
          <span style={{ width: "10px", height: "2px", background: t.color.accent.primary }} /> flotta
        </span>
      </footer>

      {selectedZone ? (
        <MapPopover zoneId={selectedZone} findings={selectedFindings} onClose={onClosePopover} />
      ) : null}
    </section>
  );
}
