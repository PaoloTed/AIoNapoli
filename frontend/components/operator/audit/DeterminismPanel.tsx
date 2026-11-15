/**
 * @purpose Banco di prova del determinismo con riesecuzione a parità di input
 * @contracts DecisionResponse
 * @tokens operator
 * @verified 2026-11-15
 */

"use client";

import { useState } from "react";
import { operatorTokens as t } from "@/styles/design-tokens-operator";
import { computeRerunDecision } from "@/lib/state/useBootstrap";
import { useAppStore } from "@/lib/state/store";
import { Button } from "@/components/ui/Button";
import { Spinner } from "@/components/ui/Spinner";
import type { DecisionResponse } from "@/lib/types/contracts";
import { RunComparison } from "./RunComparison";

export function DeterminismPanel() {
  const { decision, scenario } = useAppStore();
  const [rerun, setRerun] = useState<DecisionResponse | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = async () => {
    if (!scenario) return;
    setRunning(true);
    setError(null);
    try {
      const result = await computeRerunDecision(scenario.scenario_id);
      setRerun(result);
    } catch {
      setError("Riesecuzione non disponibile: il backend non ha risposto.");
    } finally {
      setRunning(false);
    }
  };

  return (
    <section
      style={{
        background: t.color.bg.panel,
        border: `1px solid ${t.color.border.subtle}`,
        borderRadius: t.radius.md,
        padding: t.space[4],
        display: "grid",
        gap: t.space[3],
      }}
      aria-label="Banco di prova del determinismo"
    >
      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: t.space[2], flexWrap: "wrap" }}>
        <div>
          <h2 style={{ margin: 0, fontSize: t.font.size.lg }}>Banco di prova del determinismo</h2>
          <p style={{ margin: 0, fontSize: t.font.size.sm, color: t.color.text.secondary }}>
            A parità di input il motore deve produrre lo stesso piano, lo stesso ordine e la stessa confidenza.
          </p>
        </div>
        <Button variant="primary" onClick={() => void run()} disabled={running || !decision}>
          {running ? (
            <>
              <Spinner /> Esecuzione…
            </>
          ) : (
            "Esegui di nuovo"
          )}
        </Button>
      </header>

      {error ? <p style={{ margin: 0, color: t.color.severity.critical, fontSize: t.font.size.sm }}>{error}</p> : null}

      {decision && rerun ? <RunComparison original={decision} rerun={rerun} /> : null}
      {!rerun && !error ? (
        <p style={{ margin: 0, fontSize: t.font.size.sm, color: t.color.text.muted }}>
          La riesecuzione non è ancora stata lanciata in questa sessione.
        </p>
      ) : null}
    </section>
  );
}
