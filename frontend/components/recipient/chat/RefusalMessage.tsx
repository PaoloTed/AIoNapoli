/**
 * @purpose Messaggio rassicurante quando non esistono dati attendibili
 * @contracts nessuno
 * @tokens recipient
 * @verified 2026-11-15
 */

import { recipientTokens as t } from "@/styles/design-tokens-recipient";

export function RefusalMessage() {
  return (
    <div
      style={{
        background: t.color.bg.panel,
        border: `1px solid ${t.color.border.subtle}`,
        borderRadius: t.radius.lg,
        padding: t.space[3],
        fontSize: t.font.size.sm,
        color: t.color.text.secondary,
        lineHeight: t.font.lineHeight.relaxed,
      }}
    >
      Non abbiamo informazioni attendibili su questo percorso in questo momento. Prova a chiedermi dello
      stato del traffico o delle zone con meno folla.
    </div>
  );
}
