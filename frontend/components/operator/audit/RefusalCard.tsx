/**
 * @purpose Scheda di un rifiuto formale con causa e input mancanti
 * @contracts Refusal
 * @tokens operator
 * @verified 2026-11-15
 */

import { operatorTokens as t } from "@/styles/design-tokens-operator";
import { Badge } from "@/components/ui/Badge";
import type { Refusal } from "@/lib/types/contracts";

const REASON_LABEL: Record<string, string> = {
  missing_gtfs: "GTFS non disponibile",
  unmapped_point: "Punto fuori perimetro",
  out_of_horizon: "Orizzonte temporale non coperto",
  missing_realtime: "Dati realtime assenti",
  missing_occupancy: "Occupazione non disponibile",
  missing_geofence: "Geofence mancante",
  invalid_density: "Densità non valida",
  missing_alert_level: "Livello di allerta mancante",
  missing_time_window: "Finestra temporale mancante",
  unsourced_alert: "Allerta senza fonte",
  cannot_validate: "Validazione impossibile",
  unresolved_location: "Località non risolta",
};

export function RefusalCard({ refusal }: { refusal: Refusal }) {
  return (
    <article
      style={{
        background: t.color.bg.panel,
        border: `1px solid ${t.color.border.subtle}`,
        borderRadius: t.radius.md,
        padding: t.space[3],
        display: "grid",
        gap: t.space[1],
      }}
    >
      <header style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: t.space[2] }}>
        <Badge tone="neutral">{refusal.agent}</Badge>
        <code style={{ fontSize: t.font.size.xs, color: t.color.severity.medium }}>{refusal.reason_code}</code>
      </header>
      <strong style={{ fontSize: t.font.size.md, color: t.color.text.primary }}>
        {REASON_LABEL[refusal.reason_code] ?? refusal.reason_code}
      </strong>
      <p style={{ margin: 0, fontSize: t.font.size.sm, color: t.color.text.secondary }}>{refusal.detail}</p>
      <p style={{ margin: 0, fontSize: t.font.size.xs, color: t.color.text.muted }}>
        input mancanti: {refusal.missing_input.join(", ") || "—"}
      </p>
    </article>
  );
}
