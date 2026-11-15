/**
 * @purpose Superfici semitrasparenti delle zone con saturazione critica su mappa reale
 * @contracts Finding
 * @tokens operator
 * @verified 2026-11-15
 */

import { operatorTokens as t } from "@/styles/design-tokens-operator";
import type { Finding } from "@/lib/types/contracts";
import type { MapProjection } from "@/components/map/SlippyMap";
import { aggregateByZone, zoneRingLatLng } from "./geo";

export function DensityLayer({
  findings,
  project,
}: {
  findings: Finding[];
  project: MapProjection;
}) {
  const areas = aggregateByZone(findings)
    .filter((zone) => zone.density >= 0.6)
    .map((zone) => ({
      zoneId: zone.zoneId,
      density: zone.density,
      points: zoneRingLatLng(zone.zoneId)
        .map((point) => {
          const { x, y } = project(point.lat, point.lng);
          return `${x},${y}`;
        })
        .join(" "),
    }))
    .filter((area) => area.points.length > 0);

  return (
    <svg
      aria-hidden="true"
      style={{ position: "absolute", inset: 0, width: "100%", height: "100%", pointerEvents: "none" }}
    >
      {areas.map((area) => {
        const critical = area.density >= 0.8;
        const color = critical ? t.color.severity.critical : t.color.severity.medium;
        return (
          <polygon
            key={area.zoneId}
            points={area.points}
            fill={color}
            fillOpacity={critical ? 0.24 : 0.14}
            stroke={color}
            strokeOpacity={0.75}
            strokeWidth={1.5}
            strokeDasharray={critical ? undefined : "5 4"}
          />
        );
      })}
    </svg>
  );
}
