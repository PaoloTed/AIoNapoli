export type ZonePolygonSpec = {
  zone_id: string;
  label: string;
  center: [number, number]; // [lng, lat]
  polygon: [number, number][]; // GeoJSON outer ring [lng, lat]
};

// Curated operational zone polygons matching D-06 (Z_<NAME>)
export const NAPLES_ZONES: Record<string, ZonePolygonSpec> = {
  Z_BAGNOLI: {
    zone_id: "Z_BAGNOLI",
    label: "Bagnoli",
    center: [14.172, 40.816],
    polygon: [
      [14.158, 40.808],
      [14.186, 40.808],
      [14.186, 40.824],
      [14.158, 40.824],
      [14.158, 40.808],
    ],
  },
  Z_FUORIGROTTA: {
    zone_id: "Z_FUORIGROTTA",
    label: "Fuorigrotta",
    center: [14.193, 40.827],
    polygon: [
      [14.182, 40.82],
      [14.205, 40.82],
      [14.205, 40.834],
      [14.182, 40.834],
      [14.182, 40.82],
    ],
  },
  Z_MERGELLINA: {
    zone_id: "Z_MERGELLINA",
    label: "Mergellina",
    center: [14.219, 40.829],
    polygon: [
      [14.211, 40.824],
      [14.228, 40.824],
      [14.228, 40.834],
      [14.211, 40.834],
      [14.211, 40.824],
    ],
  },
  Z_MUNICIPIO: {
    zone_id: "Z_MUNICIPIO",
    label: "Municipio / Beverello",
    center: [14.253, 40.84],
    polygon: [
      [14.246, 40.835],
      [14.261, 40.835],
      [14.261, 40.845],
      [14.246, 40.845],
      [14.246, 40.835],
    ],
  },
  Z_CENTRO: {
    zone_id: "Z_CENTRO",
    label: "Centro Storico",
    center: [14.256, 40.85],
    polygon: [
      [14.248, 40.845],
      [14.265, 40.845],
      [14.265, 40.855],
      [14.248, 40.855],
      [14.248, 40.845],
    ],
  },
  Z_GARIBALDI: {
    zone_id: "Z_GARIBALDI",
    label: "Piazza Garibaldi",
    center: [14.272, 40.853],
    polygon: [
      [14.266, 40.848],
      [14.279, 40.848],
      [14.279, 40.858],
      [14.266, 40.858],
      [14.266, 40.848],
    ],
  },
};

export const NAPLES_DEFAULT_CENTER: [number, number] = [14.215, 40.835];

// Closed scenario list configured via NEXT_PUBLIC_DEMO_SCENARIO (API.md §1.2, SCREENS.md §2)
export function getConfiguredScenarios(): string[] {
  const raw = process.env.NEXT_PUBLIC_DEMO_SCENARIO ?? "bagnoli";
  const parsed = raw
    .split(",")
    .map((s) => s.trim())
    .filter((s) => s.length > 0);
  return parsed.length > 0 ? Array.from(new Set(parsed)) : ["bagnoli"];
}

export function getDefaultScenarioId(): string {
  return getConfiguredScenarios()[0] ?? "bagnoli";
}
