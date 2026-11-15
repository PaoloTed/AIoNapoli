"use client";

import { useMemo, useState } from "react";
import Map, { Layer, Marker, NavigationControl, Source } from "react-map-gl";
import clsx from "clsx";
import { zoneId, type Finding, type VehiclePosition } from "@/lib/contracts";
import { formatAgeSeconds, formatRomeTime, type Locale } from "@/lib/format";
import { getDict } from "@/lib/i18n";
import { NAPLES_DEFAULT_CENTER, NAPLES_ZONES } from "@/lib/scenarios";
import { ProvenanceChip } from "./ProvenanceChip";

type MapPanelProps = {
  findings: Finding[];
  vehiclePositions: VehiclePosition[];
  referenceTimeIso?: string | undefined;
  alternativeSummary?: string | undefined;
  compact?: boolean;
  hideInternalIds?: boolean;
  theme?: "dark" | "light";
  locale?: Locale;
  selectedZoneId?: string | null;
  onSelectZone?: (zoneId: string | null) => void;
};

export function MapPanel({
  findings,
  vehiclePositions,
  referenceTimeIso,
  alternativeSummary,
  compact = false,
  hideInternalIds = false,
  theme = "dark",
  locale = "it",
  selectedZoneId: externalSelectedZone,
  onSelectZone,
}: MapPanelProps) {
  const d = getDict(locale);
  const mapboxToken = process.env.NEXT_PUBLIC_MAPBOX_TOKEN?.trim() ?? "";
  const [internalSelectedZone, setInternalSelectedZone] = useState<string | null>(null);
  const [zoomLevel, setZoomLevel] = useState<number>(1);
  const [showVehicles, setShowVehicles] = useState<boolean>(true);
  const [showZones, setShowZones] = useState<boolean>(true);

  const activeSelectedZone = externalSelectedZone !== undefined ? externalSelectedZone : internalSelectedZone;

  const handleSelectZone = (zId: string | null) => {
    const next = activeSelectedZone === zId ? null : zId;
    if (onSelectZone) {
      onSelectZone(next);
    } else {
      setInternalSelectedZone(next);
    }
  };

  // Highlight zones strictly from finding content.zone_id via accessor (FE-REQ-10)
  const highlightedZoneIds = useMemo(() => {
    const ids = new Set<string>();
    for (const f of findings) {
      const z = zoneId(f);
      if (z !== undefined) {
        ids.add(z);
      }
    }
    return Array.from(ids);
  }, [findings]);

  const highlightedZoneSpecs = useMemo(
    () =>
      highlightedZoneIds
        .map((id) => NAPLES_ZONES[id])
        .filter((z): z is NonNullable<typeof z> => z !== undefined),
    [highlightedZoneIds],
  );

  const zonesGeoJson = useMemo(
    () => ({
      type: "FeatureCollection" as const,
      features: highlightedZoneSpecs.map((z) => ({
        type: "Feature" as const,
        properties: { zone_id: z.zone_id, label: z.label },
        geometry: {
          type: "Polygon" as const,
          coordinates: [z.polygon],
        },
      })),
    }),
    [highlightedZoneSpecs],
  );

  const initialCenter = useMemo<[number, number]>(() => {
    const firstVehicle = vehiclePositions[0];
    if (firstVehicle) {
      return [firstVehicle.longitude, firstVehicle.latitude];
    }
    const firstZone = highlightedZoneSpecs[0];
    if (firstZone) {
      return firstZone.center;
    }
    return NAPLES_DEFAULT_CENTER;
  }, [vehiclePositions, highlightedZoneSpecs]);

  const nowRefIso = useMemo(
    () => referenceTimeIso ?? vehiclePositions[0]?.observed_at ?? new Date().toISOString(),
    [referenceTimeIso, vehiclePositions],
  );

  // SVG Fallback projection calculation
  const svgBounds = useMemo(() => {
    let minLng = 14.15;
    let maxLng = 14.285;
    let minLat = 40.805;
    let maxLat = 40.865;

    for (const z of Object.values(NAPLES_ZONES)) {
      for (const [lng, lat] of z.polygon) {
        if (lng < minLng) minLng = lng;
        if (lng > maxLng) maxLng = lng;
        if (lat < minLat) minLat = lat;
        if (lat > maxLat) maxLat = lat;
      }
    }
    for (const v of vehiclePositions) {
      if (v.longitude < minLng) minLng = v.longitude;
      if (v.longitude > maxLng) maxLng = v.longitude;
      if (v.latitude < minLat) minLat = v.latitude;
      if (v.latitude > maxLat) maxLat = v.latitude;
    }

    const dLng = (maxLng - minLng) * 0.08 || 0.01;
    const dLat = (maxLat - minLat) * 0.08 || 0.01;
    return {
      minLng: minLng - dLng,
      maxLng: maxLng + dLng,
      minLat: minLat - dLat,
      maxLat: maxLat + dLat,
    };
  }, [vehiclePositions]);

  const svgWidth = 640;
  const svgHeight = compact ? 220 : 320;
  const padX = 35;
  const padY = 30;

  const projectToSvg = (lng: number, lat: number): [number, number] => {
    const x =
      ((lng - svgBounds.minLng) / (svgBounds.maxLng - svgBounds.minLng)) *
        (svgWidth - 2 * padX) +
      padX;
    const y =
      ((svgBounds.maxLat - lat) / (svgBounds.maxLat - svgBounds.minLat)) *
        (svgHeight - 2 * padY) +
      padY;
    return [Math.round(x * 10) / 10, Math.round(y * 10) / 10];
  };

  const vbW = svgWidth / zoomLevel;
  const vbH = svgHeight / zoomLevel;
  const vbX = (svgWidth - vbW) / 2;
  const vbY = (svgHeight - vbH) / 2;

  const mapStyle =
    theme === "dark" ? "mapbox://styles/mapbox/dark-v11" : "mapbox://styles/mapbox/light-v11";

  return (
    <section
      className="rounded-[10px] border border-[var(--border)] bg-[var(--surface)] p-4 space-y-3"
      data-testid="map-panel"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <h2 className="text-[11px] font-medium uppercase tracking-wider text-[var(--text-muted)]">
            {d.operator.mapTitle}
          </h2>
          {mapboxToken.length === 0 && (
            <span
              className="rounded-[4px] border border-[var(--border)] bg-[var(--bg)] px-1.5 py-0.5 font-mono text-[10px] uppercase text-[var(--text-muted)]"
              data-testid="map-engine-badge"
            >
              SVG Locale
            </span>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {/* Layer toggles */}
          <button
            type="button"
            onClick={() => setShowZones((prev) => !prev)}
            className={clsx(
              "rounded-[4px] border px-1.5 py-0.5 font-mono text-[10px] transition-colors cursor-pointer",
              showZones
                ? "border-[#D06A32] bg-[#D06A32]/15 text-[var(--text)] font-semibold"
                : "border-[var(--border)] text-[var(--text-muted)] opacity-60",
            )}
            title="Mostra / Nascondi zone"
          >
            Zone ({highlightedZoneIds.length})
          </button>
          <button
            type="button"
            onClick={() => setShowVehicles((prev) => !prev)}
            className={clsx(
              "rounded-[4px] border px-1.5 py-0.5 font-mono text-[10px] transition-colors cursor-pointer",
              showVehicles
                ? "border-[#4FB3D9] bg-[#4FB3D9]/15 text-[var(--text)] font-semibold"
                : "border-[var(--border)] text-[var(--text-muted)] opacity-60",
            )}
            title="Mostra / Nascondi mezzi"
          >
            Mezzi ({vehiclePositions.length})
          </button>

          {/* Zoom controls */}
          <div className="inline-flex rounded-[4px] border border-[var(--border)] bg-[var(--bg)] p-0.5">
            <button
              type="button"
              onClick={() => setZoomLevel((z) => Math.max(1, Math.round((z - 0.25) * 100) / 100))}
              disabled={zoomLevel <= 1}
              className="px-1.5 py-0.2 font-mono text-[10px] text-[var(--text-muted)] hover:text-[var(--text)] disabled:opacity-30 cursor-pointer"
              title="Zoom out"
            >
              −
            </button>
            <button
              type="button"
              onClick={() => setZoomLevel(1)}
              className="px-1.5 py-0.2 font-mono text-[10px] text-[var(--text-muted)] hover:text-[var(--text)] cursor-pointer"
              title="Reset zoom"
            >
              {Math.round(zoomLevel * 100)}%
            </button>
            <button
              type="button"
              onClick={() => setZoomLevel((z) => Math.min(2.5, Math.round((z + 0.25) * 100) / 100))}
              disabled={zoomLevel >= 2.5}
              className="px-1.5 py-0.2 font-mono text-[10px] text-[var(--text-muted)] hover:text-[var(--text)] disabled:opacity-30 cursor-pointer"
              title="Zoom in"
            >
              +
            </button>
          </div>
        </div>
      </div>

      {/* Map canvas: Mapbox GL if token provided, otherwise deterministic SVG fallback (FE-REQ-12) */}
      <div
        className={clsx(
          "relative overflow-hidden rounded-[6px] border border-[var(--border)] bg-[var(--bg)]",
          compact ? "h-[220px]" : "h-[260px] md:h-[340px]",
        )}
      >
        {mapboxToken.length > 0 ? (
          <Map
            mapboxAccessToken={mapboxToken}
            initialViewState={{
              longitude: initialCenter[0],
              latitude: initialCenter[1],
              zoom: 12.6,
            }}
            mapStyle={mapStyle}
            style={{ width: "100%", height: "100%" }}
            attributionControl={false}
          >
            <NavigationControl position="top-right" showCompass={false} />

            {highlightedZoneSpecs.length > 0 && (
              <Source id="highlighted-zones" type="geojson" data={zonesGeoJson}>
                <Layer
                  id="zone-fill"
                  type="fill"
                  paint={{
                    "fill-color": "#D06A32",
                    "fill-opacity": 0.22,
                  }}
                />
                <Layer
                  id="zone-outline"
                  type="line"
                  paint={{
                    "line-color": "#D06A32",
                    "line-width": 2,
                  }}
                />
              </Source>
            )}

            {vehiclePositions.map((v) => (
              <Marker
                key={v.vehicle_id}
                longitude={v.longitude}
                latitude={v.latitude}
                anchor="center"
              >
                <div
                  className={clsx(
                    "cursor-pointer rounded-[6px] border px-1.5 py-0.5 font-mono text-[11px] font-medium transition-transform hover:scale-110",
                    v.is_simulated
                      ? "border-dashed border-[var(--border)] bg-[var(--surface)] text-[var(--text-muted)]"
                      : "border-solid border-[var(--accent)] bg-[var(--surface)] text-[var(--text)]",
                  )}
                  title={
                    hideInternalIds
                      ? (v.route_id ?? d.map.routeLabel)
                      : `${v.vehicle_id} (${v.route_id ?? "-"})`
                  }
                >
                  {v.route_id ?? (hideInternalIds ? "BUS" : v.vehicle_id)}
                </div>
              </Marker>
            ))}
          </Map>
        ) : (
          <div className="relative h-full w-full select-none" data-testid="map-not-configured">
            {/* SVG Local Deterministic Map with Zoom & Layer Toggles */}
            <svg
              viewBox={`${vbX} ${vbY} ${vbW} ${vbH}`}
              className="h-full w-full transition-all duration-200"
              aria-label="Mappa vettoriale Napoli"
            >
              <defs>
                <pattern id="mapGrid" width="40" height="40" patternUnits="userSpaceOnUse">
                  <path
                    d="M 40 0 L 0 0 0 40"
                    fill="none"
                    stroke={theme === "dark" ? "#1A232E" : "#EAE8E2"}
                    strokeWidth="1"
                  />
                </pattern>
                {/* Coastal gradient representation */}
                <linearGradient id="gulfGradient" x1="0%" y1="100%" x2="100%" y2="0%">
                  <stop
                    offset="0%"
                    stopColor={theme === "dark" ? "#0F1A24" : "#EAF2F8"}
                    stopOpacity="0.8"
                  />
                  <stop
                    offset="100%"
                    stopColor={theme === "dark" ? "#0B1016" : "#FAFAF8"}
                    stopOpacity="0.2"
                  />
                </linearGradient>
              </defs>

              {/* Background grid */}
              <rect width={svgWidth} height={svgHeight} fill="url(#mapGrid)" />

              {/* Stylized Gulf of Naples water curve (South/South-West) */}
              <path
                d={`M 0 ${svgHeight} L 0 ${Math.round(svgHeight * 0.75)} Q ${Math.round(svgWidth * 0.35)} ${Math.round(svgHeight * 0.85)} ${Math.round(svgWidth * 0.7)} ${Math.round(svgHeight * 0.95)} L ${svgWidth} ${svgHeight} Z`}
                fill="url(#gulfGradient)"
              />
              <text
                x="45"
                y={svgHeight - 14}
                className="font-mono text-[9px] uppercase tracking-widest"
                fill={theme === "dark" ? "#4A5A6A" : "#8A9AA8"}
              >
                Golfo di Napoli (Tirreno)
              </text>

              {/* All Known Zones as subtle boundary background */}
              {showZones &&
                Object.values(NAPLES_ZONES).map((z) => {
                  const isHighlighted = highlightedZoneIds.includes(z.zone_id);
                  const isSelected = activeSelectedZone === z.zone_id;
                  const projPts = z.polygon.map(([lng, lat]) => projectToSvg(lng, lat));
                  const points = projPts.map((p) => p.join(",")).join(" ");

                  const minProjX = Math.min(...projPts.map((p) => p[0]));
                  const maxProjX = Math.max(...projPts.map((p) => p[0]));
                  const minProjY = Math.min(...projPts.map((p) => p[1]));

                  const labelCenterX = (minProjX + maxProjX) / 2;
                  const labelTopY = minProjY + 11;
                  const badgeW = Math.max(42, z.label.length * 6.8 + 12);

                  return (
                    <g
                      key={z.zone_id}
                      onClick={() => handleSelectZone(z.zone_id)}
                      className="cursor-pointer transition-all"
                    >
                      <polygon
                        points={points}
                        fill={
                          isSelected
                            ? "rgba(208, 106, 50, 0.32)"
                            : isHighlighted
                              ? "rgba(208, 106, 50, 0.18)"
                              : theme === "dark"
                                ? "rgba(255, 255, 255, 0.02)"
                                : "rgba(0, 0, 0, 0.02)"
                        }
                        stroke={
                          isSelected
                            ? "#D06A32"
                            : isHighlighted
                              ? "#D06A32"
                              : theme === "dark"
                                ? "#22303D"
                                : "#D2D0CA"
                        }
                        strokeWidth={isSelected ? 3 : isHighlighted ? 2 : 1}
                        strokeDasharray={isHighlighted ? undefined : "3,3"}
                      />
                      {/* Background pill to prevent overlap with roads or vehicle pills */}
                      <rect
                        x={labelCenterX - badgeW / 2}
                        y={labelTopY - 9}
                        width={badgeW}
                        height={!hideInternalIds ? 21 : 13}
                        rx={3}
                        fill={
                          theme === "dark"
                            ? "rgba(11, 16, 22, 0.88)"
                            : "rgba(250, 250, 248, 0.92)"
                        }
                        stroke={
                          isSelected || isHighlighted
                            ? "#D06A32"
                            : theme === "dark"
                              ? "#22303D"
                              : "#D2D0CA"
                        }
                        strokeWidth={0.75}
                      />
                      <text
                        x={labelCenterX}
                        y={labelTopY + 1.5}
                        textAnchor="middle"
                        className="select-none font-sans text-[10px] font-semibold tracking-wide"
                        fill={
                          isHighlighted
                            ? theme === "dark"
                              ? "#FFFFFF"
                              : "#141A20"
                            : theme === "dark"
                              ? "#8A9BA8"
                              : "#5A6572"
                        }
                      >
                        {z.label}
                      </text>
                      {!hideInternalIds && (
                        <text
                          x={labelCenterX}
                          y={labelTopY + 10}
                          textAnchor="middle"
                          className="select-none font-mono text-[8px]"
                          fill={isHighlighted ? "#D06A32" : theme === "dark" ? "#5C6874" : "#9AA4AF"}
                        >
                          {z.zone_id}
                        </text>
                      )}
                    </g>
                  );
                })}

              {/* Vehicle Markers with Transit Dots */}
              {showVehicles &&
                vehiclePositions.map((v) => {
                  const [vx, vy] = projectToSvg(v.longitude, v.latitude);
                  const routeLabel = v.route_id ?? (hideInternalIds ? "BUS" : v.vehicle_id.slice(-4));
                  const pillWidth = Math.max(34, routeLabel.length * 7 + 16);

                  return (
                    <g key={v.vehicle_id} className="cursor-pointer transition-transform hover:scale-105">
                      <rect
                        x={vx - pillWidth / 2}
                        y={vy - 8.5}
                        width={pillWidth}
                        height={17}
                        rx={4}
                        fill={theme === "dark" ? "#131A23" : "#FFFFFF"}
                        stroke={v.is_simulated ? "#D06A32" : "#4FB3D9"}
                        strokeWidth={1.5}
                        strokeDasharray={v.is_simulated ? "3,2" : undefined}
                      />
                      <circle
                        cx={vx - pillWidth / 2 + 7}
                        cy={vy}
                        r={2.5}
                        fill={v.is_simulated ? "#D06A32" : "#2D8A4E"}
                      />
                      <text
                        x={vx + 4}
                        y={vy + 3.5}
                        textAnchor="middle"
                        className="font-mono text-[9px] font-bold"
                        fill={theme === "dark" ? "#E8EDF2" : "#141A20"}
                      >
                        {routeLabel}
                      </text>
                      <title>
                        {hideInternalIds
                          ? `${d.map.routeLabel} ${v.route_id ?? "-"}`
                          : `${v.vehicle_id} (Linea ${v.route_id ?? "-"}) · ${v.is_simulated ? "SIMULATO" : "REALE"}`}
                      </title>
                    </g>
                  );
                })}
            </svg>

            {/* Offline Local Map Notice & Contract Boundaries (SCREENS.md §3) */}
            <div className="pointer-events-none absolute bottom-2 left-2 right-2 flex flex-wrap items-center justify-between gap-1.5 rounded-[4px] bg-[var(--surface)]/90 px-2 py-1 backdrop-blur-xs text-[10px] text-[var(--text-muted)] border border-[var(--border)]">
              <span>
                Mappa locale SVG (WGS84) · Geo-fence {highlightedZoneIds.length} zone · {vehiclePositions.length} mezzi
              </span>
              <span className="font-mono text-[9px]">
                Fermate e percorsi non esposti (FE-REQ-02, FE-REQ-10)
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Alternative route text when available */}
      {alternativeSummary && (
        <div className="rounded-[6px] border border-[var(--border)] bg-[var(--bg)] px-3 py-2 text-[13px] text-[var(--text)]">
          {alternativeSummary}
        </div>
      )}

      {/* Accessible text representation of every map element (DESIGN.md §4) */}
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="space-y-1.5" data-testid="map-zones-text">
          <p className="text-[11px] font-medium uppercase tracking-wider text-[var(--text-muted)]">
            {d.map.zonesTitle}
          </p>
          {highlightedZoneIds.length === 0 ? (
            <p className="text-[13px] text-[var(--text-muted)]">{d.map.noHighlightedZone}</p>
          ) : (
            <ul className="flex flex-wrap gap-1.5">
              {highlightedZoneIds.map((zId) => {
                const known = NAPLES_ZONES[zId];
                const isSelected = activeSelectedZone === zId;
                return (
                  <li
                    key={zId}
                    data-highlighted-zone={zId}
                    onClick={() => handleSelectZone(zId)}
                    className={clsx(
                      "cursor-pointer rounded-[6px] border px-2 py-0.5 text-[12px] transition-colors",
                      isSelected
                        ? "border-[#D06A32] bg-[#D06A32]/15 text-[var(--text)] font-semibold"
                        : "border-[#D06A32]/60 hover:border-[#D06A32] text-[var(--text)]",
                    )}
                  >
                    {hideInternalIds ? (
                      <span>{known?.label ?? zId}</span>
                    ) : (
                      <code className="font-mono text-[12px]">
                        {zId}
                        {known ? ` (${known.label})` : ""}
                      </code>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </div>

        <div className="space-y-1.5" data-testid="map-vehicles-text">
          <p className="text-[11px] font-medium uppercase tracking-wider text-[var(--text-muted)]">
            {d.map.vehiclesTitle}
          </p>
          {vehiclePositions.length === 0 ? (
            <p className="text-[13px] text-[var(--text-muted)]">{d.map.noVehicles}</p>
          ) : (
            <ul className="space-y-1.5">
              {vehiclePositions.map((v) => {
                const age = formatAgeSeconds(v.observed_at, nowRefIso, locale);
                return (
                  <li
                    key={v.vehicle_id}
                    className={clsx(
                      "flex flex-wrap items-center justify-between gap-2 rounded-[6px] border bg-[var(--bg)] px-2.5 py-1.5 text-[13px]",
                      v.is_simulated
                        ? "border-dashed border-[var(--border)]"
                        : "border-solid border-[var(--border)]",
                    )}
                  >
                    <div className="flex items-center gap-2">
                      <ProvenanceChip
                        variant={v.is_simulated ? "simulated" : "real"}
                        locale={locale}
                      />
                      <span className="font-medium text-[var(--text)]">
                        {v.route_id ? `${d.map.routeLabel} ${v.route_id}` : d.map.routeLabel}
                      </span>
                      {!hideInternalIds && (
                        <code className="font-mono text-[12px] text-[var(--text-muted)]">
                          {v.vehicle_id} ({v.source_id})
                        </code>
                      )}
                    </div>

                    <span className="font-mono text-[12px] text-[var(--text-muted)]">
                      {formatRomeTime(v.observed_at, locale)}
                      {age ? ` · ${age}` : ""}
                    </span>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      </div>
    </section>
  );
}
