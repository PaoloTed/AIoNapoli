/**
 * @purpose Drawer laterale della chat operatore con retrieval locale
 * @contracts RetrievalResult
 * @tokens operator
 * @verified 2026-11-15
 */

"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { operatorTokens as t } from "@/styles/design-tokens-operator";
import { useAppStore } from "@/lib/state/store";
import { ChatInput } from "./ChatInput";
import { ChatMessage, type OperatorChatMessage } from "./ChatMessage";
import { QuickActions } from "./QuickActions";
import { operatorIntentQueries } from "./intents";
import { retrieve, type RetrievalResult } from "./retrieval";

export function ChatDrawer({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { decision, scenario, traceEvents } = useAppStore();
  const router = useRouter();
  const [messages, setMessages] = useState<OperatorChatMessage[]>([]);

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  const ask = useCallback(
    (rawQuery: string) => {
      const query = operatorIntentQueries[rawQuery as keyof typeof operatorIntentQueries] ?? rawQuery;
      const results = retrieve(query, {
        decision,
        findings: scenario?.findings ?? [],
        traceEvents,
      });
      const answer: OperatorChatMessage = results.length
        ? {
            id: `a-${Date.now()}`,
            role: "assistant",
            text: `Ho trovato ${results.length} riferimenti verificabili nello scenario corrente.`,
            citations: results,
          }
        : {
            id: `a-${Date.now()}`,
            role: "assistant",
            text:
              "Non ho trovato riferimenti a questa richiesta nei dati correnti. Prova a chiedere del piano, degli scarti di negoziazione o delle evidenze critiche.",
          };
      setMessages((prev) => [
        ...prev,
        { id: `u-${Date.now()}`, role: "user", text: rawQuery },
        answer,
      ]);
    },
    [decision, scenario, traceEvents],
  );

  const navigate = useCallback(
    (result: RetrievalResult) => {
      onClose();
      const target =
        result.type === "finding"
          ? "/operator/situation"
          : result.type === "trace"
            ? "/operator/discard"
            : "/operator/decision";
      router.push(`${target}#${result.ref}`);
    },
    [onClose, router],
  );

  if (!open) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Chat operativa"
      style={{ position: "fixed", inset: 0, zIndex: t.z.drawer, display: "flex", justifyContent: "flex-end" }}
    >
      <button
        type="button"
        aria-label="Chiudi chat"
        onClick={onClose}
        style={{ position: "absolute", inset: 0, background: t.color.overlay, border: "none" }}
      />
      <aside
        style={{
          position: "relative",
          width: "400px",
          maxWidth: "100vw",
          height: "100%",
          background: t.color.bg.panel,
          borderLeft: `1px solid ${t.color.border.strong}`,
          boxShadow: t.shadow.popover,
          display: "flex",
          flexDirection: "column",
          padding: t.space[4],
          gap: t.space[4],
        }}
      >
        <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <div>
            <strong style={{ fontSize: t.font.size.lg }}>Chat operativa</strong>
            <p style={{ margin: 0, fontSize: t.font.size.xs, color: t.color.text.muted }}>
              citation-grounded · nessuna generazione libera
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            aria-label="Chiudi"
            style={{
              background: "transparent",
              border: `1px solid ${t.color.border.strong}`,
              color: t.color.text.secondary,
              borderRadius: t.radius.sm,
              padding: `${t.space[1]} ${t.space[2]}`,
              cursor: "pointer",
            }}
          >
            ✕
          </button>
        </header>

        <div style={{ flex: 1, overflowY: "auto", display: "grid", gap: t.space[3], alignContent: "start" }}>
          {messages.length === 0 ? (
            <p style={{ margin: 0, fontSize: t.font.size.base, color: t.color.text.secondary }}>
              Chiedi perché è stato scelto questo piano, cosa è stato scartato nella negoziazione o quali
              evidenze sono critiche. Ogni risposta cita un record dello scenario.
            </p>
          ) : null}
          {messages.map((message) => (
            <ChatMessage key={message.id} message={message} onNavigate={navigate} />
          ))}
        </div>

        <QuickActions onSelect={ask} />
        <ChatInput onSend={ask} />
      </aside>
    </div>
  );
}
