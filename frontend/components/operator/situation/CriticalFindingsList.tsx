/**
 * @purpose Elenco delle criticità high/critical con click-to-focus sulla mappa
 * @contracts Finding
 * @tokens operator
 * @verified 2026-11-15
 */

"use client";

import { operatorTokens as t } from "@/styles/design-tokens-operator";
import { Badge } from "@/components/ui/Badge";
import type { Finding } from "@/lib/types/contracts";
import { formatPercent, formatRomeTime } from "@/lib/format";
import { zoneLabel } from "./geo";

export function CriticalFindingsList({
  findings,
  onFocus,
}: {
  findings: Finding[];
  onFocus: (zoneId: string) => void;
}) {
  const critical = findings
    .filter((finding) => finding.severity === "high" || finding.severity === "critical")
    .sort((a, b) => b.confidence - a.confidence);

  return (
    <section
      style={{
        background: t.color.bg.panel,
        border: `1px solid ${t.color.border.subtle}`,
        borderRadius: t.radius.md,
        padding: t.space[3],
        display: "grid",
        gap: t.space[2],
        minHeight: 0,
      }}
      aria-label="Criticità attive"
    >
      <h3 style={{ margin: 0, fontSize: t.font.size.sm, color: t.color.text.secondary, textTransform: "uppercase", letterSpacing: "0.08em" }}>
        Criticità attive
      </h3>
      <div style={{ display: "grid", gap: t.space[2], overflowY: "auto" }}>
        {critical.length === 0 ? (
          <p style={{ margin: 0, fontSize: t.font.size.base, color: t.color.text.muted }}>
            Nessuna criticità alta o critica nel campione corrente.
          </p>
        ) : null}
        {critical.map((finding) => {
          const zoneId = finding.content.zone_id;
          return (
            <button
              key={`${finding.agent}-${finding.data_reference}`}
              type="button"
              onClick={() => zoneId && onFocus(zoneId)}
              style={{
                textAlign: "left",
                background: t.color.bg.panelAlt,
                border: `1px solid ${t.color.border.subtle}`,
                borderRadius: t.radius.sm,
                padding: t.space[2],
                display: "grid",
                gap: t.space[1],
                cursor: zoneId ? "pointer" : "default",
                color: t.color.text.primary,
              }}
            >
              <span style={{ display: "flex", gap: t.space[2], alignItems: "center", flexWrap: "wrap" }}>
                <Badge tone="severity" severity={finding.severity}>
                  {finding.severity}
                </Badge>
                <Badge tone="neutral">{finding.agent}</Badge>
                <span style={{ fontSize: t.font.size.xs, color: t.color.text.muted }}>
                  {zoneId ? zoneLabel(zoneId) : "zona n/d"}
                </span>
              </span>
              <span style={{ fontSize: t.font.size.sm, color: t.color.text.secondary }}>
                {finding.content.note ?? finding.type}
              </span>
              <span style={{ fontSize: t.font.size.xs, color: t.color.text.muted }}>
                confidenza {formatPercent(finding.confidence)} · {formatRomeTime(finding.timestamp)}
              </span>
            </button>
          );
        })}
      </div>
    </section>
  );
}
