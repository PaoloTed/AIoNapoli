import fs from "node:fs";
import path from "node:path";
import { afterEach, describe, expect, it, vi } from "vitest";
import { getScenario, mapProblemToPresentation, postDecision } from "@/lib/api";
import {
  DECISION_KEYS,
  EXPECTED_CONTRACT_VERSION,
  FINDING_KEYS,
  congestion,
  decisionSchema,
  density,
  expectedAttendance,
  findingSchema,
  heavyRain,
  zoneId,
  type Finding,
} from "@/lib/contracts";
import { SAMPLE_DECISION, SAMPLE_SCENARIO } from "./fixtures";

afterEach(() => {
  vi.restoreAllMocks();
});

describe("Contracts & Accessors (FE-REQ-01..04)", () => {
  it("FE-REQ-01: Finding has 9 exact keys and Decision has 6 exact keys", () => {
    expect(FINDING_KEYS).toHaveLength(9);
    expect(DECISION_KEYS).toHaveLength(6);

    const parsedFinding = findingSchema.parse(SAMPLE_SCENARIO.findings[0]);
    expect(Object.keys(parsedFinding).sort()).toEqual([...FINDING_KEYS].sort());

    const parsedDecision = decisionSchema.parse(SAMPLE_DECISION.decision);
    expect(Object.keys(parsedDecision).sort()).toEqual([...DECISION_KEYS].sort());
  });

  it("FE-REQ-02: Zod strict schemas fail on unknown keys", () => {
    const findingWithExtra = {
      ...SAMPLE_SCENARIO.findings[0],
      invented_field: "bad",
    };
    expect(() => findingSchema.parse(findingWithExtra)).toThrow();

    const decisionWithExtra = {
      ...SAMPLE_DECISION.decision,
      extra_score: 0.99,
    };
    expect(() => decisionSchema.parse(decisionWithExtra)).toThrow();
  });

  it("FE-REQ-03: content accessors return undefined when fields are missing", () => {
    const emptyFinding: Finding = {
      agent: "crowding",
      type: "density_alert",
      content: {},
      confidence: 0.8,
      severity: "medium",
      source_id: "ir_sensors",
      data_reference: "occupancy:2026-11-14T17:40:00+01:00",
      is_simulated: true,
      timestamp: "2026-11-14T17:40:00+01:00",
    };

    expect(density(emptyFinding)).toBeUndefined();
    expect(congestion(emptyFinding)).toBeUndefined();
    expect(zoneId(emptyFinding)).toBeUndefined();
    expect(heavyRain(emptyFinding)).toBeUndefined();
    expect(expectedAttendance(emptyFinding)).toBeUndefined();
  });

  it("FE-REQ-04: mismatched contract_version flags contractMismatch without crashing on unknown keys", async () => {
    const mismatchedPayload = {
      ...SAMPLE_SCENARIO,
      contract_version: "2.0.0",
      future_extra_root_field: "ignored",
    };

    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify(mismatchedPayload), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    const res = await getScenario("bagnoli");
    expect(res.contractMismatch).toBe(true);
    expect(res.contractVersion).toBe("2.0.0");
    expect(res.data.scenario_id).toBe("bagnoli");
    expect(EXPECTED_CONTRACT_VERSION).toBe("1.0.0");
  });

  it("FE-REQ-02 over HTTP: matching contract_version rejects unknown keys", async () => {
    const badPayload = {
      ...SAMPLE_DECISION,
      unexpected_envelope_key: true,
    };

    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response(JSON.stringify(badPayload), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );

    await expect(postDecision({ scenario_id: "bagnoli" })).rejects.toThrow();
  });
});

describe("Error Mapping & Sanitization (FE-REQ-18..20)", () => {
  it("FE-REQ-18: every problem+json code has a declared presentation", () => {
    const codes = [
      "invalid_finding",
      "agent_mismatch",
      "missing_finding",
      "agent_refusal",
      "scenario_not_found",
      "upstream_timeout",
      "upstream_unavailable",
      "llm_unavailable",
      "config_invalid",
      "internal_error",
    ] as const;

    for (const code of codes) {
      const mapped = mapProblemToPresentation({
        type: `https://napoli-agentic-city/errors/${code}`,
        title: code,
        status: code === "scenario_not_found" ? 404 : code === "config_invalid" ? 500 : 422,
        code,
        detail: "detail",
        instance: "/api/v1/decision",
        ...(code === "invalid_finding" ? { field: "content.density" } : {}),
        ...(code === "agent_refusal"
          ? {
              refusal: {
                agent: "crowding",
                reason_code: "missing_occupancy",
                missing_input: ["occupancy_estimates"],
                detail: "nessuna stima",
              },
            }
          : {}),
      });
      expect(mapped.code).toBe(code);
      expect(mapped.placement).toBeTruthy();
      if (code === "config_invalid") {
        expect(mapped.canRetry).toBe(false);
      }
      if (code === "missing_finding") {
        expect(mapped.hidePlan).toBe(true);
      }
    }
  });

  it("FE-REQ-19: raw 500 stack traces are sanitized and never exposed", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      new Response("Traceback (most recent call last): ValueError at app/main.py:42", {
        status: 500,
        headers: { "Content-Type": "text/plain" },
      }),
    );

    try {
      await getScenario("bagnoli");
      expect.unreachable("Should have thrown ApiError");
    } catch (err) {
      expect((err as { problem: { code: string; detail: string } }).problem.code).toBe(
        "internal_error",
      );
      expect((err as { problem: { detail: string } }).problem.detail).not.toContain("Traceback");
    }
  });
});

describe("Hygiene & Boundaries (FE-REQ-31, FE-REQ-32)", () => {
  it("FE-REQ-31 & FE-REQ-32: no secrets and no external API fetches in client source", () => {
    const root = path.resolve(__dirname, "..");
    const dirs = ["app", "components", "hooks", "lib"];
    const files: string[] = [];

    const walk = (dir: string) => {
      for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
        const full = path.join(dir, entry.name);
        if (entry.isDirectory()) walk(full);
        else if (/\.(ts|tsx)$/.test(entry.name)) files.push(full);
      }
    };

    for (const d of dirs) walk(path.join(root, d));

    for (const file of files) {
      const content = fs.readFileSync(file, "utf8");
      expect(content).not.toMatch(/\b(pk\.|sk\.)[A-Za-z0-9_-]{8,}/);
      // Any fetch() call must live only in lib/api.ts
      if (/\bfetch\s*\(/.test(content)) {
        expect(path.basename(file)).toBe("api.ts");
      }
    }
  });
});
