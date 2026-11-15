/**
 * @purpose Badge tipizzato per severità, target e stato simulato
 * @contracts Severity, Target
 * @tokens operator
 * @verified 2026-11-15
 */

import type { CSSProperties, ReactNode } from "react";
import { operatorTokens as t } from "@/styles/design-tokens-operator";
import type { Severity, Target } from "@/lib/types/contracts";

type Tone = "severity" | "target" | "simulated" | "neutral" | "accent";

function resolveColors(tone: Tone, severity?: Severity, target?: Target): { fg: string; bg: string; border: string } {
  switch (tone) {
    case "severity": {
      const color = t.color.severity[severity ?? "low"];
      return { fg: color, bg: `${color}22`, border: `${color}55` };
    }
    case "target": {
      const color = t.color.target[target ?? "operator"];
      return { fg: color, bg: `${color}22`, border: `${color}55` };
    }
    case "simulated":
      return { fg: t.color.severity.medium, bg: `${t.color.severity.medium}1A`, border: `${t.color.severity.medium}66` };
    case "accent":
      return { fg: t.color.accent.primary, bg: t.color.accent.muted, border: `${t.color.accent.primary}55` };
    default:
      return { fg: t.color.text.secondary, bg: t.color.bg.panelAlt, border: t.color.border.subtle };
  }
}

export function Badge({
  tone,
  severity,
  target,
  children,
}: {
  tone: Tone;
  severity?: Severity;
  target?: Target;
  children: ReactNode;
}) {
  const colors = resolveColors(tone, severity, target);
  const style: CSSProperties = {
    display: "inline-flex",
    alignItems: "center",
    gap: t.space[1],
    padding: `2px ${t.space[2]}`,
    borderRadius: t.radius.pill,
    border: `1px solid ${colors.border}`,
    background: colors.bg,
    color: colors.fg,
    fontSize: t.font.size.xs,
    fontWeight: t.font.weight.semibold,
    letterSpacing: "0.04em",
    textTransform: "uppercase",
    whiteSpace: "nowrap",
  };
  return <span style={style}>{children}</span>;
}
