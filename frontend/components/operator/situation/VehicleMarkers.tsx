/**
 * @purpose Marker direzionali della flotta con bordo tratteggiato se simulati
 * @contracts VehiclePosition
 * @tokens operator
 * @verified 2026-11-15
 */

import { operatorTokens as t } from "@/styles/design-tokens-operator";
import type { VehiclePosition } from "@/lib/types/contracts";
import { projectPoint, vehiclePositionsInBounds } from "./geo";

export function VehicleMarkers({ vehicles }: { vehicles: VehiclePosition[] }) {
  return (
    <g aria-label="Posizioni flotta">
      {vehiclePositionsInBounds(vehicles).map((vehicle) => {
        const [x, y] = projectPoint(vehicle.latitude, vehicle.longitude);
        const bearing = vehicle.bearing ?? 0;
        return (
          <g key={vehicle.vehicle_id} transform={`translate(${x} ${y}) rotate(${bearing})`}>
            <path
              d="M 0 -8 L 6 6 L 0 3 L -6 6 Z"
              fill={t.color.accent.primary}
              stroke={vehicle.is_simulated ? t.color.severity.medium : t.color.bg.base}
              strokeWidth={1.2}
              strokeDasharray={vehicle.is_simulated ? "2 2" : undefined}
              opacity={0.95}
            />
            <title>
              {vehicle.vehicle_id}
              {vehicle.route_id ? ` · linea ${vehicle.route_id}` : ""}
              {vehicle.is_simulated ? " (simulato)" : ""}
            </title>
          </g>
        );
      })}
    </g>
  );
}
