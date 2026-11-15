"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api/client";
import type { IngestionStatus } from "@/lib/api/journeys";

type News = { document_id: number; title: string; source_name: string; status: string; canonical_url?: string };

export function LiveNewsPanel() {
  const [status, setStatus] = useState<IngestionStatus | null>(null);
  const [news, setNews] = useState<News[]>([]);
  const [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    const refresh = () => Promise.all([
      apiFetch<IngestionStatus>("/api/v1/ingestion/status"),
      apiFetch<News[]>("/api/v1/ingestion/documents?limit=5"),
    ]).then(([state, documents]) => { if (active) { setStatus(state); setNews(documents); setError(""); } })
      .catch(() => { if (active) setError("Acquisizione news non raggiungibile."); });
    void refresh();
    const timer = setInterval(() => void refresh(), 60000);
    return () => { active = false; clearInterval(timer); };
  }, []);
  return <section aria-label="News reali acquisite" style={{ padding: 16, marginBottom: 16, border: "1px solid #64748b", borderRadius: 12 }}>
    <strong>News reali · archivio backend</strong>
    {error && <p role="alert">{error}</p>}
    {status && <p>{status.sources.checked}/{status.sources.total} fonti controllate · {Object.values(status.documents_by_status).reduce((a, b) => a + b, 0)} documenti conservati · {status.sources.with_error} fonti con errori</p>}
    <p style={{ fontSize: 12 }}>Una notizia acquisita non è ancora una perturbazione verificata. Le notizie pending/needs_review attendono interpretazione.</p>
    <ul>{news.map((item) => <li key={item.document_id}>{item.canonical_url?.startsWith("https://") ? <a href={item.canonical_url} target="_blank" rel="noreferrer">{item.title}</a> : item.title} <small>— {item.source_name} · {item.status}</small></li>)}</ul>
    <small>La mappa e le schede dello scenario sottostante sono dimostrative.</small>
  </section>;
}
