/**
 * @purpose Mappa a tile reale (OpenStreetMap/CARTO) con proiezione Web Mercator condivisa
 * @contracts nessuno (componente grafico)
 * @tokens shared
 * @verified 2026-11-15
 */

"use client";

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type PointerEvent as ReactPointerEvent,
  type ReactNode,
} from "react";

const TILE_SIZE = 256;
const MAX_LATITUDE = 85.05112878;

export type LatLng = { lat: number; lng: number };
export type MapProjection = (lat: number, lng: number) => { x: number; y: number };
export type MapBounds = { minLat: number; maxLat: number; minLon: number; maxLon: number };

export const MAP_THEME_TILES = {
  dark: "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
  light: "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
} as const;

const SUBDOMAINS = ["a", "b", "c", "d"] as const;

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

export function lngToWorldX(lng: number, zoom: number): number {
  return ((lng + 180) / 360) * TILE_SIZE * 2 ** zoom;
}

export function latToWorldY(lat: number, zoom: number): number {
  const clamped = clamp(lat, -MAX_LATITUDE, MAX_LATITUDE);
  const rad = (clamped * Math.PI) / 180;
  return (
    (0.5 - Math.log((1 + Math.sin(rad)) / (1 - Math.sin(rad))) / (4 * Math.PI)) *
    TILE_SIZE *
    2 ** zoom
  );
}

export function worldXToLng(x: number, zoom: number): number {
  return (x / (TILE_SIZE * 2 ** zoom)) * 360 - 180;
}

export function worldYToLat(y: number, zoom: number): number {
  const n = Math.PI - (2 * Math.PI * y) / (TILE_SIZE * 2 ** zoom);
  return (180 / Math.PI) * Math.atan(Math.sinh(n));
}

function clampCenter(center: LatLng, bounds?: MapBounds): LatLng {
  if (!bounds) {
    return {
      lat: clamp(center.lat, -MAX_LATITUDE, MAX_LATITUDE),
      lng: center.lng,
    };
  }
  return {
    lat: clamp(center.lat, bounds.minLat, bounds.maxLat),
    lng: clamp(center.lng, bounds.minLon, bounds.maxLon),
  };
}

function tileUrl(theme: keyof typeof MAP_THEME_TILES, z: number, x: number, y: number): string {
  const subdomain = SUBDOMAINS[(x + y) % SUBDOMAINS.length] ?? "a";
  return MAP_THEME_TILES[theme]
    .replace("{s}", subdomain)
    .replace("{z}", String(z))
    .replace("{x}", String(x))
    .replace("{y}", String(y));
}

export function SlippyMap({
  center = { lat: 40.835, lng: 14.215 },
  zoom = 13,
  minZoom = 11,
  maxZoom = 16,
  theme = "dark",
  bounds,
  controls = true,
  ariaLabel = "Mappa di Napoli",
  children,
  style,
}: {
  center?: LatLng;
  zoom?: number;
  minZoom?: number;
  maxZoom?: number;
  theme?: keyof typeof MAP_THEME_TILES;
  bounds?: MapBounds;
  controls?: boolean;
  ariaLabel?: string;
  children?: (project: MapProjection) => ReactNode;
  style?: CSSProperties;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const dragRef = useRef<{
    pointerId: number;
    startX: number;
    startY: number;
    worldX: number;
    worldY: number;
  } | null>(null);
  const [size, setSize] = useState({ width: 0, height: 0 });
  const [view, setView] = useState<{ center: LatLng; zoom: number }>({
    center: clampCenter(center, bounds),
    zoom: clamp(zoom, minZoom, maxZoom),
  });

  useEffect(() => {
    setView({
      center: clampCenter(center, bounds),
      zoom: clamp(zoom, minZoom, maxZoom),
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [center.lat, center.lng, zoom, minZoom, maxZoom]);

  useEffect(() => {
    const element = containerRef.current;
    if (!element) return;
    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (!entry) return;
      const { width, height } = entry.contentRect;
      setSize((prev) =>
        Math.round(prev.width) === Math.round(width) && Math.round(prev.height) === Math.round(height)
          ? prev
          : { width, height },
      );
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  const worldSize = TILE_SIZE * 2 ** view.zoom;
  const centerWorldX = lngToWorldX(view.center.lng, view.zoom);
  const centerWorldY = latToWorldY(view.center.lat, view.zoom);
  const left = centerWorldX - size.width / 2;
  const top = centerWorldY - size.height / 2;

  const project = useCallback<MapProjection>(
    (lat, lng) => ({
      x: lngToWorldX(lng, view.zoom) - left,
      y: latToWorldY(lat, view.zoom) - top,
    }),
    [view.zoom, left, top],
  );

  const tiles = useMemo(() => {
    if (size.width === 0 || size.height === 0) return [];
    const tileCount = 2 ** view.zoom;
    const xStart = Math.floor(left / TILE_SIZE);
    const xEnd = Math.floor((left + size.width) / TILE_SIZE);
    const yStart = Math.max(0, Math.floor(top / TILE_SIZE));
    const yEnd = Math.min(tileCount - 1, Math.floor((top + size.height) / TILE_SIZE));
    const items: Array<{ key: string; src: string; left: number; top: number }> = [];

    for (let x = xStart; x <= xEnd; x += 1) {
      for (let y = yStart; y <= yEnd; y += 1) {
        const wrappedX = ((x % tileCount) + tileCount) % tileCount;
        items.push({
          key: `${view.zoom}-${x}-${y}`,
          src: tileUrl(theme, view.zoom, wrappedX, y),
          left: x * TILE_SIZE - left,
          top: y * TILE_SIZE - top,
        });
      }
    }
    return items;
  }, [size, view.zoom, left, top, theme]);

  const onPointerDown = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (event.button !== 0) return;
    event.currentTarget.setPointerCapture(event.pointerId);
    dragRef.current = {
      pointerId: event.pointerId,
      startX: event.clientX,
      startY: event.clientY,
      worldX: lngToWorldX(view.center.lng, view.zoom),
      worldY: latToWorldY(view.center.lat, view.zoom),
    };
  };

  const onPointerMove = (event: ReactPointerEvent<HTMLDivElement>) => {
    const drag = dragRef.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    const nextX = drag.worldX - (event.clientX - drag.startX);
    const nextY = drag.worldY - (event.clientY - drag.startY);
    setView((prev) => ({
      ...prev,
      center: clampCenter(
        {
          lat: worldYToLat(clamp(nextY, 0, worldSize), prev.zoom),
          lng: worldXToLng(nextX, prev.zoom),
        },
        bounds,
      ),
    }));
  };

  const endDrag = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (dragRef.current?.pointerId === event.pointerId) {
      dragRef.current = null;
      if (event.currentTarget.hasPointerCapture(event.pointerId)) {
        event.currentTarget.releasePointerCapture(event.pointerId);
      }
    }
  };

  const zoomBy = (delta: number) => {
    setView((prev) => ({
      ...prev,
      zoom: clamp(prev.zoom + delta, minZoom, maxZoom),
      center: clampCenter(prev.center, bounds),
    }));
  };

  return (
    <div
      ref={containerRef}
      role="region"
      aria-label={ariaLabel}
      style={{
        position: "relative",
        width: "100%",
        height: "100%",
        minHeight: "240px",
        overflow: "hidden",
        background: theme === "dark" ? "#0B1016" : "#E2E8F0",
        touchAction: "none",
        ...style,
      }}
    >
      <div
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={endDrag}
        onPointerCancel={endDrag}
        style={{
          position: "absolute",
          inset: 0,
          cursor: "grab",
          userSelect: "none",
        }}
      >
        {tiles.map((tile) => (
          // eslint-disable-next-line @next/next/no-img-element -- tile raster esterni non ottimizzabili da next/image
          <img
            key={tile.key}
            src={tile.src}
            alt=""
            aria-hidden="true"
            draggable={false}
            style={{
              position: "absolute",
              left: `${tile.left}px`,
              top: `${tile.top}px`,
              width: `${TILE_SIZE}px`,
              height: `${TILE_SIZE}px`,
              maxWidth: "none",
              filter:
                theme === "dark"
                  ? "invert(1) hue-rotate(180deg) brightness(0.92) contrast(1.12) saturate(0.85)"
                  : undefined,
            }}
          />
        ))}
      </div>

      <div style={{ position: "absolute", inset: 0, pointerEvents: "none" }}>
        {size.width > 0 && size.height > 0 ? children?.(project) : null}
      </div>

      <div
        style={{
          position: "absolute",
          right: "6px",
          bottom: "4px",
          fontSize: "9px",
          color: theme === "dark" ? "rgba(226,232,240,0.65)" : "rgba(15,23,42,0.55)",
          background: theme === "dark" ? "rgba(11,16,22,0.55)" : "rgba(255,255,255,0.65)",
          padding: "1px 5px",
          borderRadius: "3px",
          pointerEvents: "auto",
        }}
      >
        ©{" "}
        <a
          href="https://www.openstreetmap.org/copyright"
          target="_blank"
          rel="noreferrer"
          style={{ color: "inherit" }}
        >
          OpenStreetMap contributors
        </a>
      </div>

      {controls ? (
        <div
          style={{
            position: "absolute",
            right: "8px",
            bottom: "28px",
            display: "grid",
            gap: "4px",
            pointerEvents: "auto",
          }}
        >
          {[
            { label: "+", action: () => zoomBy(1), disabled: view.zoom >= maxZoom },
            { label: "−", action: () => zoomBy(-1), disabled: view.zoom <= minZoom },
          ].map((control) => (
            <button
              key={control.label}
              type="button"
              aria-label={control.label === "+" ? "Zoom avanti" : "Zoom indietro"}
              onClick={control.action}
              disabled={control.disabled}
              style={{
                width: "30px",
                height: "30px",
                border: `1px solid ${theme === "dark" ? "rgba(148,163,184,0.4)" : "rgba(100,116,139,0.35)"}`,
                borderRadius: "6px",
                background: theme === "dark" ? "rgba(17,24,39,0.9)" : "rgba(255,255,255,0.95)",
                color: theme === "dark" ? "#E2E8F0" : "#0F172A",
                fontSize: "16px",
                lineHeight: 1,
                cursor: control.disabled ? "not-allowed" : "pointer",
                opacity: control.disabled ? 0.45 : 1,
              }}
            >
              {control.label}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
