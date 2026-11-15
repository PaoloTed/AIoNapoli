/**
 * @purpose Bottone con varianti primary, secondary e ghost
 * @contracts nessuno
 * @tokens operator
 * @verified 2026-11-15
 */

"use client";

import type { ButtonHTMLAttributes, CSSProperties } from "react";
import { operatorTokens as t } from "@/styles/design-tokens-operator";

type Variant = "primary" | "secondary" | "ghost";

const variants: Record<Variant, CSSProperties> = {
  primary: {
    background: t.color.accent.primary,
    color: t.color.text.inverse,
    border: `1px solid ${t.color.accent.primary}`,
  },
  secondary: {
    background: t.color.bg.panelAlt,
    color: t.color.text.primary,
    border: `1px solid ${t.color.border.strong}`,
  },
  ghost: {
    background: "transparent",
    color: t.color.text.secondary,
    border: `1px solid transparent`,
  },
};

export function Button({
  variant = "secondary",
  style,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant }) {
  return (
    <button
      type="button"
      {...props}
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: t.space[2],
        padding: `${t.space[2]} ${t.space[3]}`,
        borderRadius: t.radius.sm,
        fontSize: t.font.size.sm,
        fontWeight: t.font.weight.semibold,
        cursor: props.disabled ? "not-allowed" : "pointer",
        opacity: props.disabled ? 0.55 : 1,
        transition: `background ${t.transition.fast}, border-color ${t.transition.fast}`,
        ...variants[variant],
        ...style,
      }}
    />
  );
}
