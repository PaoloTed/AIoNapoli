/**
 * @purpose Status card recipient con icona, titolo e dettaglio in linguaggio naturale
 * @contracts nessuno
 * @tokens recipient
 * @verified 2026-11-15
 */

import { recipientTokens as t } from "@/styles/design-tokens-recipient";

export function StatusCard({
  icon,
  title,
  detail,
  tone,
}: {
  icon: string;
  title: string;
  detail: string;
  tone: "positive" | "attention" | "alert";
}) {
  const color =
    tone === "positive"
      ? t.color.severity.low
      : tone === "attention"
        ? t.color.severity.medium
        : t.color.severity.critical;

  return (
    <article
      style={{
        minWidth: "220px",
        flex: "1 1 220px",
        background: t.color.bg.elevated,
        border: `1px solid ${t.color.border.subtle}`,
        borderRadius: t.radius.lg,
        padding: t.space[4],
        boxShadow: t.shadow.soft,
        display: "grid",
        gap: t.space[1],
      }}
    >
      <span
        aria-hidden="true"
        style={{
          width: "38px",
          height: "38px",
          borderRadius: t.radius.md,
          display: "grid",
          placeItems: "center",
          background: `${color}14`,
          fontSize: "19px",
        }}
      >
        {icon}
      </span>
      <strong style={{ fontSize: t.font.size.md, color: t.color.text.primary }}>{title}</strong>
      <span style={{ fontSize: t.font.size.sm, color: t.color.text.secondary, lineHeight: t.font.lineHeight.relaxed }}>
        {detail}
      </span>
    </article>
  );
}
