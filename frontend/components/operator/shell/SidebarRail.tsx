/**
 * @purpose Rail verticale di navigazione tra le schede del Command Center
 * @contracts nessuno
 * @tokens operator
 * @verified 2026-11-15
 */

"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { operatorTokens as t } from "@/styles/design-tokens-operator";
import { BrandLogo } from "@/components/brand/BrandLogo";

const ITEMS = [
  { href: "/operator/situation", label: "Situazione", glyph: "◎" },
  { href: "/operator/decision", label: "Decisione", glyph: "◆" },
  { href: "/operator/discard", label: "Scarti", glyph: "⇄" },
  { href: "/operator/audit", label: "Audit", glyph: "▤" },
] as const;

export function SidebarRail({ onOpenChat }: { onOpenChat: () => void }) {
  const pathname = usePathname();

  return (
    <nav
      aria-label="Schede operative"
      style={{
        width: "208px",
        flexShrink: 0,
        background: t.color.bg.panel,
        borderRight: `1px solid ${t.color.border.subtle}`,
        display: "flex",
        flexDirection: "column",
        justifyContent: "space-between",
        padding: `${t.space[4]} ${t.space[2]}`,
      }}
    >
      <div style={{ display: "flex", flexDirection: "column", gap: t.space[6] }}>
        <div style={{ padding: `0 ${t.space[2]}` }}>
          <BrandLogo variant="icon" height={30} priority />
          <p
            style={{
              margin: `${t.space[2]} 0 0`,
              fontSize: t.font.size.xs,
              letterSpacing: "0.12em",
              textTransform: "uppercase",
              color: t.color.text.muted,
            }}
          >
            Command Center
          </p>
        </div>

        <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: "2px" }}>
          {ITEMS.map((item) => {
            const active = pathname?.startsWith(item.href) ?? false;
            return (
              <li key={item.href}>
                <Link
                  href={item.href}
                  aria-current={active ? "page" : undefined}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: t.space[3],
                    padding: `${t.space[3]} ${t.space[3]}`,
                    borderLeft: `2px solid ${active ? t.color.accent.primary : "transparent"}`,
                    background: active ? t.color.accent.muted : "transparent",
                    color: active ? t.color.text.primary : t.color.text.secondary,
                    borderRadius: `0 ${t.radius.sm} ${t.radius.sm} 0`,
                    textDecoration: "none",
                    fontSize: t.font.size.md,
                    fontWeight: active ? t.font.weight.semibold : t.font.weight.medium,
                    transition: `background ${t.transition.fast}, color ${t.transition.fast}`,
                  }}
                >
                  <span aria-hidden="true" style={{ color: t.color.accent.primary, fontSize: "15px" }}>
                    {item.glyph}
                  </span>
                  {item.label}
                </Link>
              </li>
            );
          })}
        </ul>
      </div>

      <button
        type="button"
        onClick={onOpenChat}
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          gap: t.space[1],
          padding: `${t.space[2]} ${t.space[2]}`,
          borderRadius: t.radius.sm,
          border: `1px solid ${t.color.border.strong}`,
          background: t.color.bg.panelAlt,
          color: t.color.text.primary,
          fontSize: t.font.size.sm,
          fontWeight: t.font.weight.semibold,
          cursor: "pointer",
          whiteSpace: "nowrap",
        }}
      >
        ✦ Chat
        <kbd
          style={{
            fontSize: "10px",
            color: t.color.text.muted,
            border: `1px solid ${t.color.border.subtle}`,
            borderRadius: t.radius.sm,
            padding: "0 3px",
          }}
        >
          Ctrl K
        </kbd>
      </button>
    </nav>
  );
}
