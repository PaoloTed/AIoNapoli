/**
 * @purpose Card base del Command Center con bordo e superficie tokenizzata
 * @contracts nessuno
 * @tokens operator
 * @verified 2026-11-15
 */

import type { CSSProperties, ReactNode } from "react";
import { operatorTokens as t } from "@/styles/design-tokens-operator";

export function Card({
  children,
  style,
  elevated = false,
  accent,
}: {
  children: ReactNode;
  style?: CSSProperties;
  elevated?: boolean;
  accent?: string;
}) {
  return (
    <section
      style={{
        background: elevated ? t.color.bg.elevated : t.color.bg.panel,
        border: `1px solid ${accent ?? t.color.border.subtle}`,
        borderRadius: t.radius.md,
        boxShadow: t.shadow.subtle,
        ...style,
      }}
    >
      {children}
    </section>
  );
}
