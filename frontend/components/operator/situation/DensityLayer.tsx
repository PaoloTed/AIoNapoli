/**
 * @purpose Superfici semitrasparenti delle zone con saturazione critica
 * @contracts Finding
 * @tokens operator
 * @verified 2026-11-15
 */

import { operatorTokens as t } from "@/styles/design-tokens-operator";
import type { Finding } from "@/lib/types/contracts";
import { aggregateByZone, zonePolygonPoints } from "./geo";

export function DensityLayer({ findings }: { findings: Finding[] }) {
  return (
    <g aria-label="Aree ad alta densità">
      {aggregateByZone(findings)
        .filter((zone) => zone.density >= 0.6)
        .map((zone) => {
          const points = zonePolygonPoints(zone.zoneId);
          if (!points) return null;
          const critical = zone.density >= 0.8;
          const color = critical ? t.color.severity.critical : t.color.severity.medium;
          return (
            <polygon
              key={zone.zoneId}
              points={points}
              fill={color}
              fillOpacity={critical ? 0.28 : 0.16}
              stroke={color}
              strokeOpacity={0.65}
              strokeWidth={1.5}
            />
          );
        })}
    </g>
  );
}
