/**
 * @purpose Barra superiore compatta con sezione attiva, scenario e stato stream
 * @contracts ScenarioSnapshot, DecisionResponse
 * @tokens operator
 * @verified 2026-11-15
 */

"use client";

import { usePathname } from "next/navigation";
import { operatorTokens as t } from "@/styles/design-tokens-operator";
import { useAppStore } from "@/lib/state/store";
import { formatRomeTime } from "@/lib/format";
import { StatusDot } from "./StatusDot";

const TITLES: Record<string, string> = {
  "/operator/situation": "Situazione",
  "/operator/decision": "Decisione",
  "/operator/discard": "Scarti e Negoziazione",
  "/operator/audit": "Audit e Determinismo",
};

export function Header({ onOpenChat }: { onOpenChat: () => void }) {
  const pathname = usePathname();
  const { scenario, decision, streamStatus, isSimulated } = useAppStore();
  const title = (pathname && TITLES[pathname]) ?? "Command Center";
  const lastUpdate = decision?.decision.timestamp ?? scenario?.findings[0]?.timestamp;

  return (
    <header
      style={{
        height: "60px",
        flexShrink: 0,
        borderBottom: `1px solid ${t.color.border.subtle}`,
        background: t.color.bg.panel,
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: `0 ${t.space[6]}`,
        gap: t.space[4],
      }}
    >
      <div style={{ display: "flex", alignItems: "baseline", gap: t.space[3] }}>
        <h1 style={{ margin: 0, fontSize: t.font.size.xl, fontWeight: t.font.weight.semibold }}>
          {title}
        </h1>
        <code
          style={{
            fontSize: t.font.size.sm,
            color: t.color.accent.primary,
            background: t.color.accent.muted,
            borderRadius: t.radius.sm,
            padding: "2px 6px",
          }}
        >
          {scenario?.scenario_id ?? "—"}
        </code>
      </div>

      <div style={{ display: "flex", alignItems: "center", gap: t.space[4] }}>
        <span
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: t.space[2],
            fontSize: t.font.size.sm,
            color: t.color.text.secondary,
          }}
        >
          <StatusDot status={streamStatus} />
          {streamStatus === "connected"
            ? "Live"
            : streamStatus === "reconnecting"
              ? "Riconnessione"
              : streamStatus === "disconnected"
                ? "Offline"
                : "Pronto"}
        </span>

        {isSimulated ? (
          <span style={{ fontSize: t.font.size.xs, color: t.color.severity.medium }}>
            dati simulati
          </span>
        ) : null}

        <span style={{ fontSize: t.font.size.sm, color: t.color.text.muted }}>
          agg. {lastUpdate ? formatRomeTime(lastUpdate) : "—"}
        </span>

        <button
          type="button"
          onClick={onOpenChat}
          aria-label="Apri chat operativa"
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: t.space[2],
            padding: `${t.space[2]} ${t.space[3]}`,
            borderRadius: t.radius.sm,
            border: `1px solid ${t.color.accent.primary}55`,
            background: t.color.accent.muted,
            color: t.color.accent.primary,
            fontSize: t.font.size.sm,
            fontWeight: t.font.weight.semibold,
            cursor: "pointer",
          }}
        >
          ✦ Chiedi
        </button>
      </div>
    </header>
  );
}
