/**
 * @purpose Popover di dettaglio delle evidenze di una zona
 * @contracts Finding
 * @tokens operator
 * @verified 2026-11-15
 */

import { operatorTokens as t } from "@/styles/design-tokens-operator";
import { Badge } from "@/components/ui/Badge";
import type { Finding } from "@/lib/types/contracts";
import { formatPercent, formatRomeTime } from "@/lib/format";
import { zoneLabel } from "./geo";

export function MapPopover({ zoneId, findings, onClose }: { zoneId: string; findings: Finding[]; onClose: () => void }) {
  return (
    <aside
      style={{
        position: "absolute",
        top: t.space[4],
        right: t.space[4],
        zIndex: 4,
        pointerEvents: "auto",
        width: "300px",
        maxHeight: "calc(100% - 32px)",
        overflowY: "auto",
        background: t.color.bg.elevated,
        border: `1px solid ${t.color.border.strong}`,
        borderRadius: t.radius.md,
        boxShadow: t.shadow.popover,
        padding: t.space[3],
        display: "grid",
        gap: t.space[3],
      }}
    >
      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <strong style={{ fontSize: t.font.size.md }}>{zoneLabel(zoneId)}</strong>
        <button
          type="button"
          onClick={onClose}
          aria-label="Chiudi dettaglio"
          style={{ background: "transparent", border: "none", color: t.color.text.muted, cursor: "pointer" }}
        >
          ✕
        </button>
      </header>

      {findings.map((finding) => (
        <article
          key={`${finding.agent}-${finding.data_reference}`}
          style={{ borderTop: `1px solid ${t.color.border.subtle}`, paddingTop: t.space[2], display: "grid", gap: t.space[1] }}
        >
          <div style={{ display: "flex", gap: t.space[2], flexWrap: "wrap" }}>
            <Badge tone="severity" severity={finding.severity}>
              {finding.severity}
            </Badge>
            <Badge tone="neutral">{finding.agent}</Badge>
            {finding.is_simulated ? <Badge tone="simulated">simulato</Badge> : null}
          </div>
          <p style={{ margin: 0, fontSize: t.font.size.sm, color: t.color.text.primary }}>
            {finding.content.note ?? finding.type}
          </p>
          <p style={{ margin: 0, fontSize: t.font.size.xs, color: t.color.text.muted }}>
            confidenza {formatPercent(finding.confidence)} · {formatRomeTime(finding.timestamp)}
          </p>
          <code style={{ fontSize: t.font.size.xs, color: t.color.text.muted }}>{finding.data_reference}</code>
        </article>
      ))}
    </aside>
  );
}
