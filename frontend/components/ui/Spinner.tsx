/**
 * @purpose Indicatore di caricamento compatto
 * @contracts nessuno
 * @tokens operator
 * @verified 2026-11-15
 */

import { operatorTokens as t } from "@/styles/design-tokens-operator";

export function Spinner({ label = "Caricamento" }: { label?: string }) {
  return (
    <span
      role="status"
      aria-label={label}
      style={{
        display: "inline-block",
        width: "16px",
        height: "16px",
        borderRadius: "50%",
        border: `2px solid ${t.color.border.strong}`,
        borderTopColor: t.color.accent.primary,
        animation: "spin 0.9s linear infinite",
      }}
    />
  );
}
