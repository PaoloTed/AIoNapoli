import type { Locale } from "./format";

export type RecipientTarget = "tourist" | "citizen";

export type RecipientProfile = {
  target: RecipientTarget;
  basePath: "/tourist" | "/citizen";
  defaultLocale: Locale;
  showLanguageSwitcher: boolean;
  question: string;
  maxActionsVisible?: number;
  showZoneStatus: boolean;
  dictKey: "tourist" | "citizen";
};

export const RECIPIENT_PROFILES: Record<RecipientTarget, RecipientProfile> = {
  tourist: {
    target: "tourist",
    basePath: "/tourist",
    defaultLocale: "it",
    showLanguageSwitcher: true,
    question: "come arrivo?",
    maxActionsVisible: 3,
    showZoneStatus: false,
    dictKey: "tourist",
  },
  citizen: {
    target: "citizen",
    basePath: "/citizen",
    defaultLocale: "it",
    showLanguageSwitcher: false,
    question: "quale servizio prendo?",
    showZoneStatus: true,
    dictKey: "citizen",
  },
};
