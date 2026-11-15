"use client";

import { RECIPIENT_PROFILES } from "@/lib/recipients";
import { RecipientView } from "./RecipientView";

export function TouristView({ scenarioId }: { scenarioId?: string | undefined }) {
  return <RecipientView profile={RECIPIENT_PROFILES.tourist} scenarioId={scenarioId} />;
}
