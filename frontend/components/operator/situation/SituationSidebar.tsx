/**
 * @purpose Pannello laterale della scheda Situazione
 * @contracts Conflict, Finding
 * @tokens operator
 * @verified 2026-11-15
 */

"use client";

import type { Conflict, Finding } from "@/lib/types/contracts";
import { ConflictBanner } from "./ConflictBanner";
import { GaugePanel } from "./GaugePanel";
import { CriticalFindingsList } from "./CriticalFindingsList";
import { averageConfidence, averageDensity, maxCongestion } from "./geo";

export function SituationSidebar({
  findings,
  conflict,
  onFocus,
}: {
  findings: Finding[];
  conflict: Conflict | null;
  onFocus: (zoneId: string) => void;
}) {
  return (
    <div style={{ display: "grid", gap: "12px", alignContent: "start", minHeight: 0 }}>
      <ConflictBanner conflict={conflict} />
      <GaugePanel
        density={averageDensity(findings)}
        saturation={maxCongestion(findings)}
        confidence={averageConfidence(findings)}
      />
      <CriticalFindingsList findings={findings} onFocus={onFocus} />
    </div>
  );
}
