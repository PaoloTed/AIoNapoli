/**
 * @purpose Shell responsive recipient con Overview e Chat (desktop affiancate, mobile drawer)
 * @contracts ScenarioSnapshot, DecisionResponse, Target
 * @tokens recipient
 * @verified 2026-11-15
 */

"use client";

import { useState } from "react";
import { recipientTokens as t } from "@/styles/design-tokens-recipient";
import { useAppStore } from "@/lib/state/store";
import { RecipientHeader } from "./RecipientHeader";
import { OverviewPanel } from "./overview/OverviewPanel";
import { ChatPanel } from "./chat/ChatPanel";

export function RecipientShell() {
  const { scenario, decision, target, setTarget, lang, setLang, streamStatus, isSimulated } = useAppStore();
  const [mobileChatOpen, setMobileChatOpen] = useState(false);
  const findings = scenario?.findings ?? [];

  return (
    <div
      style={{
        minHeight: "100vh",
        background: t.color.bg.base,
        color: t.color.text.primary,
        fontFamily: t.font.family,
        display: "flex",
        flexDirection: "column",
      }}
    >
      <RecipientHeader
        target={target}
        onTargetChange={setTarget}
        lang={lang}
        onLangChange={setLang}
        status={streamStatus}
        simulated={isSimulated}
      />

      <main
        className="recipient-main"
        style={{
          flex: 1,
          width: "100%",
          maxWidth: "1280px",
          margin: "0 auto",
          padding: `0 ${t.space[6]} ${t.space[12]}`,
        }}
      >
        {findings.length === 0 ? (
          <div
            style={{
              background: t.color.bg.panel,
              border: `1px solid ${t.color.border.subtle}`,
              borderRadius: t.radius.lg,
              padding: t.space[8],
              textAlign: "center",
              color: t.color.text.secondary,
            }}
          >
            Sto preparando le informazioni sulla città…
          </div>
        ) : (
          <div className="recipient-grid">
            <OverviewPanel
              target={target}
              findings={findings}
              decision={decision}
              onOpenChat={() => setMobileChatOpen(true)}
            />
            <div className="recipient-chat-desktop" style={{ position: "sticky", top: t.space[4], height: "calc(100vh - 140px)" }}>
              <ChatPanel target={target} />
            </div>
          </div>
        )}
      </main>

      <button
        type="button"
        className="recipient-sticky"
        onClick={() => setMobileChatOpen(true)}
        style={{
          position: "fixed",
          left: t.space[4],
          right: t.space[4],
          bottom: t.space[4],
          zIndex: 40,
          border: "none",
          borderRadius: t.radius.pill,
          padding: "16px 20px",
          fontSize: t.font.size.md,
          fontWeight: t.font.weight.semibold,
          color: t.color.text.inverse,
          background: target === "tourist" ? t.color.accent.tourist : t.color.accent.citizen,
          boxShadow: t.shadow.elevated,
          cursor: "pointer",
        }}
      >
        ✦ Chiedi all&apos;assistente
      </button>

      {mobileChatOpen ? (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Chat assistente"
          style={{
            position: "fixed",
            inset: 0,
            zIndex: 50,
            background: "rgba(15, 23, 42, 0.35)",
            display: "flex",
            flexDirection: "column",
            justifyContent: "flex-end",
          }}
        >
          <button
            type="button"
            aria-label="Chiudi chat"
            onClick={() => setMobileChatOpen(false)}
            style={{ position: "absolute", inset: 0, border: "none", background: "transparent" }}
          />
          <div style={{ position: "relative", height: "85vh", padding: t.space[3] }}>
            <ChatPanel target={target} onClose={() => setMobileChatOpen(false)} />
          </div>
        </div>
      ) : null}
    </div>
  );
}
