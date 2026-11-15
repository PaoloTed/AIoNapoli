import { apiFetch } from "./client";

export type JourneyLeg = {
  mode: string; route?: string | null; operator?: string | null;
  from_name?: string | null; to_name?: string | null;
  start_scheduled?: string | null; end_scheduled?: string | null;
  geometry?: string | null;
};
export type JourneyResponse = {
  status: string;
  interpretation: { parser: string; warnings: string[] };
  clarification?: { role: string; question: string; candidates: { candidate_id: string; label: string }[] } | null;
  journey?: {
    status: string;
    itineraries: { index: number; duration_s?: number | null; transfers?: number | null; walk_distance_m?: number | null; legs: JourneyLeg[] }[];
    avoided_problems: { title: string; reason: string }[];
    uncertainties: string[];
    agent_trace: { agent: string; status: string; detail: string }[];
    source: { is_simulated: boolean };
  } | null;
};

export function planPrompt(prompt: string, context: Record<string, unknown> = {}, location?: {lat: number; lon: number}) {
  return apiFetch<JourneyResponse>("/api/v1/journeys", {
    method: "POST", headers: { "Content-Type": "application/json" }, timeoutMs: 60000,
    body: JSON.stringify({ prompt, context, timezone: "Europe/Rome", first: 3, ...(location ? { client_location: location } : {}) }),
  });
}

export type IngestionStatus = {
  sources: { total: number; checked: number; with_error: number };
  documents_by_status: Record<string, number>;
};
