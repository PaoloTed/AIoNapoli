"use client";

import { useMemo } from "react";
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
}: MapPanelProps) {
  const d = getDict(locale);
  const mapboxToken = process.env.NEXT_PUBLIC_MAPBOX_TOKEN?.trim() ?? "";

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

  const mapStyle =
    theme === "dark" ? "mapbox://styles/mapbox/dark-v11" : "mapbox://styles/mapbox/light-v11";

  return (
    <section
      className="rounded-[10px] border border-[var(--border)] bg-[var(--surface)] p-4 space-y-3"
      data-testid="map-panel"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-[11px] font-medium uppercase tracking-wider text-[var(--text-muted)]">
          {d.operator.mapTitle}
        </h2>
        <span className="font-mono text-[12px] text-[var(--text-muted)]">
          {vehiclePositions.length} {locale === "en" ? "vehicles" : "mezzi"}
        </span>
      </div>

      {/* Map canvas or declared empty state when NEXT_PUBLIC_MAPBOX_TOKEN is missing (FE-REQ-12) */}
      <div
        className={clsx(
          "overflow-hidden rounded-[6px] border border-[var(--border)] bg-[var(--bg)]",
          compact ? "h-[200px]" : "h-[240px] md:h-[340px]",
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
                    "fill-opacity": 0.18,
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
                    "rounded-[6px] border px-1.5 py-0.5 font-mono text-[11px] font-medium",
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
          <div
            className="flex h-full flex-col items-start justify-center p-4 space-y-1.5"
            data-testid="map-not-configured"
          >
            <p className="text-[11px] font-medium uppercase tracking-wider text-[var(--text-muted)]">
              {d.map.notConfiguredTitle}
            </p>
            <p className="text-[14px] text-[var(--text-muted)] max-w-md">
              {d.map.notConfiguredDetail}
            </p>
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
                return (
                  <li
                    key={zId}
                    data-highlighted-zone={zId}
                    className="rounded-[6px] border border-[#D06A32] px-2 py-0.5 text-[12px] text-[var(--text)]"
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
