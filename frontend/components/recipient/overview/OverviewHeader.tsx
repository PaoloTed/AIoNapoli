/**
 * @purpose Intestazione contestuale dell'Overview con messaggio naturale per target
 * @contracts Finding, Target
 * @tokens recipient
 * @verified 2026-11-15
 */

"use client";

import { recipientTokens as t } from "@/styles/design-tokens-recipient";
import type { Finding, Target } from "@/lib/types/contracts";
import { NAPLES_ZONES } from "@/lib/scenarios";

const SEVERITY_RANK: Record<Finding["severity"], number> = { low: 1, medium: 2, high: 3, critical: 4 };

export function OverviewHeader({ findings, target }: { findings: Finding[]; target: Target }) {
  const accent = target === "tourist" ? t.color.accent.tourist : t.color.accent.citizen;
  const top = [...findings].sort((a, b) => SEVERITY_RANK[b.severity] - SEVERITY_RANK[a.severity])[0];
  const zoneId = top?.content.zone_id;
  const zoneName = zoneId ? (NAPLES_ZONES[zoneId]?.label ?? zoneId) : null;

  const message = (() => {
    if (!top) {
      return target === "tourist"
        ? "La città è tranquilla: è un buon momento per esplorare."
        : "Nessuna criticità attiva: la rete sta funzionando regolarmente.";
    }
    if (target === "tourist") {
      const parts = [zoneName ? `Sei nei pressi di ${zoneName}` : "Sei in città"];
      if (top.content.note) parts.push(top.content.note);
      else parts.push(`Situazione ${top.severity} rilevata dall'agente ${top.agent}`);
      parts.push("Ti consiglio un percorso alternativo lontano dalla folla.");
      return parts.join(" · ");
    }
    return (
      top.content.note ??
      `Situazione ${top.severity} su ${zoneName ?? "una zona monitorata"}: segui le indicazioni dell'assistente.`
    );
  })();

  return (
    <header style={{ display: "grid", gap: t.space[2] }}>
      <span
        style={{
          fontSize: t.font.size.xs,
          textTransform: "uppercase",
          letterSpacing: "0.12em",
          color: accent,
          fontWeight: t.font.weight.semibold,
        }}
      >
        {target === "tourist" ? "La tua visita a Napoli" : "La tua città, in tempo reale"}
      </span>
      <h1 style={{ margin: 0, fontSize: t.font.size["2xl"], lineHeight: 1.25, color: t.color.text.primary }}>
        {target === "tourist" ? "Esplora senza stress" : "Muoviti con serenità"}
      </h1>
      <p style={{ margin: 0, fontSize: t.font.size.base, color: t.color.text.secondary, lineHeight: t.font.lineHeight.relaxed }}>
        {message}
      </p>
    </header>
  );
}
