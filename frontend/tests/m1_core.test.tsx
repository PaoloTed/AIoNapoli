import fs from "node:fs";
import path from "node:path";
import { act, fireEvent, render, renderHook, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { MockBanner } from "@/components/MockBanner";
import { useSSEStream } from "@/hooks/useSSEStream";
import {
  ApiError,
  NetworkError,
  apiFetch,
  openStream,
  postRouteRequest,
  withMockFallback,
} from "@/lib/api";
import {
  decisionResponseSchema,
  scenarioResponseSchema,
  type RefusalCode,
  type TraceEvent,
} from "@/lib/contracts";

describe("M1: Core Contracts & Fixtures Integrity", () => {
  const fixturesDir = path.resolve(__dirname, "../fixtures");

  it("loads scenario-bagnoli.json and validates against strict schema", () => {
    const raw = fs.readFileSync(path.join(fixturesDir, "scenario-bagnoli.json"), "utf8");
    const json = JSON.parse(raw);
    const parsed = scenarioResponseSchema.parse(json);
    expect(parsed.scenario_id).toBe("bagnoli");
    expect(parsed.findings).toHaveLength(3);
    expect(parsed.vehicle_positions).toHaveLength(2);
  });

  it("loads decision-bagnoli.json and validates against strict schema", () => {
    const raw = fs.readFileSync(path.join(fixturesDir, "decision-bagnoli.json"), "utf8");
    const json = JSON.parse(raw);
    const parsed = decisionResponseSchema.parse(json);
    expect(parsed.decision_id).toBe("23afe929acf8f472");
    expect(parsed.decision.plan).toHaveLength(3);
    expect(parsed.decision.reasoning_log).toHaveLength(9);
    expect(parsed.relevance.targets.operator.items).toHaveLength(3);
    expect(parsed.relevance.targets.tourist.items).toHaveLength(3);
    expect(parsed.relevance.targets.citizen.items).toHaveLength(3);
  });

  it("loads stream-bagnoli.jsonl and verifies strictly monotonic seq numbering", () => {
    const raw = fs.readFileSync(path.join(fixturesDir, "stream-bagnoli.jsonl"), "utf8");
    const lines = raw.trim().split("\n");
    expect(lines.length).toBeGreaterThanOrEqual(19);

    let lastSeq = 0;
    for (const line of lines) {
      const parsed = JSON.parse(line);
      expect(parsed.seq).toBeGreaterThan(lastSeq);
      lastSeq = parsed.seq;
      expect(parsed.event).toBeDefined();
    }
  });

  it("loads refusal-examples.json and verifies all 12 refusal codes", () => {
    const raw = fs.readFileSync(path.join(fixturesDir, "refusal-examples.json"), "utf8");
    const json = JSON.parse(raw);
    expect(Array.isArray(json.refusal_examples)).toBe(true);

    const expectedCodes: RefusalCode[] = [
      "missing_gtfs",
      "unmapped_point",
      "out_of_horizon",
      "missing_realtime",
      "missing_occupancy",
      "missing_geofence",
      "invalid_density",
      "missing_alert_level",
      "missing_time_window",
      "unsourced_alert",
      "cannot_validate",
      "unresolved_location",
    ];

    const presentCodes = new Set(
      json.refusal_examples
        .map((ex: { refusal?: { reason_code: string } }) => ex.refusal?.reason_code)
        .filter(Boolean),
    );

    expect(expectedCodes).toHaveLength(12);
    for (const code of expectedCodes) {
      expect(presentCodes.has(code)).toBe(true);
    }
  });
});

describe("M1: HTTP API Client & withMockFallback", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    delete process.env.NEXT_PUBLIC_USE_MOCKS;
  });

  it("apiFetch successfully resolves JSON response", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify({ status: "ok" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const res = await apiFetch<{ status: string }>("/api/test");
    expect(res.status).toBe("ok");
  });

  it("apiFetch throws ApiError on non-200 responses with RFC 9457 detail", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          type: "https://example.com/err",
          title: "Bad Request",
          status: 422,
          code: "invalid_finding",
          detail: "Validation failed on content.density",
          instance: "/api/v1/decision",
        }),
        {
          status: 422,
          headers: { "Content-Type": "application/problem+json" },
        },
      ),
    );

    await expect(apiFetch("/api/v1/decision")).rejects.toThrow(ApiError);
  });

  it("apiFetch throws NetworkError on abort/timeout", async () => {
    const abortController = new AbortController();
    abortController.abort("user cancelled");

    await expect(apiFetch("/api/slow", {}, abortController.signal)).rejects.toThrow(NetworkError);
  });

  it("withMockFallback uses mock supplier directly when NEXT_PUBLIC_USE_MOCKS=true", async () => {
    process.env.NEXT_PUBLIC_USE_MOCKS = "true";
    const apiFn = vi.fn().mockRejectedValue(new Error("Should not be called"));
    const mockSupplier = vi.fn().mockResolvedValue({ mocked: true });

    const result = await withMockFallback(apiFn, mockSupplier);
    expect(result.isMock).toBe(true);
    expect(result.data).toEqual({ mocked: true });
    expect(apiFn).not.toHaveBeenCalled();
    expect(mockSupplier).toHaveBeenCalledTimes(1);
  });

  it("withMockFallback returns live data when apiFn succeeds", async () => {
    process.env.NEXT_PUBLIC_USE_MOCKS = "false";
    const apiFn = vi.fn().mockResolvedValue({ live: true });
    const mockSupplier = vi.fn().mockReturnValue({ live: false });

    const result = await withMockFallback(apiFn, mockSupplier);
    expect(result.isMock).toBe(false);
    expect(result.data).toEqual({ live: true });
    expect(mockSupplier).not.toHaveBeenCalled();
  });

  it("withMockFallback catches network errors and falls back to mock supplier", async () => {
    process.env.NEXT_PUBLIC_USE_MOCKS = "false";
    const apiFn = vi.fn().mockRejectedValue(new Error("Network connection dropped"));
    const mockSupplier = vi.fn().mockReturnValue({ fallback: true });
    const onFallback = vi.fn();

    const result = await withMockFallback(apiFn, mockSupplier, { onFallback });
    expect(result.isMock).toBe(true);
    expect(result.data).toEqual({ fallback: true });
    expect(onFallback).toHaveBeenCalledWith("Network connection dropped");
  });

  it("postRouteRequest sends POST to /api/v1/route-request with text payload", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          trip_request: null,
          unresolved: [],
          parser_mode: "regex",
          needs_clarification: false,
          question: null,
        }),
        {
          status: 200,
          headers: { "Content-Type": "application/json" },
        },
      ),
    );

    const res = await postRouteRequest("da Garibaldi a Bagnoli");
    expect(res.needs_clarification).toBe(false);
    expect(fetchSpy).toHaveBeenCalledWith(
      expect.stringContaining("/api/v1/route-request"),
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ text: "da Garibaldi a Bagnoli" }),
      }),
    );
  });

  it("openStream returns EventSource pointing to scenario stream URL", () => {
    const mockES = vi.fn();
    vi.stubGlobal("EventSource", mockES);

    openStream("bagnoli");
    expect(mockES).toHaveBeenCalledWith(expect.stringContaining("/api/v1/scenario/bagnoli/stream"));
    vi.unstubAllGlobals();
  });
});

describe("M1: MockBanner Component", () => {
  afterEach(() => {
    delete process.env.NEXT_PUBLIC_USE_MOCKS;
  });

  it("renders MockBanner when isMock={true}", () => {
    render(<MockBanner isMock={true} reason="Backend non disponibile" />);
    expect(screen.getByTestId("mock-banner")).toBeInTheDocument();
    expect(screen.getByText("Backend non disponibile")).toBeInTheDocument();
  });

  it("does not render MockBanner when isMock={false}", () => {
    render(<MockBanner isMock={false} />);
    expect(screen.queryByTestId("mock-banner")).toBeNull();
  });

  it("renders MockBanner when NEXT_PUBLIC_USE_MOCKS is 'true'", () => {
    process.env.NEXT_PUBLIC_USE_MOCKS = "true";
    render(<MockBanner />);
    expect(screen.getByTestId("mock-banner")).toBeInTheDocument();
  });

  it("dismisses banner on click and triggers onDismiss callback", () => {
    const onDismiss = vi.fn();
    render(<MockBanner isMock={true} onDismiss={onDismiss} />);

    const closeBtn = screen.getByRole("button", { name: /chiudi avviso modalità mock/i });
    fireEvent.click(closeBtn);

    expect(onDismiss).toHaveBeenCalledTimes(1);
    expect(screen.queryByTestId("mock-banner")).toBeNull();
  });
});

describe("M1: useSSEStream Hook", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
    delete process.env.NEXT_PUBLIC_USE_MOCKS;
  });

  it("plays back mock events sequentially with strictly monotonic seq ordering", async () => {
    const testEvents: TraceEvent[] = [
      { seq: 1, event_type: "start", data: { scenario_id: "test", contract_version: "1.0.0" } },
      { seq: 2, event_type: "phase", data: { phase: "regole", index: 1 } },
      { seq: 3, event_type: "decision", data: { decision_id: "dec_1", contract_version: "1.0.0" } },
    ];

    process.env.NEXT_PUBLIC_USE_MOCKS = "true";

    const { result } = renderHook(() =>
      useSSEStream("test", {
        mockEvents: testEvents,
        playbackSpeedMs: 50,
      }),
    );

    expect(result.current.status).toBe("open");
    expect(result.current.isMock).toBe(true);

    // Advance timer step 1
    act(() => {
      vi.advanceTimersByTime(50);
    });
    expect(result.current.events).toHaveLength(1);
    expect(result.current.events[0]?.seq).toBe(1);

    // Advance timer step 2
    act(() => {
      vi.advanceTimersByTime(50);
    });
    expect(result.current.events).toHaveLength(2);
    expect(result.current.events[1]?.seq).toBe(2);

    // Advance timer step 3 (decision)
    act(() => {
      vi.advanceTimersByTime(50);
    });
    expect(result.current.events).toHaveLength(3);
    expect(result.current.status).toBe("done");
  });

  it("discards out-of-order or duplicate seq numbers from EventSource", () => {
    type Listener = (e: MessageEvent) => void;
    const listeners: Record<string, Listener> = {};

    class MockEventSource {
      addEventListener(type: string, listener: Listener) {
        listeners[type] = listener;
      }
      close = vi.fn();
      onopen = vi.fn();
      onerror = vi.fn();
    }

    vi.stubGlobal("EventSource", MockEventSource);

    const { result } = renderHook(() => useSSEStream("bagnoli"));

    // Simulate open
    act(() => {
      // @ts-expect-error test trigger
      listeners.start?.({
        lastEventId: "1",
        data: JSON.stringify({ scenario_id: "bagnoli", contract_version: "1.0.0" }),
      });
    });
    expect(result.current.events).toHaveLength(1);

    // Send duplicate seq 1 -> MUST BE DISCARDED
    act(() => {
      listeners.phase?.({
        lastEventId: "1",
        data: JSON.stringify({ phase: "duplicate", index: 1 }),
      } as MessageEvent);
    });
    expect(result.current.events).toHaveLength(1);

    // Send out-of-order seq 0 -> MUST BE DISCARDED
    act(() => {
      listeners.phase?.({
        lastEventId: "0",
        data: JSON.stringify({ phase: "backwards", index: 0 }),
      } as MessageEvent);
    });
    expect(result.current.events).toHaveLength(1);

    // Send next valid seq 2 -> ACCEPTED
    act(() => {
      listeners.phase?.({
        lastEventId: "2",
        data: JSON.stringify({ phase: "validazione", index: 1 }),
      } as MessageEvent);
    });
    expect(result.current.events).toHaveLength(2);
    expect(result.current.events[1]?.seq).toBe(2);

    vi.unstubAllGlobals();
  });
});
