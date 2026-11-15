/**
 * @purpose Scheda Situazione: mappa operativa e pannello criticità
 * @contracts ScenarioSnapshot, DecisionResponse
 * @tokens operator
 * @verified 2026-11-15
 */

"use client";

import { useState } from "react";
import { useAppStore } from "@/lib/state/store";
import { MapPanel } from "@/components/operator/situation/MapPanel";
import { SituationSidebar } from "@/components/operator/situation/SituationSidebar";
import { EmptyState } from "@/components/ui/EmptyState";
import { LiveNewsPanel } from "@/components/operator/situation/LiveNewsPanel";

export default function SituationPage() {
  const { scenario, decision } = useAppStore();
  const [selectedZone, setSelectedZone] = useState<string | null>(null);
  const findings = scenario?.findings ?? [];
  const vehicles = scenario?.vehicle_positions ?? [];

  return (
    <><LiveNewsPanel /><div className="operator-grid-situation" style={{ minHeight: "calc(100vh - 92px)" }}>
      <MapPanel
        findings={findings}
        vehicles={vehicles}
        selectedZone={selectedZone}
        onMarkerClick={setSelectedZone}
        onClosePopover={() => setSelectedZone(null)}
      />
      {findings.length > 0 ? (
        <SituationSidebar
          findings={findings}
          conflict={decision?.decision.conflict ?? null}
          onFocus={setSelectedZone}
        />
      ) : (
        <EmptyState
          title="Nessuna evidenza"
          description="Lo scenario non espone ancora finding: attendi il bootstrap o verifica la sorgente dati."
        />
      )}
    </div></>
  );
}
