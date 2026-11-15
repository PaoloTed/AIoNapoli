/**
 * @purpose Contenitore conversazione recipient con quick actions e input
 * @contracts DecisionResponse, Target
 * @tokens recipient
 * @verified 2026-11-15
 */

"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { recipientTokens as t } from "@/styles/design-tokens-recipient";
import { useAppStore } from "@/lib/state/store";
import { BrandLogo } from "@/components/brand/BrandLogo";
import type { Target } from "@/lib/types/contracts";
import { ChatMessage, type RecipientChatMessage } from "./ChatMessage";
import { ChatInput } from "./ChatInput";
import { QuickActions } from "./QuickActions";
import { retrieve } from "./retrieval";
import { buildDemoMessages } from "./demoScripts";
import { isMockMode } from "@/lib/api/mockMode";
import { LiveJourneyChat } from "./LiveJourneyChat";

export function ChatPanel({ target, onClose }: { target: Target; onClose?: () => void }) {
  const props = onClose ? { target, onClose } : { target };
  return isMockMode() ? <DemoChatPanel {...props} /> : <LiveJourneyChat {...props} />;
}

function DemoChatPanel({ target, onClose }: { target: Target; onClose?: () => void }) {
  const { decision, lang, demoRequest } = useAppStore();
  const [messages, setMessages] = useState<RecipientChatMessage[]>([]);
  const counter = useRef(0);
  const decisionRef = useRef(decision);
  const scrollRef = useRef<HTMLDivElement>(null);

  decisionRef.current = decision;

  useEffect(() => {
    if (!demoRequest || demoRequest.target !== target) return;

    const demoTarget: "citizen" | "tourist" = demoRequest.target === "tourist" ? "tourist" : "citizen";
    const script = buildDemoMessages(demoTarget, decisionRef.current, lang);
    setMessages([]);
    const timers: Array<ReturnType<typeof setTimeout>> = [];
    script.forEach((message, index) => {
      timers.push(
        setTimeout(() => {
          setMessages((prev) => [...prev, message]);
        }, 550 + index * 650),
      );
    });

    return () => {
      timers.forEach((timer) => clearTimeout(timer));
    };
  }, [demoRequest, target, lang]);

  useEffect(() => {
    const element = scrollRef.current;
    if (element) {
      element.scrollTo({ top: element.scrollHeight, behavior: "smooth" });
    }
  }, [messages]);

  const ask = useCallback(
    (query: string) => {
      counter.current += 1;
      const id = counter.current;
      const plans = retrieve(query, target, { decision });
      const reply: RecipientChatMessage =
        plans.length > 0
          ? {
              id: `a-${id}`,
              role: "assistant",
              text:
                lang === "en"
                  ? `Here ${plans.length === 1 ? "is" : "are"} ${plans.length} suggestion${plans.length === 1 ? "" : "s"} for you.`
                  : `Ecco ${plans.length} suggeriment${plans.length === 1 ? "o" : "i"} per te.`,
              plans,
            }
          : {
              id: `a-${id}`,
              role: "assistant",
              text: "",
            };
      setMessages((prev) => [...prev, { id: `u-${id}`, role: "user", text: query }, reply]);
    },
    [decision, lang, target],
  );

  return (
    <section
      aria-label="Chat assistente"
      style={{
        display: "flex",
        flexDirection: "column",
        height: "100%",
        minHeight: 0,
        background: t.color.bg.elevated,
        border: `1px solid ${t.color.border.subtle}`,
        borderRadius: t.radius.lg,
        boxShadow: t.shadow.soft,
        overflow: "hidden",
      }}
    >
      <header
        style={{
          padding: `${t.space[3]} ${t.space[4]}`,
          borderBottom: `1px solid ${t.color.border.subtle}`,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          gap: t.space[2],
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: t.space[2] }}>
          <span
            aria-hidden="true"
            style={{
              width: "34px",
              height: "34px",
              borderRadius: "50%",
              display: "grid",
              placeItems: "center",
              background: target === "tourist" ? t.color.accent.touristLight : t.color.accent.citizenLight,
              overflow: "hidden",
            }}
          >
            <BrandLogo variant="icon" height={24} />
          </span>
          <div>
            <strong style={{ display: "block", fontSize: t.font.size.sm, color: t.color.text.primary }}>
              Assistente AIoNapoli
            </strong>
            <span style={{ fontSize: t.font.size.xs, color: t.color.text.muted }}>
              risposte dalle schede operative del piano
            </span>
          </div>
        </div>
        {onClose ? (
          <button
            type="button"
            onClick={onClose}
            aria-label="Chiudi chat"
            style={{ border: "none", background: "transparent", color: t.color.text.muted, cursor: "pointer", fontSize: "18px" }}
          >
            ✕
          </button>
        ) : null}
      </header>

      <div
        ref={scrollRef}
        style={{
          flex: 1,
          minHeight: 0,
          overflowY: "auto",
          padding: t.space[4],
          display: "grid",
          gap: t.space[4],
          alignContent: "start",
        }}
      >
        {messages.length === 0 ? (
          <div
            style={{
              background: t.color.bg.panel,
              borderRadius: t.radius.md,
              padding: t.space[3],
              fontSize: t.font.size.sm,
              color: t.color.text.secondary,
              lineHeight: t.font.lineHeight.relaxed,
            }}
          >
            {target === "tourist"
              ? "Ciao! Posso suggerirti cosa visitare lontano dalla folla e come muoverti in città."
              : "Ciao! Posso dirti quali linee evitare oggi e come raggiungere la tua destinazione."}
          </div>
        ) : null}
        {messages.map((message) => (
          <ChatMessage key={message.id} message={message} target={target} lang={lang} />
        ))}
      </div>

      <footer style={{ padding: t.space[3], borderTop: `1px solid ${t.color.border.subtle}`, display: "grid", gap: t.space[2] }}>
        <QuickActions target={target} onSelect={ask} />
        <ChatInput target={target} onSend={ask} />
      </footer>
    </section>
  );
}
