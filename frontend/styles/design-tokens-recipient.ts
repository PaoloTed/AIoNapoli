/**
 * @purpose Token grafici per la superficie Recipient (Cittadino e Turista - Light Mode)
 * @contracts nessuno (token grafici)
 * @tokens recipient
 * @verified 2026-11-15
 */

export const recipientTokens = {
  color: {
    bg: {
      base: "#FFFFFF",
      panel: "#F8FAFC",
      elevated: "#FFFFFF",
    },
    border: {
      subtle: "#E2E8F0",
      strong: "#CBD5E1",
      focus: "#0EA5E9",
    },
    text: {
      primary: "#0F172A",
      secondary: "#475569",
      muted: "#94A3B8",
      inverse: "#FFFFFF",
    },
    accent: {
      citizen: "#0284C7",
      citizenLight: "#E0F2FE",
      tourist: "#EA580C",
      touristLight: "#FFEDD5",
    },
    severity: {
      low: "#059669",
      medium: "#D97706",
      high: "#EA580C",
      critical: "#DC2626",
    },
  },
  font: {
    family: "var(--font-recipient), sans-serif",
    size: {
      xs: "12px",
      sm: "14px",
      base: "15px",
      md: "16px",
      lg: "18px",
      xl: "22px",
      "2xl": "28px",
    },
    weight: {
      regular: 400,
      medium: 500,
      semibold: 600,
      bold: 700,
    },
    lineHeight: {
      normal: 1.5,
      relaxed: 1.65,
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
    sm: "8px",
    md: "12px",
    lg: "18px",
    pill: "9999px",
  },
  shadow: {
    soft: "0 4px 20px -2px rgba(15, 23, 42, 0.06), 0 2px 6px -1px rgba(15, 23, 42, 0.03)",
    elevated: "0 10px 30px -4px rgba(15, 23, 42, 0.10)",
  },
} as const;

export type RecipientAccent = "citizen" | "tourist";
