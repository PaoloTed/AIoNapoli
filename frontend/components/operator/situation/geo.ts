/**
 * @purpose Aggregazioni geografiche delle zone operative per la mappa reale
 * @contracts Finding, VehiclePosition
 * @tokens operator
 * @verified 2026-11-15
 */

import { NAPLES_ZONES } from "@/lib/scenarios";
import type { Finding, Severity, VehiclePosition } from "@/lib/types/contracts";
import type { LatLng } from "@/components/map/SlippyMap";

export const NAPLES_BBOX = {
  minLon: 14.1,
  maxLon: 14.4,
  minLat: 40.75,
  maxLat: 40.95,
} as const;

export const NAPLES_CENTER: LatLng = { lat: 40.84, lng: 14.2 };

export function zoneCenterLatLng(zoneId: string): LatLng | null {
  const zone = NAPLES_ZONES[zoneId];
  if (!zone) return null;
  const [lng, lat] = zone.center;
  return { lat, lng };
}

export function zoneRingLatLng(zoneId: string): LatLng[] {
  const zone = NAPLES_ZONES[zoneId];
  if (!zone) return [];
  return zone.polygon.map(([lng, lat]) => ({ lat, lng }));
}

const SEVERITY_RANK: Record<Severity, number> = { low: 1, medium: 2, high: 3, critical: 4 };

export type ZoneAggregate = {
  zoneId: string;
  findings: Finding[];
  maxSeverity: Severity;
  density: number;
  center: LatLng;
};

export function aggregateByZone(findings: Finding[]): ZoneAggregate[] {
  const map = new Map<string, Finding[]>();
  for (const finding of findings) {
    const zoneId = finding.content.zone_id;
    if (!zoneId) continue;
    const list = map.get(zoneId) ?? [];
    list.push(finding);
    map.set(zoneId, list);
  }

  const aggregates: ZoneAggregate[] = [];
  for (const [zoneId, list] of map) {
    const center = zoneCenterLatLng(zoneId);
    if (!center) continue;
    let maxSeverity: Severity = "low";
    let density = 0;
    for (const finding of list) {
      if (SEVERITY_RANK[finding.severity] > SEVERITY_RANK[maxSeverity]) {
        maxSeverity = finding.severity;
      }
      density = Math.max(density, finding.content.density ?? 0);
    }
    aggregates.push({ zoneId, findings: list, maxSeverity, density, center });
  }
  return aggregates;
}

export function vehiclePositionsInBounds(vehicles: VehiclePosition[]): VehiclePosition[] {
  return vehicles.filter(
    (vehicle) =>
      vehicle.latitude >= NAPLES_BBOX.minLat &&
      vehicle.latitude <= NAPLES_BBOX.maxLat &&
      vehicle.longitude >= NAPLES_BBOX.minLon &&
      vehicle.longitude <= NAPLES_BBOX.maxLon,
  );
}

export function averageConfidence(findings: Finding[]): number {
  if (findings.length === 0) return 0;
  return findings.reduce((sum, finding) => sum + finding.confidence, 0) / findings.length;
}

export function averageDensity(findings: Finding[]): number {
  const densities = findings
    .map((finding) => finding.content.density)
    .filter((value): value is number => typeof value === "number");
  if (densities.length === 0) return 0;
  return densities.reduce((sum, value) => sum + value, 0) / densities.length;
}

export function maxCongestion(findings: Finding[]): number {
  const values = findings
    .map((finding) => finding.content.congestion)
    .filter((value): value is number => typeof value === "number");
  if (values.length === 0) return 0;
  return Math.max(...values);
}

export function zoneLabel(zoneId: string): string {
  return NAPLES_ZONES[zoneId]?.label ?? zoneId;
}
