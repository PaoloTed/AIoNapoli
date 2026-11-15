"use client";

import { useState } from "react";
import clsx from "clsx";
import {
  fetchRouteRequest,
  SAMPLE_ROUTE_QUERIES,
  type RouteRequestResponse,
} from "@/lib/routeRequest";
import { type Locale } from "@/lib/format";

type RouteRequestAssistantProps = {
  theme?: "dark" | "light";
  locale?: Locale;
  compact?: boolean;
  onLocationSelected?: (lat: number, lon: number, label: string) => void;
};

export function RouteRequestAssistant({
  theme = "light",
  locale = "it",
  compact = false,
  onLocationSelected,
}: RouteRequestAssistantProps) {
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<RouteRequestResponse | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const isDark = theme === "dark";

  const handleSearch = async (textToSearch: string) => {
    const trimmed = textToSearch.trim();
    if (!trimmed) return;

    setLoading(true);
    setErrorMsg(null);

    try {
      const res = await fetchRouteRequest(trimmed);
      setResult(res);
      if (res.trip_request && onLocationSelected) {
        onLocationSelected(
          res.trip_request.destination.lat,
          res.trip_request.destination.lon,
          res.trip_request.destination.label,
        );
      }
    } catch (err) {
      setErrorMsg(err instanceof Error ? err.message : "Errore durante l'elaborazione");
    } finally {
      setLoading(false);
    }
  };

  const handleChipClick = (sample: string) => {
    setQuery(sample);
    void handleSearch(sample);
  };

  return (
    <div
      data-testid="route-request-assistant"
      className={clsx(
        "rounded-[8px] border transition-colors",
        isDark
          ? "border-[#22303D] bg-[#0E151D] text-[#E8EDF2]"
          : "border-[#E5E3DE] bg-[#FFFFFF] text-[#141A20]",
        compact ? "p-3 space-y-3" : "p-4 space-y-4 shadow-xs",
      )}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <span className="text-[10px] font-bold uppercase tracking-wider text-[#D06A32]">
            Assistente di Viaggio Determinista
          </span>
          <h3 className="text-[15px] font-semibold">
            {locale === "en" ? "Natural Language Route Planner" : "Richiesta Percorso in Linguaggio Naturale"}
          </h3>
        </div>
        <span
          className={clsx(
            "rounded-[4px] border px-2 py-0.5 font-mono text-[10px]",
            isDark
              ? "border-[#22303D] bg-[#131A23] text-[#8A9BA8]"
              : "border-[#E5E3DE] bg-[#F5F4F0] text-[#5C6874]",
          )}
        >
          POST /api/v1/route-request
        </span>
      </div>

      <p className="text-[12px] text-[var(--text-muted)]">
        {locale === "en"
          ? "Enter an informal journey query. Origins and destinations are strictly geocoded within Naples' boundaries without LLM hallucinations."
          : "Digita una richiesta informale. Origine e destinazione vengono risolte deterministicamente sul territorio di Napoli senza allucinazioni generative."}
      </p>

      {/* Preset Chips */}
      <div className="flex flex-wrap items-center gap-1.5">
        <span className="text-[11px] text-[var(--text-muted)] font-medium">
          {locale === "en" ? "Examples:" : "Esempi:"}
        </span>
        {SAMPLE_ROUTE_QUERIES.map((sample) => (
          <button
            key={sample}
            type="button"
            onClick={() => handleChipClick(sample)}
            className={clsx(
              "rounded-[4px] border px-2 py-0.5 text-[11px] transition-colors cursor-pointer",
              isDark
                ? "border-[#22303D] bg-[#141C26] text-[#A6B4C2] hover:border-[#D06A32] hover:text-[#FFFFFF]"
                : "border-[#DCDAD4] bg-[#F5F4F0] text-[#4A5568] hover:border-[#D06A32] hover:text-[#141A20]",
            )}
          >
            {sample}
          </button>
        ))}
      </div>

      {/* Search Input Box */}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          void handleSearch(query);
        }}
        className="flex gap-2"
      >
        <div className="relative flex-1">
          <input
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={
              locale === "en"
                ? "e.g. From Piazza Garibaldi to Bagnoli at 18..."
                : "Es: Da Piazza Garibaldi a Bagnoli alle 18..."
            }
            className={clsx(
              "w-full rounded-[6px] border px-3 py-2 text-[13px] outline-none transition-colors",
              isDark
                ? "border-[#2A3B4C] bg-[#141C26] text-[#E8EDF2] placeholder-[#6C7A89] focus:border-[#D06A32]"
                : "border-[#D2D0CA] bg-[#FAF9F5] text-[#141A20] placeholder-[#8A94A0] focus:border-[#D06A32]",
            )}
          />
          {query && (
            <button
              type="button"
              onClick={() => {
                setQuery("");
                setResult(null);
              }}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-[12px] text-[var(--text-muted)] hover:text-[var(--text)]"
            >
              ✕
            </button>
          )}
        </div>

        <button
          type="submit"
          disabled={loading || !query.trim()}
          className={clsx(
            "rounded-[6px] px-3.5 py-2 text-[13px] font-medium transition-colors cursor-pointer disabled:opacity-50",
            isDark
              ? "bg-[#D06A32] text-white hover:bg-[#B85724]"
              : "bg-[#D06A32] text-white hover:bg-[#B85724]",
          )}
        >
          {loading ? (locale === "en" ? "Resolving..." : "Analisi...") : locale === "en" ? "Parse" : "Risolvi"}
        </button>
      </form>

      {/* Error state */}
      {errorMsg && (
        <div className="rounded-[6px] border border-[#E05252]/40 bg-[#E05252]/10 p-2.5 text-[12px] text-[#E05252]">
          {errorMsg}
        </div>
      )}

      {/* Results Section */}
      {result && (
        <div aria-live="polite" className="space-y-3 pt-1">
          {result.trip_request ? (
            <div
              className={clsx(
                "rounded-[6px] border p-3 space-y-2.5",
                isDark ? "border-[#1E3040] bg-[#111922]" : "border-[#E0DED7] bg-[#F7F6F2]",
              )}
            >
              <div className="flex flex-wrap items-center justify-between gap-1 text-[11px]">
                <span className="font-semibold text-[#2D8A4E] flex items-center gap-1">
                  <span>✓</span> {locale === "en" ? "Request Parsed & Geocoded" : "Richiesta Risolta con Successo"}
                </span>
                <span className="font-mono text-[10px] text-[var(--text-muted)]">
                  parser_mode: {result.parser_mode} · Bounding Box Napoli OK
                </span>
              </div>

              <div className="grid gap-2 sm:grid-cols-2 text-[12px]">
                {/* Origin */}
                <div
                  className={clsx(
                    "rounded-[4px] border p-2 space-y-1",
                    isDark ? "border-[#22303D] bg-[#0E151D]" : "border-[#E5E3DE] bg-[#FFFFFF]",
                  )}
                >
                  <div className="flex items-center justify-between text-[10px] font-medium text-[var(--text-muted)]">
                    <span>{locale === "en" ? "ORIGIN" : "ORIGINE"}</span>
                    <span className="rounded-[3px] bg-[#2D8A4E]/15 px-1 py-0.2 text-[#2D8A4E] uppercase">
                      {result.trip_request.origin.kind}
                    </span>
                  </div>
                  <p className="font-semibold">{result.trip_request.origin.label}</p>
                  <p className="font-mono text-[10px] text-[var(--text-muted)]">
                    [{result.trip_request.origin.lat.toFixed(4)}, {result.trip_request.origin.lon.toFixed(4)}] ·{" "}
                    {result.trip_request.origin.resolved_by}
                  </p>
                </div>

                {/* Destination */}
                <div
                  className={clsx(
                    "rounded-[4px] border p-2 space-y-1",
                    isDark ? "border-[#22303D] bg-[#0E151D]" : "border-[#E5E3DE] bg-[#FFFFFF]",
                  )}
                >
                  <div className="flex items-center justify-between text-[10px] font-medium text-[var(--text-muted)]">
                    <span>{locale === "en" ? "DESTINATION" : "DESTINAZIONE"}</span>
                    <span className="rounded-[3px] bg-[#4FB3D9]/15 px-1 py-0.2 text-[#4FB3D9] uppercase">
                      {result.trip_request.destination.kind}
                    </span>
                  </div>
                  <p className="font-semibold">{result.trip_request.destination.label}</p>
                  <p className="font-mono text-[10px] text-[var(--text-muted)]">
                    [{result.trip_request.destination.lat.toFixed(4)}, {result.trip_request.destination.lon.toFixed(4)}] ·{" "}
                    {result.trip_request.destination.resolved_by}
                  </p>
                </div>
              </div>

              {/* Timestamp & Constraints */}
              <div className="flex flex-wrap items-center justify-between gap-2 text-[11px] text-[var(--text-muted)] pt-1 border-t border-[var(--border)]">
                <span>
                  {locale === "en" ? "Departure:" : "Partenza:"}{" "}
                  <strong className="font-mono text-[var(--text)]">
                    {result.trip_request.when.slice(11, 16)}
                  </strong>
                </span>
                <span>
                  {Object.keys(result.trip_request.constraints).length > 0 ? (
                    <span className="text-[#D06A32] font-medium">
                      {locale === "en" ? "Covered path preferred" : "Preferito percorso al coperto"}
                    </span>
                  ) : (
                    <span>{locale === "en" ? "Standard constraints" : "Nessun vincolo meteo penalizzante"}</span>
                  )}
                </span>
              </div>
            </div>
          ) : null}

          {/* Clarification state */}
          {result.needs_clarification && (
            <div
              className={clsx(
                "rounded-[6px] border p-3 space-y-2 text-[12px]",
                isDark ? "border-[#D06A32]/40 bg-[#D06A32]/10" : "border-[#D06A32]/30 bg-[#FFF7F0]",
              )}
            >
              <div className="flex items-center gap-1.5 font-semibold text-[#D06A32]">
                <span>⚠</span>
                <span>{locale === "en" ? "Clarification Required" : "Richiesta di Chiarimento"}</span>
              </div>

              {result.question && (
                <p className="font-medium text-[var(--text)]">
                  &ldquo;{result.question}&rdquo;
                </p>
              )}

              {result.unresolved.length > 0 && (
                <div className="space-y-1 pt-1">
                  <p className="text-[11px] font-medium uppercase tracking-wider text-[var(--text-muted)]">
                    {locale === "en" ? "Unresolved Entities:" : "Entità non verificate:"}
                  </p>
                  <ul className="space-y-1">
                    {result.unresolved.map((u, idx) => (
                      <li
                        key={idx}
                        className="flex flex-wrap items-center gap-1.5 font-mono text-[11px]"
                      >
                        <span className="font-bold text-[#E05252]">{u.raw_text}</span>:
                        <span className="text-[var(--text-muted)]">{u.reason}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              <p className="text-[11px] text-[var(--text-muted)] pt-1">
                {locale === "en"
                  ? "The system rejects locations outside the Naples metropolitan bounding box (40.75-40.95 lat, 14.10-14.40 lon) to guarantee deterministic routing."
                  : "Il sistema rigetta luoghi al di fuori del bounding box metropolitano di Napoli (40.75-40.95 lat, 14.10-14.40 lon) per garantire instradamento deterministico senza percorsi inventati."}
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
