/**
 * @purpose Mappa reale di Napoli con overlay operativi allineati (Web Mercator)
 * @contracts Finding, VehiclePosition
 * @tokens operator
 * @verified 2026-11-15
 */

"use client";

import { useMemo } from "react";
import { operatorTokens as t } from "@/styles/design-tokens-operator";
import type { Finding, VehiclePosition } from "@/lib/types/contracts";
import { SlippyMap } from "@/components/map/SlippyMap";
import { DensityLayer } from "./DensityLayer";
import { FindingMarkers } from "./FindingMarkers";
import { VehicleMarkers } from "./VehicleMarkers";
import { MapPopover } from "./MapPopover";
import { NAPLES_BBOX, NAPLES_CENTER } from "./geo";

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
        background: "#0B1016",
        border: `1px solid ${t.color.border.subtle}`,
        borderRadius: t.radius.md,
        overflow: "hidden",
        height: "100%",
        minHeight: "520px",
      }}
      aria-label="Mappa operativa di Napoli"
    >
      <div style={{ position: "absolute", inset: 0 }}>
        <SlippyMap
          center={NAPLES_CENTER}
          zoom={12}
          minZoom={11}
          maxZoom={16}
          theme="dark"
          bounds={NAPLES_BBOX}
          ariaLabel="Mappa reale di Napoli con evidenze e flotta"
        >
          {(project) => (
            <>
              <DensityLayer findings={findings} project={project} />
              <VehicleMarkers vehicles={vehicles} project={project} />
              <FindingMarkers findings={findings} project={project} onMarkerClick={onMarkerClick} />
            </>
          )}
        </SlippyMap>
      </div>

      <header
        style={{
          position: "absolute",
          top: t.space[3],
          left: t.space[4],
          right: t.space[4],
          zIndex: 3,
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: t.space[2],
          flexWrap: "wrap",
          pointerEvents: "none",
        }}
      >
        <h2
          style={{
            margin: 0,
            fontSize: t.font.size.lg,
            fontWeight: t.font.weight.semibold,
            background: "rgba(11,16,22,0.78)",
            border: `1px solid ${t.color.border.subtle}`,
            borderRadius: t.radius.sm,
            padding: `${t.space[1]} ${t.space[3]}`,
            backdropFilter: "blur(4px)",
          }}
        >
          Live City Operations Map · Napoli
        </h2>
        <span
          style={{
            fontSize: "10px",
            color: t.color.text.secondary,
            background: "rgba(11,16,22,0.78)",
            border: `1px solid ${t.color.border.subtle}`,
            borderRadius: t.radius.pill,
            padding: "2px 8px",
            whiteSpace: "nowrap",
            backdropFilter: "blur(4px)",
          }}
        >
          bbox {NAPLES_BBOX.minLat}–{NAPLES_BBOX.maxLat} / {NAPLES_BBOX.minLon}–{NAPLES_BBOX.maxLon}
        </span>
      </header>

      <footer
        style={{
          position: "absolute",
          bottom: t.space[3],
          left: t.space[3],
          zIndex: 3,
          display: "flex",
          gap: t.space[3],
          background: "rgba(11,16,22,0.8)",
          border: `1px solid ${t.color.border.subtle}`,
          borderRadius: t.radius.sm,
          padding: `${t.space[1]} ${t.space[3]}`,
          fontSize: t.font.size.xs,
          color: t.color.text.secondary,
          backdropFilter: "blur(4px)",
          pointerEvents: "none",
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
