/**
 * @purpose Segnaposto ufficiale del marchio AIoNapoli per la superficie recipient
 * @contracts nessuno
 * @tokens recipient
 * @verified 2026-11-15
 */

import { recipientTokens as t } from "@/styles/design-tokens-recipient";

const sizes = {
  sm: { padding: "4px 10px", fontSize: "14px" },
  md: { padding: "6px 14px", fontSize: "18px" },
  lg: { padding: "8px 18px", fontSize: "22px" },
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
