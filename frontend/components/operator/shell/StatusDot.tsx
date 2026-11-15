/**
 * @purpose Micro-indicatore dello stato della connessione SSE
 * @contracts StreamStatus
 * @tokens operator
 * @verified 2026-11-15
 */

import { operatorTokens as t } from "@/styles/design-tokens-operator";
import type { StreamStatus } from "@/lib/state/store";

const COLORS: Record<StreamStatus, string> = {
  idle: t.color.text.muted,
  connected: t.color.severity.low,
  reconnecting: t.color.severity.medium,
  disconnected: t.color.severity.critical,
};

const LABELS: Record<StreamStatus, string> = {
  idle: "In attesa",
  connected: "Stream connesso",
  reconnecting: "Riconnessione",
  disconnected: "Stream disconnesso",
};

export function StatusDot({ status }: { status: StreamStatus }) {
  return (
    <span
      title={LABELS[status]}
      aria-label={LABELS[status]}
      style={{
        display: "inline-block",
        width: "8px",
        height: "8px",
        borderRadius: "50%",
        background: COLORS[status],
        boxShadow: `0 0 0 3px ${COLORS[status]}22`,
      }}
    />
  );
}
