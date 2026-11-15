/**
 * @purpose Barra persistente che segnala la provenienza simulata dei dati
 * @contracts nessuno
 * @tokens operator
 * @verified 2026-11-15
 */

import { operatorTokens as t } from "@/styles/design-tokens-operator";

export function MockBanner() {
  return (
    <div
      role="status"
      style={{
        background: `${t.color.severity.medium}1A`,
        borderBottom: `1px solid ${t.color.severity.medium}55`,
        color: t.color.severity.medium,
        fontSize: t.font.size.sm,
        fontWeight: t.font.weight.medium,
        padding: `${t.space[1]} ${t.space[6]}`,
        display: "flex",
        alignItems: "center",
        gap: t.space[2],
        flexShrink: 0,
      }}
    >
      <span aria-hidden="true">◇</span>
      Modalità simulazione: il backend non è raggiungibile, i dati provengono dal dataset mock locale.
    </div>
  );
}
