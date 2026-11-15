/**
 * @purpose Visualizzatore di ProblemDetail RFC 7807 senza stack trace
 * @contracts ProblemDetail
 * @tokens operator
 * @verified 2026-11-15
 */

import type { ProblemDetail } from "@/lib/types/contracts";
import { operatorTokens as t } from "@/styles/design-tokens-operator";

export function ErrorState({ problem, onRetry }: { problem: ProblemDetail; onRetry?: () => void }) {
  return (
    <div
      role="alert"
      style={{
        border: `1px solid ${t.color.severity.critical}66`,
        background: `${t.color.severity.critical}14`,
        borderRadius: t.radius.md,
        padding: t.space[4],
        display: "flex",
        flexDirection: "column",
        gap: t.space[2],
      }}
    >
      <strong style={{ color: t.color.severity.critical, fontSize: t.font.size.md }}>
        {problem.title} · <code>{problem.code}</code>
      </strong>
      <p style={{ margin: 0, color: t.color.text.secondary, fontSize: t.font.size.base }}>
        {problem.detail}
      </p>
      {problem.refusal ? (
        <p style={{ margin: 0, color: t.color.text.muted, fontSize: t.font.size.sm }}>
          Rifiuto: {problem.refusal.reason_code} — {problem.refusal.detail}
        </p>
      ) : null}
      {onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          style={{
            alignSelf: "flex-start",
            background: "transparent",
            border: `1px solid ${t.color.border.strong}`,
            color: t.color.text.primary,
            padding: `${t.space[1]} ${t.space[3]}`,
            borderRadius: t.radius.sm,
            cursor: "pointer",
          }}
        >
          Riprova
        </button>
      ) : null}
    </div>
  );
}
