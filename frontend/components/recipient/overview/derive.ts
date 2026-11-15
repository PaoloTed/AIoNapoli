/**
 * @purpose Derivazione delle status card dalle evidenze per target
 * @contracts Finding, Target
 * @tokens recipient
 * @verified 2026-11-15
 */

import type { Finding, Target } from "@/lib/types/contracts";
import { formatPercent } from "@/lib/format";
import { NAPLES_ZONES } from "@/lib/scenarios";

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
  const zoneId = crowding.content.zone_id;
  const zoneName = zoneId ? (NAPLES_ZONES[zoneId]?.label ?? zoneId) : undefined;
  const note = crowding.content.note;
  const attendance = crowding.content.expected_attendance;

  const title =
    density >= 0.8
      ? `${zoneName ? `${zoneName}: ` : ""}zona molto affollata`
      : density >= 0.6
        ? `${zoneName ? `${zoneName}: ` : ""}zona affollata`
        : `Affollamento contenuto${zoneName ? ` a ${zoneName}` : ""}`;

  const reasons: string[] = [];
  if (note) reasons.push(note);
  if (!note?.includes("%")) reasons.push(`saturazione ${formatPercent(density)}`);
  if (typeof attendance === "number") {
    reasons.push(`${attendance.toLocaleString("it-IT")} presenze attese`);
  }
  if (reasons.length === 0) reasons.push(`Saturazione attuale ${formatPercent(density)}.`);

  return {
    icon: "👥",
    title,
    detail: reasons.join(" · "),
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
    detail: heavy
      ? "Pioggia intensa prevista: porta l'ombrello e valuta un percorso al coperto."
      : "Condizioni meteo serene per muoversi in città.",
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
