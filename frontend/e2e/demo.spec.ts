import { expect, test } from "@playwright/test";
import { SAMPLE_DECISION, SAMPLE_SCENARIO } from "../tests/fixtures";

const SSE_BODY = [
  `event: start\nid: 1\ndata: ${JSON.stringify({ scenario_id: "bagnoli", contract_version: "1.0.0" })}\n\n`,
  `event: phase\nid: 2\ndata: ${JSON.stringify({ phase: "regole", index: 1 })}\n\n`,
  `event: rule_evaluated\nid: 3\ndata: ${JSON.stringify({ rule_id: "R1_line2_crowding", agents: ["mobility", "crowding"], fired: true, reason: "densita' 0.91 oltre soglia 0.85" })}\n\n`,
  `event: rule_evaluated\nid: 4\ndata: ${JSON.stringify({ rule_id: "R3_weather_capacity", agents: ["context", "crowding"], fired: false, reason: "soglia meteo non superata" })}\n\n`,
  `event: decision\nid: 5\ndata: ${JSON.stringify({ decision_id: SAMPLE_DECISION.decision_id, contract_version: "1.0.0" })}\n\n`,
].join("");

test("Demo E2E: / -> /operator (3-step render, 3 plan targets, repeat determinism)", async ({
  page,
}) => {
  await page.route("**/api/v1/scenario/bagnoli", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(SAMPLE_SCENARIO),
    });
  });

  await page.route("**/api/v1/decision", async (route) => {
    await new Promise((r) => setTimeout(r, 150));
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(SAMPLE_DECISION),
    });
  });

  await page.route("**/api/v1/scenario/bagnoli/stream", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "text/event-stream; charset=utf-8",
      body: SSE_BODY,
    });
  });

  await page.goto("/");
  await expect(page.getByTestId("role-card-operator")).toBeVisible();
  await expect(page.getByTestId("role-card-tourist")).toBeVisible();
  await expect(page.getByTestId("role-card-citizen")).toBeVisible();

  await page.getByTestId("role-card-operator").click();

  // FE-REQ-06: Map and finding cards visible before decision finishes
  await expect(page.getByTestId("map-panel")).toBeVisible();
  await expect(page.getByTestId("finding-card-mobility")).toBeVisible();
  await expect(page.getByTestId("finding-card-crowding")).toBeVisible();
  await expect(page.getByTestId("finding-card-context")).toBeVisible();

  // Decision and 3 target plan columns appear
  await expect(page.getByTestId("decision-header")).toBeVisible();
  await expect(page.getByTestId("plan-column-operator")).toBeVisible();
  await expect(page.getByTestId("plan-column-tourist")).toBeVisible();
  await expect(page.getByTestId("plan-column-citizen")).toBeVisible();
  await expect(page.getByTestId("reasoning-list")).toBeVisible();

  // Timeline shows SSE steps including non-fired rule
  await expect(page.getByTestId("rule-row-R1_line2_crowding")).toBeVisible();
  await expect(page.getByTestId("rule-row-R3_weather_capacity")).toBeVisible();

  // Determinism repeat check
  await page.getByTestId("repeat-decision-button").click();
  await expect(page.getByTestId("repeat-result")).toContainText("same");
  await expect(page.getByTestId("repeat-result")).toContainText(SAMPLE_DECISION.decision_id);
});

test("Tourist and Citizen routes respect privacy and bilingual controls", async ({ page }) => {
  await page.route("**/api/v1/scenario/bagnoli", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(SAMPLE_SCENARIO),
    });
  });
  await page.route("**/api/v1/decision", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(SAMPLE_DECISION),
    });
  });

  await page.goto("/tourist");
  await expect(page.getByTestId("primary-message-text")).toContainText(
    "Linea R2 da Fuorigrotta, circa 20 minuti.",
  );
  await page.getByTestId("lang-en").click();
  await expect(page.getByTestId("primary-message-text")).toContainText(
    "Line R2 from Fuorigrotta, about 20 minutes.",
  );
  await expect(page.getByTestId("reasoning-list")).toHaveCount(0);

  await page.goto("/citizen");
  await expect(page.getByTestId("citizen-zone-status")).toContainText("Zona molto affollata");
  await expect(page.getByTestId("reasoning-list")).toHaveCount(0);
});

test("Unknown scenario renders empty state with link to known scenarios", async ({ page }) => {
  await page.route("**/api/v1/scenario/sconosciuto", async (route) => {
    await route.fulfill({
      status: 404,
      contentType: "application/problem+json",
      body: JSON.stringify({
        type: "https://napoli-agentic-city/errors/scenario_not_found",
        title: "Scenario non trovato",
        status: 404,
        code: "scenario_not_found",
        detail: "Lo scenario sconosciuto non esiste",
        instance: "/api/v1/scenario/sconosciuto",
      }),
    });
  });

  await page.goto("/operator?scenario=sconosciuto");
  await expect(page.getByText("Scenario non trovato")).toBeVisible();
  await expect(page.getByRole("link", { name: "bagnoli" })).toBeVisible();
});
