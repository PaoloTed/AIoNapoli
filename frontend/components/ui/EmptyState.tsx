/**
 * @purpose Stato vuoto operator con messaggio e azione opzionale
 * @contracts nessuno
 * @tokens operator
 * @verified 2026-11-15
 */

import type { ReactNode } from "react";
import { operatorTokens as t } from "@/styles/design-tokens-operator";

export function EmptyState({
  title,
  description,
  action,
  icon = "◎",
}: {
  title: string;
  description: string;
  action?: ReactNode;
  icon?: string;
}) {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: t.space[3],
        padding: `${t.space[12]} ${t.space[6]}`,
        textAlign: "center",
        color: t.color.text.secondary,
      }}
    >
      <span style={{ fontSize: "32px", color: t.color.accent.primary }} aria-hidden="true">
        {icon}
      </span>
      <strong style={{ color: t.color.text.primary, fontSize: t.font.size.lg }}>{title}</strong>
      <p style={{ margin: 0, maxWidth: "420px", fontSize: t.font.size.base }}>{description}</p>
      {action}
    </div>
  );
}
