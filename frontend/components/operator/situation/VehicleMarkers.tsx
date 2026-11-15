/**
 * @purpose Marker direzionali della flotta proiettati sulla mappa reale
 * @contracts VehiclePosition
 * @tokens operator
 * @verified 2026-11-15
 */

import { operatorTokens as t } from "@/styles/design-tokens-operator";
import type { VehiclePosition } from "@/lib/types/contracts";
import type { MapProjection } from "@/components/map/SlippyMap";
import { vehiclePositionsInBounds } from "./geo";

export function VehicleMarkers({
  vehicles,
  project,
}: {
  vehicles: VehiclePosition[];
  project: MapProjection;
}) {
  return (
    <>
      {vehiclePositionsInBounds(vehicles).map((vehicle) => {
        const { x, y } = project(vehicle.latitude, vehicle.longitude);
        const bearing = vehicle.bearing ?? 0;
        return (
          <div
            key={vehicle.vehicle_id}
            title={`${vehicle.vehicle_id}${vehicle.route_id ? ` · linea ${vehicle.route_id}` : ""}${
              vehicle.is_simulated ? " (simulato)" : ""
            }`}
            style={{
              position: "absolute",
              left: `${x}px`,
              top: `${y}px`,
              width: "18px",
              height: "18px",
              transform: `translate(-50%, -50%) rotate(${bearing}deg)`,
              pointerEvents: "none",
            }}
          >
            <svg viewBox="0 0 18 18" width="18" height="18" aria-hidden="true">
              <path
                d="M 9 1 L 15 16 L 9 12 L 3 16 Z"
                fill={t.color.accent.primary}
                stroke={vehicle.is_simulated ? t.color.severity.medium : "#0B1016"}
                strokeWidth={1.2}
                strokeDasharray={vehicle.is_simulated ? "2 2" : undefined}
              />
            </svg>
          </div>
        );
      })}
    </>
  );
}
