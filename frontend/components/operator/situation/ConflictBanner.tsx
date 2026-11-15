/**
 * @purpose Banner di conflitto tra agenti rilevato dall'orchestratore
 * @contracts Conflict
 * @tokens operator
 * @verified 2026-11-15
 */

import { operatorTokens as t } from "@/styles/design-tokens-operator";
import type { Conflict } from "@/lib/types/contracts";

export function ConflictBanner({ conflict }: { conflict: Conflict | null }) {
  const detected = conflict?.detected ?? false;
  const color = detected ? t.color.severity.critical : t.color.severity.low;

  return (
    <div
      role={detected ? "alert" : "status"}
      style={{
        border: `1px solid ${color}66`,
        background: `${color}14`,
        borderRadius: t.radius.md,
        padding: t.space[3],
        display: "grid",
        gap: t.space[1],
      }}
    >
      <span
        style={{
          fontSize: t.font.size.xs,
          textTransform: "uppercase",
          letterSpacing: "0.1em",
          color,
          fontWeight: t.font.weight.semibold,
        }}
      >
        {detected ? "Conflitto rilevato" : "Nessun conflitto"}
      </span>
      <p style={{ margin: 0, fontSize: t.font.size.base, color: t.color.text.primary }}>
        {conflict?.description ?? "Tutte le evidenze sono coerenti: piano di monitoraggio attivo."}
      </p>
    </div>
  );
}
