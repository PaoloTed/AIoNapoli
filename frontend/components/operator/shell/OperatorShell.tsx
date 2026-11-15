/**
 * @purpose Shell full-height del Command Center con rail, header, bootstrap e chat
 * @contracts ScenarioSnapshot, DecisionResponse, TraceEvent
 * @tokens operator
 * @verified 2026-11-15
 */

"use client";

import { useCallback, useState, type ReactNode } from "react";
import { operatorTokens as t } from "@/styles/design-tokens-operator";
import { useAppStore } from "@/lib/state/store";
import { useBootstrapScenario } from "@/lib/state/useBootstrap";
import { useSSEStream } from "@/lib/sse/useSSEStream";
import { useKeyboardShortcut } from "@/components/ui/useKeyboardShortcut";
import { ErrorState } from "@/components/ui/ErrorState";
import { Header } from "./Header";
import { SidebarRail } from "./SidebarRail";
import { ChatDrawer } from "../chat/ChatDrawer";
import { MockBanner } from "../MockBanner";

export function OperatorShell({
  scenarioId,
  children,
}: {
  scenarioId: string;
  children: ReactNode;
}) {
  const { isSimulated } = useAppStore();
  const { loading, problem, reload } = useBootstrapScenario(scenarioId);
  const [chatOpen, setChatOpen] = useState(false);
  useSSEStream(scenarioId, { enabled: !loading, simulated: isSimulated });

  const openChat = useCallback(() => setChatOpen(true), []);
  const closeChat = useCallback(() => setChatOpen(false), []);
  useKeyboardShortcut({ key: "k", ctrlOrMeta: true }, openChat);

  return (
    <div
      style={{
        height: "100vh",
        display: "flex",
        background: t.color.bg.base,
        color: t.color.text.primary,
        fontFamily: t.font.family,
        fontSize: t.font.size.base,
        overflow: "hidden",
      }}
    >
      <SidebarRail onOpenChat={openChat} />
      <div style={{ flex: 1, display: "flex", flexDirection: "column", minWidth: 0 }}>
        {isSimulated ? <MockBanner /> : null}
        <Header onOpenChat={openChat} />
        <main style={{ flex: 1, overflow: "auto", padding: t.space[4] }}>
          {problem ? (
            <div style={{ marginBottom: t.space[4] }}>
              <ErrorState problem={problem} onRetry={reload} />
            </div>
          ) : null}
          {children}
        </main>
      </div>
      <ChatDrawer open={chatOpen} onClose={closeChat} />
    </div>
  );
}
