"use client";

import { useEffect } from "react";

interface OperatorShortcutsModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export function OperatorShortcutsModal({ isOpen, onClose }: OperatorShortcutsModalProps) {
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape" && isOpen) {
        onClose();
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const shortcuts = [
    { key: "1", description: "Naviga a Sala Operativa (Mission Control)" },
    { key: "2", description: "Naviga a Guida Turista (Interfaccia Mobile)" },
    { key: "3", description: "Naviga a Guida Cittadino (Servizi e Tratte)" },
    { key: "4", description: "Naviga a Verifica & Audit (Convalida Immutabile)" },
    { key: "R", description: "Ripeti Verifica Deterministica (Test Idempotenza)" },
    { key: "S", description: "Apri Ispezione Telemetria Sensori (RealSense/YOLO)" },
    { key: "?", description: "Mostra / Nascondi Guida Scorciatoie da Tastiera" },
    { key: "Esc", description: "Chiudi qualsiasi finestra o cassetto modale" },
  ];

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Scorciatoie da Tastiera per Sala Operativa"
      data-testid="shortcuts-modal"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="w-full max-w-md rounded-[12px] border border-[var(--border)] bg-[#0B1016] p-6 text-[#E6EDF3] shadow-2xl space-y-4"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-[var(--border)] pb-3">
          <div className="flex items-center gap-2">
            <span className="text-[16px]">⌨</span>
            <h3 className="text-[14px] font-semibold tracking-wide text-white">
              SCORCIATOIE DA TASTIERA
            </h3>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-[4px] p-1 text-[#8B949E] hover:bg-[#161F2C] hover:text-white"
            aria-label="Chiudi guida scorciatoie"
          >
            ✕
          </button>
        </div>

        <p className="text-[12px] text-[#8B949E]">
          Naviga e opera rapidamente nella console di controllo tramite la tastiera:
        </p>

        <ul className="space-y-2 text-[13px]">
          {shortcuts.map((sc) => (
            <li
              key={sc.key}
              className="flex items-center justify-between rounded-[6px] border border-[var(--border)] bg-[#121820] px-3 py-2"
            >
              <span className="text-[#C9D1D9]">{sc.description}</span>
              <kbd className="inline-flex min-w-[24px] items-center justify-center rounded border border-[#30363D] bg-[#161F2C] px-2 py-0.5 font-mono text-[11px] font-semibold text-[#58A6FF] shadow-sm">
                {sc.key}
              </kbd>
            </li>
          ))}
        </ul>

        <div className="pt-2 text-right">
          <button
            type="button"
            onClick={onClose}
            className="rounded-[6px] border border-[var(--border)] bg-[#161F2C] px-4 py-1.5 text-[12px] font-medium text-white hover:bg-[#1F2937]"
          >
            Ho capito (ESC)
          </button>
        </div>
      </div>
    </div>
  );
}
