"use client";

import { useEffect, useRef, useState } from "react";
import { recipientTokens as t } from "@/styles/design-tokens-recipient";
import type { Target } from "@/lib/types/contracts";
import { apiFetch } from "@/lib/api/client";
import { planPrompt, type JourneyResponse, type IngestionStatus } from "@/lib/api/journeys";
import { ChatInput } from "./ChatInput";

type Entry = { query: string; result?: JourneyResponse; error?: string };
const examples = ["Da metro Chiaiano al MANN domani alle 8", "Da via Giovanni Antonio Campano a Città della Scienza domani alle 8"];
const labels: Record<string, string> = {
  no_route: "Nessun percorso disponibile per data e modalità richieste.",
  no_verified_route: "Non è disponibile un percorso verificato rispetto ai problemi noti.",
  insufficient_data: "Dati insufficienti per verificare il viaggio.",
  place_not_found: "Luogo non trovato: specifica meglio origine e destinazione.",
  invalid_request: "Richiesta non valida: controlla luoghi, data e preferenze.",
};
const time = (value?: string | null) => value ? new Date(value).toLocaleTimeString("it-IT", { hour: "2-digit", minute: "2-digit", timeZone: "Europe/Rome" }) : "";

export function LiveJourneyChat({ target, onClose }: { target: Target; onClose?: () => void }) {
  const [entries, setEntries] = useState<Entry[]>([]);
  const [busy, setBusy] = useState(false);
  const busyRef = useRef(false);
  const [status, setStatus] = useState<IngestionStatus | null>(null);
  const [location, setLocation] = useState<{ lat: number; lon: number }>();
  const [context, setContext] = useState<Record<string, unknown>>({});
  const [locationMessage, setLocationMessage] = useState("");
  const scroll = useRef<HTMLDivElement>(null);
  const accent = target === "tourist" ? t.color.accent.tourist : t.color.accent.citizen;
  useEffect(() => { apiFetch<IngestionStatus>("/api/v1/ingestion/status").then(setStatus).catch(() => setStatus(null)); }, []);
  useEffect(() => { scroll.current?.scrollTo({ top: scroll.current.scrollHeight, behavior: "smooth" }); }, [entries, busy]);

  async function ask(query: string, nextContext: Record<string, unknown> = {}) {
    if (busyRef.current) return;
    busyRef.current = true;
    setBusy(true);
    setContext(nextContext);
    setEntries((previous) => [...previous, { query }]);
    try {
      const result = await planPrompt(query, nextContext, location);
      setEntries((previous) => [...previous.slice(0, -1), { query, result }]);
    } catch (error) {
      setEntries((previous) => [...previous.slice(0, -1), { query, error: error instanceof Error ? error.message : "Backend non disponibile" }]);
    } finally { busyRef.current = false; setBusy(false); }
  }

  function locate() {
    if (!navigator.geolocation) { setLocationMessage("Posizione non supportata dal browser."); return; }
    setLocationMessage("Richiesta posizione…");
    navigator.geolocation.getCurrentPosition(({ coords }) => {
      setLocation({ lat: coords.latitude, lon: coords.longitude });
      setLocationMessage("Posizione disponibile: puoi scrivere ‘da qui’.");
    }, () => setLocationMessage("Posizione non disponibile: scrivi l'indirizzo."), { timeout: 10000 });
  }

  const buttonStyle = { padding: "8px 12px", borderRadius: 14, border: `1px solid ${accent}`, color: accent, background: "transparent", cursor: "pointer" };
  return <section aria-label="Pianificazione viaggio reale" style={{ display: "flex", flexDirection: "column", height: "100%", minHeight: 400, border: `1px solid ${t.color.border.subtle}`, borderRadius: 20, background: t.color.bg.elevated, overflow: "hidden" }}>
    <header style={{ padding: 16, borderBottom: `1px solid ${t.color.border.subtle}`, display: "flex", justifyContent: "space-between" }}>
      <div><strong>Il tuo viaggio a Napoli</strong><div style={{ fontSize: 12 }}>Percorsi reali ANM + EAV · problemi noti dalle news</div></div>
      {onClose && <button onClick={onClose} aria-label="Chiudi chat" style={buttonStyle}>✕</button>}
    </header>
    <div ref={scroll} aria-live="polite" style={{ flex: 1, overflowY: "auto", padding: 16 }}>
      {status && <p style={{ fontSize: 12, color: t.color.text.secondary }}>
        {Object.values(status.documents_by_status).reduce((a, b) => a + b, 0)} news conservate · {status.sources.checked}/{status.sources.total} fonti controllate.
        {((status.documents_by_status.pending ?? 0) + (status.documents_by_status.needs_review ?? 0)) > 0 && " Alcune notizie attendono interpretazione: copertura dei problemi incompleta."}
      </p>}
      {entries.length === 0 && <><p>Scrivi origine, destinazione e quando vuoi partire.</p>{examples.map((example) => <p key={example}><button style={buttonStyle} onClick={() => void ask(example)}>{example}</button></p>)}</>}
      {entries.map((entry, index) => <article key={index} style={{ marginBottom: 20 }}>
        <p style={{ background: accent, color: "white", padding: 12, borderRadius: 16 }}>{entry.query}</p>
        {entry.error && <p role="alert">{entry.error}. Nessun percorso simulato è stato sostituito.</p>}
        {entry.result && <>
          {entry.result.interpretation.parser !== "llm" && <p style={{ fontSize: 12 }}>Comprensione del testo: parser locale; modello AI non attivo.</p>}
          {entry.result.clarification && <div><p>{entry.result.clarification.question}</p>
            {entry.result.clarification.candidates.map((candidate) => <button key={candidate.candidate_id} disabled={busy || index !== entries.length - 1} style={{ ...buttonStyle, margin: 4 }} onClick={() => {
              const selected = { ...((context.selected_candidates as Record<string, string>) ?? {}), [entry.result!.clarification!.role]: candidate.candidate_id };
              void ask(entry.query, { ...context, selected_candidates: selected });
            }}>{candidate.label}</button>)}
            {entry.result.clarification.role === "preference" && <button disabled={busy || index !== entries.length - 1} style={buttonStyle} onClick={() => void ask(entry.query, { ...context, accept_unsupported_constraints: true })}>Procedi senza garantire questo vincolo</button>}
          </div>}
          {labels[entry.result.status] && <p>{labels[entry.result.status]}</p>}
          {entry.result.journey?.source.is_simulated && <strong>SIMULAZIONE</strong>}
          {entry.result.journey?.itineraries.map((itinerary, routeIndex) => <div key={itinerary.index} style={{ padding: 12, margin: "12px 0", border: `1px solid ${t.color.border.subtle}`, borderRadius: 12 }}>
            <strong>{routeIndex === 0 ? "Percorso consigliato" : "Alternativa"} · {itinerary.duration_s != null ? `${Math.ceil(itinerary.duration_s / 60)} min` : "durata non disponibile"}</strong>
            <div>{itinerary.transfers ?? 0} cambi · {Math.round(itinerary.walk_distance_m ?? 0)} m a piedi</div>
            <ol>{itinerary.legs.map((leg, legIndex) => <li key={legIndex} style={{ margin: "8px 0" }}>
              {leg.mode === "WALK" ? "A piedi" : `${leg.mode} ${leg.route ?? ""}`} · {leg.from_name} → {leg.to_name}<br />
              <small>{time(leg.start_scheduled)}–{time(leg.end_scheduled)} {leg.operator}</small>
            </li>)}</ol>
          </div>)}
          {entry.result.journey?.avoided_problems.map((problem, i) => <p key={i}>Problema evitato: {problem.title}. {problem.reason}</p>)}
          {entry.result.journey?.uncertainties.map((note, i) => <p key={i}>{note}</p>)}
          {!!entry.result.journey?.agent_trace.length && <details><summary>Contributi degli agenti</summary>{entry.result.journey.agent_trace.map((trace, i) => <p key={i}><strong>{trace.agent}</strong>: {trace.detail}</p>)}</details>}
        </>}
      </article>)}
      {busy && <p role="status">Calcolo e verifica del viaggio…</p>}
    </div>
    <footer style={{ padding: 12, borderTop: `1px solid ${t.color.border.subtle}` }}>
      <button type="button" style={buttonStyle} onClick={locate}>Usa la mia posizione</button><small> {locationMessage}</small>
      <div aria-busy={busy} style={{ pointerEvents: busy ? "none" : "auto", opacity: busy ? 0.6 : 1, marginTop: 8 }}><ChatInput target={target} onSend={(query) => void ask(query)} /></div>
    </footer>
  </section>;
}
