/**
 * @purpose Derivazione delle status card dalle evidenze per target
 * @contracts Finding, Target
 * @tokens recipient
 * @verified 2026-11-15
 */

import type { Finding, Target } from "@/lib/types/contracts";
import { formatPercent } from "@/lib/format";

export type StatusCardSpec = {
  icon: string;
  title: string;
  detail: string;
  tone: "positive" | "attention" | "alert";
};

function byAgent(findings: Finding[], agent: Finding["agent"]): Finding | undefined {
  return findings.find((finding) => finding.agent === agent);
}

function lineCard(findings: Finding[]): StatusCardSpec {
  const mobility = byAgent(findings, "mobility");
  if (!mobility) {
    return {
      icon: "🚇",
      title: "Linee regolari",
      detail: "Nessuna interruzione segnalata sulle linee portanti.",
      tone: "positive",
    };
  }
  const disruption = mobility.type === "route_disruption";
  const line = mobility.content.line_id ?? "linea";
  return {
    icon: "🚇",
    title: disruption ? `Linea ${line}: sospesa` : `Linea ${line}: regolare`,
    detail:
      mobility.content.note ??
      (mobility.content.estimated_time_min
        ? `Ripresa stimata in ${mobility.content.estimated_time_min} minuti.`
        : "Servizio monitorato in tempo reale."),
    tone: disruption ? "alert" : "positive",
  };
}

function crowdingCard(findings: Finding[]): StatusCardSpec {
  const crowding = byAgent(findings, "crowding");
  if (!crowding) {
    return {
      icon: "👥",
      title: "Affollamento nella norma",
      detail: "Nessun picco di presenze rilevato nelle zone monitorate.",
      tone: "positive",
    };
  }
  const density = crowding.content.density ?? 0;
  return {
    icon: "👥",
    title: density >= 0.8 ? "Zona molto affollata" : density >= 0.6 ? "Zona affollata" : "Affollamento contenuto",
    detail: crowding.content.note ?? `Saturazione attuale ${formatPercent(density)}.`,
    tone: density >= 0.8 ? "alert" : density >= 0.6 ? "attention" : "positive",
  };
}

function weatherCard(findings: Finding[]): StatusCardSpec {
  const context = findings.find(
    (finding) => finding.agent === "context" && (finding.content.heavy_rain !== undefined || finding.content.alert_level),
  );
  if (!context) {
    return {
      icon: "☀️",
      title: "Meteo stabile",
      detail: "Condizioni meteo senza impatti sulla mobilità.",
      tone: "positive",
    };
  }
  const heavy = context.content.heavy_rain === true;
  return {
    icon: heavy ? "🌧️" : "☀️",
    title: heavy ? `Allerta meteo ${context.content.alert_level ?? ""}`.trim() : "Meteo stabile",
    detail: context.content.note ?? "Condizioni meteo aggiornate dall'agente Contesto.",
    tone: heavy ? "attention" : "positive",
  };
}

function eventCard(findings: Finding[]): StatusCardSpec {
  const event = findings.find(
    (finding) => finding.agent === "context" && typeof finding.content.expected_attendance === "number",
  );
  if (!event) {
    return {
      icon: "🎉",
      title: "Nessun evento rilevante",
      detail: "Il calendario eventi non segnala grandi afflussi.",
      tone: "positive",
    };
  }
  const attendance = event.content.expected_attendance ?? 0;
  return {
    icon: "🎉",
    title: "Evento in corso",
    detail: event.content.note ?? `${attendance.toLocaleString("it-IT")} presenze attese.`,
    tone: attendance >= 8000 ? "attention" : "positive",
  };
}

export function deriveStatusCards(findings: Finding[], target: Target): StatusCardSpec[] {
  if (target === "tourist") {
    return [crowdingCard(findings), weatherCard(findings), eventCard(findings)];
  }
  return [lineCard(findings), crowdingCard(findings), weatherCard(findings)];
}
