/**
 * @purpose Segnaposto ufficiale del marchio AIoNapoli per la superficie operatore
 * @contracts nessuno
 * @tokens operator
 * @verified 2026-11-15
 */

import { operatorTokens as t } from "@/styles/design-tokens-operator";

const sizes = {
  sm: { padding: "4px 8px", fontSize: "13px" },
  md: { padding: "6px 12px", fontSize: "16px" },
  lg: { padding: "8px 16px", fontSize: "20px" },
} as const;

export function LogoPlaceholder({ size = "md" }: { size?: keyof typeof sizes }) {
  return (
    <span
      aria-label="AIoNapoli (logo provvisorio)"
      style={{
        display: "inline-block",
        border: `1px dashed ${t.color.border.strong}`,
        borderRadius: t.radius.sm,
        color: t.color.text.primary,
        fontFamily: t.font.family,
        fontWeight: t.font.weight.semibold,
        letterSpacing: "-0.01em",
        lineHeight: 1.2,
        ...sizes[size],
      }}
    >
      AIoNapoli
    </span>
  );
}
