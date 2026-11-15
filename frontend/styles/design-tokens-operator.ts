/**
 * @purpose Token di design per il Command Center Operatore (Dark Mode)
 * @contracts nessuno (token grafici)
 * @tokens operator
 * @verified 2026-11-15
 */

export const operatorTokens = {
  color: {
    bg: {
      base: "#0B0F19",
      panel: "#111827",
      panelAlt: "#161F30",
      elevated: "#1F293D",
    },
    border: {
      subtle: "#1F2937",
      strong: "#374151",
      focus: "#06B6D4",
    },
    text: {
      primary: "#F9FAFB",
      secondary: "#9CA3AF",
      muted: "#6B7280",
      inverse: "#111827",
    },
    accent: {
      primary: "#06B6D4",
      hover: "#0891B2",
      muted: "rgba(6, 182, 212, 0.15)",
    },
    severity: {
      low: "#10B981",
      medium: "#F59E0B",
      high: "#F97316",
      critical: "#EF4444",
    },
    target: {
      operator: "#8B5CF6",
      tourist: "#EC4899",
      citizen: "#3B82F6",
    },
    overlay: "rgba(11, 15, 25, 0.75)",
  },
  font: {
    family: "var(--font-manrope), sans-serif",
    size: {
      xs: "11px",
      sm: "12px",
      base: "13px",
      md: "14px",
      lg: "16px",
      xl: "18px",
      "2xl": "22px",
    },
    weight: {
      regular: 400,
      medium: 500,
      semibold: 600,
      bold: 700,
    },
    lineHeight: {
      tight: 1.2,
      normal: 1.5,
      relaxed: 1.6,
    },
  },
  space: {
    0: "0px",
    1: "4px",
    2: "8px",
    3: "12px",
    4: "16px",
    6: "24px",
    8: "32px",
    12: "48px",
  },
  radius: {
    sm: "4px",
    md: "8px",
    lg: "12px",
    pill: "9999px",
  },
  shadow: {
    subtle: "0 1px 3px rgba(0, 0, 0, 0.4)",
    popover: "0 10px 25px -5px rgba(0, 0, 0, 0.7), 0 8px 10px -6px rgba(0, 0, 0, 0.7)",
  },
  transition: {
    fast: "150ms cubic-bezier(0.4, 0, 0.2, 1)",
    base: "250ms cubic-bezier(0.4, 0, 0.2, 1)",
    slow: "350ms cubic-bezier(0.4, 0, 0.2, 1)",
  },
  z: {
    base: 1,
    header: 20,
    popover: 50,
    drawer: 100,
    modal: 200,
  },
} as const;

export type SeverityKey = keyof typeof operatorTokens.color.severity;
export type TargetKey = keyof typeof operatorTokens.color.target;
