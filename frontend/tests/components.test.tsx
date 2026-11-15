import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";
import { ChatPanel } from "@/components/ChatPanel";
import { CitizenView } from "@/components/CitizenView";
import { ConflictPanel } from "@/components/ConflictPanel";
import { DecisionHeader } from "@/components/DecisionHeader";
import { DiscardRecalcPanel } from "@/components/DiscardRecalcPanel";
import { FindingCard } from "@/components/FindingCard";
import { GroundedQueryPanel } from "@/components/GroundedQueryPanel";
import { LiveVisionFeed } from "@/components/LiveVisionFeed";
import { MapPanel } from "@/components/MapPanel";
import { OperatorShortcutsModal } from "@/components/OperatorShortcutsModal";
import { OperatorView } from "@/components/OperatorView";
import { PlanColumn } from "@/components/PlanColumn";
import { ProvenanceChip } from "@/components/ProvenanceChip";
import { RefusalCard } from "@/components/RefusalCard";
import { RelevanceDivergencePanel } from "@/components/RelevanceDivergencePanel";
import { RouteRequestAssistant } from "@/components/RouteRequestAssistant";
import { RuleTimeline } from "@/components/RuleTimeline";
import { SensorInspectorDrawer } from "@/components/SensorInspectorDrawer";
import { TouristView } from "@/components/TouristView";
import { VerifyView } from "@/components/VerifyView";
import { useDecisionStream } from "@/hooks/useDecisionStream";
import type { DecisionResponse, Finding, ScenarioResponse, StreamEvent } from "@/lib/contracts";
import { SAMPLE_DECISION, SAMPLE_SCENARIO } from "./fixtures";

vi.mock("next/navigation", () => ({
  usePathname: () => "/operator",
  useRouter: () => ({ push: vi.fn() }),
}));

// Mock react-map-gl so tests without Mapbox token never touch WebGL
vi.mock("react-map-gl", () => ({
  default: ({ children }: { children?: React.ReactNode }) => (
    <div data-testid="mock-mapbox">{children}</div>
  ),
  Marker: ({ children }: { children?: React.ReactNode }) => <div>{children}</div>,
  Source: ({ children }: { children?: React.ReactNode }) => <div>{children}</div>,
  Layer: () => null,
  NavigationControl: () => null,
}));

beforeAll(() => {
  HTMLCanvasElement.prototype.getContext = vi.fn().mockReturnValue({
    clearRect: vi.fn(),
    fillRect: vi.fn(),
    strokeRect: vi.fn(),
    beginPath: vi.fn(),
    arc: vi.fn(),
    fill: vi.fn(),
    stroke: vi.fn(),
    fillText: vi.fn(),
    createLinearGradient: vi.fn().mockReturnValue({ addColorStop: vi.fn() }),
    createRadialGradient: vi.fn().mockReturnValue({ addColorStop: vi.fn() }),
    save: vi.fn(),
    restore: vi.fn(),
    clip: vi.fn(),
    moveTo: vi.fn(),
    lineTo: vi.fn(),
  });
});

class MockEventSource {
  static instances: MockEventSource[] = [];
  listeners = new Map<string, ((event: MessageEvent<string>) => void)[]>();
  closed = false;

  constructor(readonly url: string) {
    MockEventSource.instances.push(this);
  }

  addEventListener(type: string, cb: (event: MessageEvent<string>) => void) {
    const existing = this.listeners.get(type) ?? [];
    existing.push(cb);
    this.listeners.set(type, existing);
  }

  emit(type: string, payload: unknown) {
    const cbs = this.listeners.get(type) ?? [];
    const ev = { data: JSON.stringify(payload) } as MessageEvent<string>;
    for (const cb of cbs) cb(ev);
  }

  emitRaw(type: string) {
    const cbs = this.listeners.get(type) ?? [];
    const ev = {} as MessageEvent<string>;
    for (const cb of cbs) cb(ev);
  }

  close() {
    this.closed = true;
  }
}

function renderWithQuery(ui: React.ReactElement) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(<QueryClientProvider client={client}>{ui}</QueryClientProvider>);
}

beforeEach(() => {
  MockEventSource.instances = [];
  vi.stubGlobal("EventSource", MockEventSource);
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("Provenance & Partial States (FE-REQ-07, 08, 09, 10, 12, 20)", () => {
  it("FE-REQ-09: ProvenanceChip & FindingCard distinguish simulated vs real data", () => {
    const { container: simContainer } = render(
      <FindingCard agent="crowding" finding={SAMPLE_SCENARIO.findings[1]} />,
    );
    expect(simContainer.querySelector("[data-provenance='simulated']")).toHaveTextContent(
      "SIMULATO",
    );
    expect(simContainer.querySelector("article")).toHaveClass("border-dashed");

    const { container: realContainer } = render(
      <FindingCard agent="mobility" finding={SAMPLE_SCENARIO.findings[0]} />,
    );
    expect(realContainer.querySelector("[data-provenance='real']")).toBeInTheDocument();
    expect(realContainer.querySelector("article")).toHaveClass("border-solid");
    expect(realContainer).not.toHaveTextContent("SIMULATO");

    render(<ProvenanceChip variant="unavailable" />);
    expect(screen.getByText("NON DISPONIBILE")).toBeInTheDocument();
  });

  it("FE-REQ-07 & FE-REQ-20: missing finding renders partial unavailable card with refusal reason_code", () => {
    render(
      <FindingCard
        agent="crowding"
        refusal={{
          agent: "crowding",
          reason_code: "missing_occupancy",
          missing_input: ["occupancy_estimates"],
          detail: "nessuna stima nella finestra",
        }}
      />,
    );

    expect(screen.getByText("NON DISPONIBILE")).toBeInTheDocument();
    expect(screen.getByText("missing_occupancy")).toBeInTheDocument();
    expect(screen.getByText("nessuna stima nella finestra")).toBeInTheDocument();
  });

  it("FE-REQ-07 & FE-REQ-20: RefusalCard explicitly declares agent refusal and missing inputs", () => {
    const onSelect = vi.fn();
    render(
      <RefusalCard
        agent="crowding"
        refusal={{
          agent: "crowding",
          reason_code: "insufficient_camera_stream",
          missing_input: ["cam_bagnoli_01", "cam_bagnoli_02"],
          detail: "feed video temporaneamente oscurato",
        }}
        onClick={onSelect}
      />,
    );

    expect(screen.getByTestId("refusal-card-crowding")).toBeInTheDocument();
    expect(screen.getByText("RIFIUTO AGENTE")).toBeInTheDocument();
    expect(screen.getByText("insufficient_camera_stream")).toBeInTheDocument();
    expect(screen.getByText("cam_bagnoli_01")).toBeInTheDocument();
    expect(screen.getByText("feed video temporaneamente oscurato")).toBeInTheDocument();

    fireEvent.click(screen.getByTestId("refusal-card-crowding"));
    expect(onSelect).toHaveBeenCalled();
  });

  it("FE-REQ-08: ConflictPanel renders active conflict with triggering rule and involved agents", () => {
    render(
      <ConflictPanel
        conflict={{
          detected: true,
          description: "La linea 2 ha capienza ridotta ma la domanda verso Bagnoli eccede la soglia",
        }}
        trigger={{
          rule_id: "R2_conflict_route_vs_density",
          agents_involved: ["mobility", "crowding"],
        }}
      />,
    );

    expect(screen.getByTestId("conflict-panel")).toBeInTheDocument();
    expect(screen.getByTestId("conflict-box")).toBeInTheDocument();
    expect(screen.getByText("R2_conflict_route_vs_density")).toBeInTheDocument();
    expect(screen.getByText("mobility")).toBeInTheDocument();
    expect(screen.getByText("crowding")).toBeInTheDocument();
  });

  it("FE-REQ-08: conflict.detected=false shows no_rules banner without errors", () => {
    const noRulesDecision: DecisionResponse = {
      ...SAMPLE_DECISION,
      decision: {
        ...SAMPLE_DECISION.decision,
        conflict: {
          detected: false,
          description: "Nessun conflitto attivo sulle soglie configurate",
        },
      },
    };

    render(
      <DecisionHeader
        decisionId={noRulesDecision.decision_id}
        decision={noRulesDecision.decision}
        findings={SAMPLE_SCENARIO.findings}
        onRepeat={vi.fn()}
        repeatState={{ status: "idle" }}
      />,
    );

    expect(screen.getByText(/Nessuna regola scattata/i)).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("FE-REQ-10 & FE-REQ-12: MapPanel highlights no zone when zone_id missing and works without token", () => {
    const findingsWithoutZone: Finding[] = [
      {
        ...SAMPLE_SCENARIO.findings[0]!,
        content: { congestion: 0.5 },
      },
    ];

    render(
      <MapPanel
        findings={findingsWithoutZone}
        vehiclePositions={SAMPLE_SCENARIO.vehicle_positions}
      />,
    );

    expect(screen.getByTestId("map-not-configured")).toBeInTheDocument();
    expect(screen.getByTestId("map-zones-text")).toHaveTextContent(
      "Nessuna zona evidenziata dai finding.",
    );
    expect(screen.getByTestId("map-vehicles-text")).toHaveTextContent("ANM-2231");
  });

  it("FE-REQ-12: MapPanel renders deterministic SVG fallback and supports zone selection binding", () => {
    const onSelectZone = vi.fn();
    render(
      <MapPanel
        findings={SAMPLE_SCENARIO.findings}
        vehiclePositions={SAMPLE_SCENARIO.vehicle_positions}
        selectedZoneId="Z_BAGNOLI"
        onSelectZone={onSelectZone}
      />,
    );

    expect(screen.getByLabelText("Mappa vettoriale Napoli")).toBeInTheDocument();
    expect(screen.getByTestId("map-engine-badge")).toHaveTextContent(/svg locale/i);

    const zoneBadge = screen.getByText("Bagnoli");
    fireEvent.click(zoneBadge);
    expect(onSelectZone).toHaveBeenCalled();
  });
});

describe("Stream SSE & RuleTimeline (FE-REQ-13..17, 30)", () => {
  function StreamHarness({ scenarioId }: { scenarioId: string }) {
    const stream = useDecisionStream(scenarioId, true);
    return <RuleTimeline steps={stream.steps} status={stream.status} onRetry={stream.reconnect} />;
  }

  it("FE-REQ-13, 15, 16, 17, 30: SSE opens right URL, shows fired=false reason, resets on reconnect, degrades cleanly", async () => {
    render(<StreamHarness scenarioId="bagnoli" />);

    expect(MockEventSource.instances).toHaveLength(1);
    const es1 = MockEventSource.instances[0]!;
    expect(es1.url).toContain("/api/v1/scenario/bagnoli/stream");

    act(() => {
      es1.emit("rule_evaluated", {
        rule_id: "R1_line2_crowding",
        agents: ["mobility", "crowding"],
        fired: true,
        reason: "densita' 0.91 oltre soglia 0.85",
      });
      es1.emit("rule_evaluated", {
        rule_id: "R3_weather_capacity",
        agents: ["context", "crowding"],
        fired: false,
        reason: "heavy_rain assente",
      });
    });

    await waitFor(() => {
      expect(screen.getByTestId("rule-row-R3_weather_capacity")).toHaveTextContent(
        "heavy_rain assente",
      );
    });
    expect(screen.getByRole("list")).toHaveAttribute("aria-live", "polite");

    // Simulate stream drop -> degraded
    act(() => {
      es1.emitRaw("error");
    });
    await waitFor(() => {
      expect(screen.getByText("Stream non disponibile")).toBeInTheDocument();
    });
    expect(es1.closed).toBe(true);

    // Retry reconnect clears steps before re-opening (no duplication)
    fireEvent.click(screen.getByText("Riprova stream"));
    expect(MockEventSource.instances).toHaveLength(2);
    const es2 = MockEventSource.instances[1]!;
    act(() => {
      es2.emit("rule_evaluated", {
        rule_id: "R1_line2_crowding",
        agents: ["mobility", "crowding"],
        fired: true,
        reason: "densita' 0.91 oltre soglia 0.85",
      });
    });

    await waitFor(() => {
      expect(screen.getAllByTestId("rule-row-R1_line2_crowding")).toHaveLength(1);
    });
  });

  it("FE-REQ-14 & FE-REQ-16: DiscardRecalcPanel displays discarded option, rationale and adopted recalculation", () => {
    render(<DiscardRecalcPanel decision={SAMPLE_DECISION.decision} locale="it" />);

    expect(screen.getByTestId("discard-recalc-panel")).toBeInTheDocument();
    expect(screen.getByText("Opzione scartata")).toBeInTheDocument();
    expect(screen.getByText("Ricalcolo vincente")).toBeInTheDocument();
    expect(screen.getByText("ADOTTATO")).toBeInTheDocument();
    expect(screen.getByText(/attraversa la zona satura/i)).toBeInTheDocument();
  });
});

describe("Target Isolation, Ordering & Limits (FE-REQ-21..26)", () => {
  it("FE-REQ-21 & FE-REQ-24: TouristView hides reasoning_log/rationale and switches IT/EN with lang attr", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.includes("/scenario/")) {
        return new Response(JSON.stringify(SAMPLE_SCENARIO), { status: 200 });
      }
      return new Response(JSON.stringify(SAMPLE_DECISION), { status: 200 });
    });

    renderWithQuery(<TouristView scenarioId="bagnoli" />);

    await waitFor(() => {
      expect(screen.getByTestId("primary-message-text")).toHaveTextContent(
        "Linea R2 da Fuorigrotta, circa 20 minuti.",
      );
    });

    // Reasoning log and rationale must never appear
    expect(document.body.textContent).not.toContain("priorita' sicurezza applicata");
    expect(document.body.textContent).not.toContain("P2 tempo di percorrenza");
    expect(document.body.textContent).not.toContain("3f9a51c7e2b84d06");

    // Switch to English
    fireEvent.click(screen.getByTestId("lang-en"));
    expect(screen.getByTestId("primary-message-text")).toHaveTextContent(
      "Line R2 from Fuorigrotta, about 20 minutes.",
    );
    expect(screen.getByTestId("primary-message-text")).toHaveAttribute("lang", "en");
  });

  it("FE-REQ-21: CitizenView shows qualitative zone status and hides confidence/reasoning_log", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.includes("/scenario/")) {
        return new Response(JSON.stringify(SAMPLE_SCENARIO), { status: 200 });
      }
      return new Response(JSON.stringify(SAMPLE_DECISION), { status: 200 });
    });

    renderWithQuery(<CitizenView scenarioId="bagnoli" />);

    await waitFor(() => {
      expect(screen.getByTestId("citizen-zone-status")).toHaveTextContent("Zona molto affollata");
    });
    expect(document.body.textContent).not.toContain("priorita' sicurezza applicata");
    expect(document.body.textContent).not.toContain("0.91");
  });

  it("FE-REQ-22: PlanColumn follows relevance.targets[target].order strictly", () => {
    const multiDecision: DecisionResponse = {
      ...SAMPLE_DECISION,
      decision: {
        ...SAMPLE_DECISION.decision,
        plan: [
          { priority: 1, action: "Prima azione operatore", target: "operator", rationale: "R1" },
          { priority: 2, action: "Seconda azione operatore", target: "operator", rationale: "R2" },
        ],
      },
      relevance: {
        ...SAMPLE_DECISION.relevance,
        targets: {
          ...SAMPLE_DECISION.relevance.targets,
          operator: {
            order: [1, 0],
            items: [],
          },
        },
      },
    };

    render(
      <PlanColumn
        target="operator"
        plan={multiDecision.decision.plan}
        targetRelevance={multiDecision.relevance.targets.operator}
        rounding={4}
        narrative={multiDecision.narrative}
      />,
    );

    const cards = screen.getAllByTestId("plan-card-operator");
    expect(cards[0]).toHaveTextContent("Seconda azione operatore");
    expect(cards[1]).toHaveTextContent("Prima azione operatore");
  });

  it("FE-REQ-23 & FE-REQ-25: ChatPanel falls back to PlanItem.action when narrative.items is empty and caps tourist to 3 items", () => {
    const fiveTouristDecision: DecisionResponse = {
      ...SAMPLE_DECISION,
      decision: {
        ...SAMPLE_DECISION.decision,
        plan: [
          { priority: 1, action: "Azione T1 (10 min)", target: "tourist", rationale: "r1" },
          { priority: 2, action: "Azione T2", target: "tourist", rationale: "r2" },
          { priority: 3, action: "Azione T3", target: "tourist", rationale: "r3" },
          { priority: 4, action: "Azione T4", target: "tourist", rationale: "r4" },
          { priority: 5, action: "Azione T5", target: "tourist", rationale: "r5" },
        ],
      },
      relevance: {
        ...SAMPLE_DECISION.relevance,
        targets: {
          ...SAMPLE_DECISION.relevance.targets,
          tourist: {
            order: [0, 1, 2, 3, 4],
            items: [],
          },
        },
      },
      narrative: {
        mode: "off",
        items: [],
      },
    };

    render(
      <ChatPanel
        target="tourist"
        findings={SAMPLE_SCENARIO.findings}
        decisionResponse={fiveTouristDecision}
        locale="it"
      />,
    );

    expect(screen.getByTestId("primary-message-text")).toHaveTextContent("Azione T1 (10 min)");
    expect(screen.getByText("testo da template")).toBeInTheDocument();
    expect(screen.getAllByTestId("alternative-item")).toHaveLength(2);
    expect(screen.getByTestId("more-actions-notice")).toHaveTextContent("Altre 2 azioni");
    expect(document.body.textContent).not.toContain("Azione T4");
  });

  it("FE-REQ-26: OperatorView repeat button checks determinism across two POST /decision calls", async () => {
    let decisionCalls = 0;
    const partialScenario: ScenarioResponse = {
      ...SAMPLE_SCENARIO,
      findings: SAMPLE_SCENARIO.findings.slice(0, 2),
    };

    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.includes("/scenario/")) {
        return new Response(JSON.stringify(partialScenario), { status: 200 });
      }
      decisionCalls += 1;
      return new Response(JSON.stringify(SAMPLE_DECISION), { status: 200 });
    });

    renderWithQuery(<OperatorView scenarioId="bagnoli" />);

    await waitFor(() => {
      expect(screen.getByTestId("repeat-decision-button")).toBeInTheDocument();
    });

    // Partial scenario shows missing card for context
    expect(screen.getByTestId("finding-card-context")).toHaveAttribute(
      "data-finding-state",
      "missing",
    );

    fireEvent.click(screen.getByTestId("repeat-decision-button"));

    await waitFor(() => {
      expect(screen.getByTestId("repeat-result")).toHaveTextContent("same3f9a51c7e2b84d06");
    });
    expect(decisionCalls).toBe(3); // 1 initial + 2 for repeat comparison
  });

  it("FE-REQ-26 & FE-REQ-28: VerifyView renders deterministic ID, replay check and declared limits", async () => {
    vi.spyOn(globalThis, "fetch").mockImplementation(async (input) => {
      const url = String(input);
      if (url.includes("/scenario/")) {
        return new Response(JSON.stringify(SAMPLE_SCENARIO), { status: 200 });
      }
      return new Response(JSON.stringify(SAMPLE_DECISION), { status: 200 });
    });

    renderWithQuery(<VerifyView scenarioId="bagnoli" />);

    await waitFor(() => {
      expect(screen.getByTestId("verify-decision-id")).toHaveTextContent(SAMPLE_DECISION.decision_id);
    });

    expect(screen.getByTestId("verify-limits-section")).toBeInTheDocument();
    expect(screen.getByTestId("verify-metrics-section")).toBeInTheDocument();

    fireEvent.click(screen.getByTestId("verify-replay-button"));

    await waitFor(() => {
      expect(screen.getByTestId("verify-replay-result")).toHaveTextContent(/IDEMPOTENZA CONFERMATA/i);
    });

    // Anti-tamper avalanche test verification
    fireEvent.click(screen.getByTestId("verify-tamper-button"));
    expect(screen.getByTestId("verify-tamper-result")).toHaveTextContent(/EFFETTO VALANGA/i);
    expect(screen.getByTestId("verify-tamper-result")).toHaveTextContent("e47c1a89d302b55f");
  });

  it("F5: GroundedQueryPanel answers strictly from cited fields without hallucinations", () => {
    render(
      <GroundedQueryPanel
        decisionResponse={SAMPLE_DECISION}
        findings={SAMPLE_SCENARIO.findings}
        locale="it"
      />,
    );

    expect(screen.getByTestId("grounded-query-panel")).toBeInTheDocument();

    // Query 1: Covered intent (conflict)
    fireEvent.change(screen.getByTestId("grounded-query-input"), {
      target: { value: "Perché hai scartato la linea?" },
    });
    fireEvent.click(screen.getByTestId("grounded-query-submit"));

    expect(screen.getByTestId("grounded-query-result")).toBeInTheDocument();
    expect(screen.getByTestId("grounded-answer-text")).toHaveTextContent(/scartata/i);
    expect(screen.getByTestId("grounded-citations")).toHaveTextContent("decision.conflict");

    // Query 2: Out of bounds query
    fireEvent.change(screen.getByTestId("grounded-query-input"), {
      target: { value: "Chi vincerà la partita di calcio?" },
    });
    fireEvent.click(screen.getByTestId("grounded-query-submit"));

    expect(screen.getByTestId("grounded-answer-text")).toHaveTextContent(/Dato non disponibile nei campi verificati/i);
  });

  it("F6: RelevanceDivergencePanel computes pairwise order inversions between targets", () => {
    render(
      <RelevanceDivergencePanel
        relevance={SAMPLE_DECISION.relevance}
        plan={SAMPLE_DECISION.decision.plan}
      />,
    );

    expect(screen.getByTestId("relevance-divergence-panel")).toBeInTheDocument();
    expect(screen.getByTestId("divergence-op-tour")).toBeInTheDocument();
    expect(screen.getByTestId("divergence-tour-cit")).toBeInTheDocument();
  });

  it("F9: RouteRequestAssistant parses natural language query and handles clarification", async () => {
    render(<RouteRequestAssistant theme="light" locale="it" />);

    expect(screen.getByTestId("route-request-assistant")).toBeInTheDocument();

    // Click sample query chip
    const sampleChip = screen.getByText("Da Piazza Garibaldi a Bagnoli alle 18");
    fireEvent.click(sampleChip);

    await waitFor(() => {
      expect(screen.getByText(/Richiesta Risolta con Successo/i)).toBeInTheDocument();
      expect(screen.getByText("Piazza Garibaldi")).toBeInTheDocument();
      expect(screen.getByText("Bagnoli")).toBeInTheDocument();
    });

    // Test out-of-bounds input
    const outChip = screen.getByText("Da Roma a Milano alle 12");
    fireEvent.click(outChip);

    await waitFor(() => {
      expect(screen.getByText(/Richiesta di Chiarimento/i)).toBeInTheDocument();
    });
  });

  it("F10: MapPanel supports zoom controls and layer toggling without errors", () => {
    render(
      <MapPanel
        findings={SAMPLE_SCENARIO.findings}
        vehiclePositions={SAMPLE_SCENARIO.vehicle_positions}
        theme="dark"
        locale="it"
      />,
    );

    expect(screen.getByTestId("map-panel")).toBeInTheDocument();
    expect(screen.getByTitle("Zoom in")).toBeInTheDocument();
    expect(screen.getByTitle("Zoom out")).toBeInTheDocument();
    expect(screen.getByTitle("Mostra / Nascondi zone")).toBeInTheDocument();
    expect(screen.getByTitle("Mostra / Nascondi mezzi")).toBeInTheDocument();

    // Toggle layer
    fireEvent.click(screen.getByTitle("Mostra / Nascondi zone"));
    fireEvent.click(screen.getByTitle("Zoom in"));
    expect(screen.getByTitle("Reset zoom")).toHaveTextContent("125%");
  });

  it("F11: RuleTimeline filters stream events by category", () => {
    const mockSteps: StreamEvent[] = [
      { event: "phase", data: { phase: "start", index: 0 } },
      {
        event: "rule_evaluated",
        data: { rule_id: "R1_line2_crowding", agents: ["mobility"], fired: true, reason: "density" },
      },
      {
        event: "conflict_detected",
        data: { description: "Conflitto rotta", zone_id: "Z_BAGNOLI" },
      },
    ];

    render(<RuleTimeline steps={mockSteps} status="done" locale="it" />);

    expect(screen.getByText("Tutti (3)")).toBeInTheDocument();
    expect(screen.getByText("Regole (1)")).toBeInTheDocument();
    expect(screen.getByText("Conflitti (1)")).toBeInTheDocument();

    // Click Regole filter
    fireEvent.click(screen.getByText("Regole (1)"));
    expect(screen.getByText(/density/i)).toBeInTheDocument();
  });

  it("F12: SensorInspectorDrawer renders hardware telemetry for Intel RealSense and YOLOv11", () => {
    const handleClose = vi.fn();
    render(
      <SensorInspectorDrawer
        isOpen={true}
        onClose={handleClose}
        initialAgent="crowding"
        findings={SAMPLE_SCENARIO.findings}
        vehiclePositions={SAMPLE_SCENARIO.vehicle_positions}
        locale="it"
      />,
    );

    expect(screen.getByRole("dialog", { name: /Ispezione Telemetria Sensori Hardware/i })).toBeInTheDocument();
    expect(screen.getByText(/Intel RealSense™ D435i/i)).toBeInTheDocument();
    expect(screen.getByText(/Ultralytics YOLOv11/i)).toBeInTheDocument();
    expect(screen.getAllByText("142")[0]).toBeInTheDocument();
    expect(screen.getAllByText("0.91 p/m²")[0]).toBeInTheDocument();

    // Switch to mobility tab
    fireEvent.click(screen.getByText(/Mobilità \(ANM\/GTFS\)/i));
    expect(screen.getByText(/OTP 2.x MULTIMODAL CORE/i)).toBeInTheDocument();
    expect(screen.getByText("ANM-2231")).toBeInTheDocument();

    // Switch to context tab
    fireEvent.click(screen.getByText(/Contesto \(Meteo\/Radar\)/i));
    expect(screen.getByText(/ALLERTA ARANCIONE/i)).toBeInTheDocument();
    expect(screen.getByText("24.5 mm/h")).toBeInTheDocument();

    // Close button
    fireEvent.click(screen.getByLabelText(/Chiudi ispezione/i));
    expect(handleClose).toHaveBeenCalled();
  });

  it("F13: OperatorShortcutsModal renders keyboard shortcut reference", () => {
    const handleClose = vi.fn();
    render(<OperatorShortcutsModal isOpen={true} onClose={handleClose} />);

    expect(screen.getByRole("dialog", { name: /Scorciatoie da Tastiera per Sala Operativa/i })).toBeInTheDocument();
    expect(screen.getByText(/Ripeti Verifica Deterministica/i)).toBeInTheDocument();
    expect(screen.getByText(/Apri Ispezione Telemetria Sensori/i)).toBeInTheDocument();

    fireEvent.click(screen.getByLabelText(/Chiudi guida scorciatoie/i));
    expect(handleClose).toHaveBeenCalled();
  });

  it("F14: LiveVisionFeed renders interactive canvas and dynamic headcount/density slider", () => {
    render(<LiveVisionFeed initialHeadcount={142} areaSqm={150.0} alarmThreshold={0.85} />);

    expect(screen.getByTestId("live-vision-feed")).toBeInTheDocument();
    expect(screen.getByText(/FEED OTTICO REALSENSE & INFERENZA YOLOv11/i)).toBeInTheDocument();
    expect(screen.getByText("0.95 p/m²")).toBeInTheDocument();
    expect(screen.getByText(/ALLARME/i)).toBeInTheDocument();

    // Toggle view mode to RGB
    fireEvent.click(screen.getByText("RGB + YOLO"));
    expect(screen.getByText("RGB + YOLO")).toBeInTheDocument();

    // Toggle view mode to Depth
    fireEvent.click(screen.getByText("Depth (z16)"));
    expect(screen.getByText("Depth (z16)")).toBeInTheDocument();

    // Adjust slider down to nominal count (e.g. 50 people -> 0.33 p/m²)
    const slider = screen.getByLabelText(/Regola conteggio persone simulate/i);
    fireEvent.change(slider, { target: { value: "50" } });
    expect(screen.getByText("0.33 p/m²")).toBeInTheDocument();
    expect(screen.getByText("NOMINALE")).toBeInTheDocument();
  });
});
