import type { DecisionResponse, ScenarioResponse } from "@/lib/contracts";

export const SAMPLE_SCENARIO: ScenarioResponse = {
  contract_version: "1.0.0",
  scenario_id: "bagnoli",
  title: "Regata America's Cup, Linea 2 ferma, pioggia in arrivo",
  findings: [
    {
      agent: "mobility",
      type: "route_disruption",
      content: { zone_id: "Z_BAGNOLI", congestion: 0.88 },
      confidence: 0.9,
      severity: "high",
      source_id: "anm",
      data_reference: "rss:2026-11-14T16:12:00+01:00",
      is_simulated: false,
      timestamp: "2026-11-14T16:12:00+01:00",
    },
    {
      agent: "crowding",
      type: "density_alert",
      content: { density: 0.91, zone_id: "Z_BAGNOLI" },
      confidence: 0.82,
      severity: "high",
      source_id: "ir_sensors",
      data_reference: "occupancy:2026-11-14T17:40:00+01:00",
      is_simulated: true,
      timestamp: "2026-11-14T17:40:00+01:00",
    },
    {
      agent: "context",
      type: "impact_assessment",
      content: { heavy_rain: true, expected_attendance: 12000, zone_id: "Z_BAGNOLI" },
      confidence: 0.75,
      severity: "medium",
      source_id: "open_meteo",
      data_reference: "weather:2026-11-14T17:00:00+01:00",
      is_simulated: true,
      timestamp: "2026-11-14T17:00:00+01:00",
    },
  ],
  vehicle_positions: [
    {
      vehicle_id: "ANM-2231",
      route_id: "R2",
      latitude: 40.8206,
      longitude: 14.1785,
      bearing: 214.5,
      observed_at: "2026-11-14T17:39:48+01:00",
      source_id: "anm",
      is_simulated: false,
    },
  ],
};

export const SAMPLE_DECISION: DecisionResponse = {
  contract_version: "1.0.0",
  decision_id: "3f9a51c7e2b84d06",
  decision: {
    trigger: {
      rule_id: "R1_line2_crowding",
      agents_involved: ["mobility", "crowding"],
    },
    conflict: {
      detected: true,
      description: "Il percorso verso Z_BAGNOLI attraversa la zona satura rilevata da crowding",
    },
    plan: [
      {
        priority: 1,
        action: "Percorso via bus di superficie con priorita' 1 per sicurezza",
        target: "operator",
        rationale:
          "P1 sicurezza delle persone; densita' 0.91 oltre soglia 0.85 (R1_line2_crowding)",
      },
      {
        priority: 1,
        action: "Alternativa: linea R2 da Fuorigrotta, tempo stimato 20 min",
        target: "tourist",
        rationale:
          "P2 tempo di percorrenza; percorso alternativo citato in R2_conflict_route_vs_density",
      },
      {
        priority: 1,
        action: "Raggiungi il servizio pubblico in 15 min via percorso A",
        target: "citizen",
        rationale: "P3 esperienza; servizio pubblico nella stessa zona",
      },
    ],
    reasoning_log: [
      {
        step: 1,
        agent: "crowding",
        finding_ref: "7b1e9c04a2d5",
        rule_applied: "R1_line2_crowding",
        outcome: "densita' 0.91 oltre la soglia 0.85, regola scattata",
      },
      {
        step: 2,
        agent: "mobility",
        finding_ref: "c4d8a0f31b6e",
        rule_applied: "R2_conflict_route_vs_density",
        outcome: "percorso e zona satura coincidono su Z_BAGNOLI",
      },
      {
        step: 3,
        agent: "orchestrator",
        finding_ref: "7b1e9c04a2d5",
        rule_applied: "P1",
        outcome: "priorita' sicurezza applicata, percorso diretto scartato",
      },
    ],
    confidence: 0.86,
    timestamp: "2026-11-14T17:41:12+01:00",
  },
  relevance: {
    rounding: 4,
    targets: {
      operator: {
        order: [0],
        items: [
          {
            plan_index: 0,
            score: 0.9312,
            contributions: [
              { feature: "severity_score", value: 1.0, weight: 0.4, contribution: 0.4 },
              { feature: "confidence", value: 0.86, weight: 0.2, contribution: 0.172 },
              { feature: "affects_public_service", value: 1, weight: 0.2, contribution: 0.2 },
              { feature: "priority_rank", value: 1.0, weight: 0.2, contribution: 0.2 },
            ],
          },
        ],
      },
      tourist: {
        order: [1],
        items: [
          {
            plan_index: 1,
            score: 0.84,
            contributions: [
              { feature: "affects_route", value: 1, weight: 0.5, contribution: 0.5 },
              { feature: "severity_score", value: 0.85, weight: 0.4, contribution: 0.34 },
            ],
          },
        ],
      },
      citizen: {
        order: [2],
        items: [
          {
            plan_index: 2,
            score: 0.78,
            contributions: [
              { feature: "affects_public_service", value: 1, weight: 0.6, contribution: 0.6 },
              { feature: "confidence", value: 0.9, weight: 0.2, contribution: 0.18 },
            ],
          },
        ],
      },
    },
  },
  narrative: {
    mode: "replay",
    items: [
      {
        plan_index: 1,
        texts: {
          it: "Linea R2 da Fuorigrotta, circa 20 minuti.",
          en: "Line R2 from Fuorigrotta, about 20 minutes.",
        },
      },
    ],
  },
};
