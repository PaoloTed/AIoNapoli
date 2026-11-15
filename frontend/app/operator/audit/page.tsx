/**
 * @purpose Scheda Audit: metadati, determinismo e registro dei rifiuti formali
 * @contracts DecisionResponse, Refusal
 * @tokens operator
 * @verified 2026-11-15
 */

"use client";

import { useAppStore } from "@/lib/state/store";
import { mockRefusals } from "@/lib/api/mocks";
import { operatorTokens as t } from "@/styles/design-tokens-operator";
import { DecisionMeta } from "@/components/operator/decision/DecisionMeta";
import { DeterminismPanel } from "@/components/operator/audit/DeterminismPanel";
import { RefusalCard } from "@/components/operator/audit/RefusalCard";
import { EmptyState } from "@/components/ui/EmptyState";
import { formatRomeDateTime } from "@/lib/format";

export default function AuditPage() {
  const { decision } = useAppStore();

  if (!decision) {
    return (
      <EmptyState
        title="Nessuna decisione da verificare"
        description="Il registro di audit si popola quando il motore produce una decisione."
      />
    );
  }

  return (
    <div style={{ display: "grid", gap: "16px", maxWidth: "1080px" }}>
      <section style={{ display: "grid", gap: t.space[2] }}>
        <h2 style={{ margin: 0, fontSize: t.font.size.xl }}>Metadati della decisione</h2>
        <DecisionMeta payload={decision} />
        <p style={{ margin: 0, fontSize: t.font.size.sm, color: t.color.text.secondary }}>
          Regola dominante <code>{decision.decision.trigger.rule_id}</code> · agenti coinvolti{" "}
          {decision.decision.trigger.agents_involved.join(", ")} · prodotta il{" "}
          {formatRomeDateTime(decision.decision.timestamp)}
        </p>
      </section>

      <DeterminismPanel />

      <section style={{ display: "grid", gap: t.space[2] }}>
        <h2 style={{ margin: 0, fontSize: t.font.size.xl }}>Registro dei rifiuti formali</h2>
        <p style={{ margin: 0, fontSize: t.font.size.sm, color: t.color.text.secondary }}>
          Esempi di refusal dichiarati dal contratto: il sistema espone il rifiuto come esito, non come guasto.
        </p>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(280px, 1fr))", gap: t.space[3] }}>
          {mockRefusals.map((refusal) => (
            <RefusalCard key={`${refusal.agent}-${refusal.reason_code}`} refusal={refusal} />
          ))}
        </div>
      </section>
    </div>
  );
}
