import { chromium } from "playwright";
import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const outDir = path.resolve(__dirname, "../../ricerche/tests/frontend-verifica/gallery");
if (!fs.existsSync(outDir)) {
  fs.mkdirSync(outDir, { recursive: true });
}

async function capture() {
  console.log("Launching Chromium...");
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext();

  // 0. Home Page at 1440x900
  console.log("Capturing Home...");
  const homePage = await context.newPage();
  await homePage.setViewportSize({ width: 1440, height: 900 });
  await homePage.goto("http://localhost:3000/", { waitUntil: "networkidle" });
  await homePage.waitForTimeout(1000);
  await homePage.screenshot({ path: path.join(outDir, "00_home_1440.png"), fullPage: true });

  // 0b. Home Page Route Request Query
  console.log("Testing Home Route Request Query...");
  const sampleChip = homePage.locator("button:has-text('Da Piazza Garibaldi a Bagnoli alle 18')");
  if (await sampleChip.count() > 0) {
    await sampleChip.click();
    await homePage.waitForTimeout(800);
    const assistant = homePage.locator("[data-testid='route-request-assistant']");
    await assistant.scrollIntoViewIfNeeded();
    await assistant.screenshot({ path: path.join(outDir, "00b_home_route_query.png") });
  }
  await homePage.close();

  // 1. Operator at 1440x900
  console.log("Capturing Operator...");
  const opPage = await context.newPage();
  await opPage.setViewportSize({ width: 1440, height: 900 });
  await opPage.goto("http://localhost:3000/operator?scenario=bagnoli", { waitUntil: "networkidle" });
  await opPage.waitForTimeout(1000);
  await opPage.screenshot({ path: path.join(outDir, "01_operator_1440.png"), fullPage: true });

  // 1b. Operator interactive click on finding card to test zone binding
  console.log("Testing card click binding...");
  const firstCard = opPage.locator("[data-testid='finding-card-mobility']");
  if (await firstCard.count() > 0) {
    await firstCard.click();
    await opPage.waitForTimeout(500);
    await opPage.screenshot({ path: path.join(outDir, "01b_operator_zone_highlighted.png") });
  }

  // 1c. Operator grounded query test
  console.log("Testing grounded query...");
  const queryInput = opPage.locator("[data-testid='grounded-query-input']");
  const querySubmit = opPage.locator("[data-testid='grounded-query-submit']");
  if (await queryInput.count() > 0) {
    await queryInput.fill("Perché hai scartato la linea?");
    await querySubmit.click();
    await opPage.waitForTimeout(500);
    const queryPanel = opPage.locator("[data-testid='grounded-query-panel']");
    await queryPanel.scrollIntoViewIfNeeded();
    await opPage.waitForTimeout(300);
    await queryPanel.screenshot({ path: path.join(outDir, "01c_operator_grounded_answer.png") });
  }

  // 1d. Operator Sensor & Telemetry Inspector Drawer (RealSense / YOLOv11)
  console.log("Testing Sensor Inspector Drawer...");
  const inspectBtn = opPage.locator("[data-testid='sensor-inspector-trigger']");
  if (await inspectBtn.count() > 0) {
    await inspectBtn.click();
    await opPage.waitForSelector("[data-testid='sensor-inspector-drawer']", { timeout: 3000 });
    await opPage.waitForTimeout(500);
    await opPage.screenshot({ path: path.join(outDir, "01d_operator_sensor_inspector.png"), fullPage: true });
    // Close drawer via Escape key
    await opPage.keyboard.press("Escape");
    await opPage.waitForTimeout(400);
  }

  // 1e. Operator Keyboard Shortcuts Modal
  console.log("Testing Keyboard Shortcuts Modal...");
  const shortcutsBtn = opPage.locator("[data-testid='shortcuts-modal-trigger']");
  if (await shortcutsBtn.count() > 0) {
    await shortcutsBtn.click();
    await opPage.waitForSelector("[data-testid='shortcuts-modal']", { timeout: 3000 });
    await opPage.waitForTimeout(500);
    await opPage.screenshot({ path: path.join(outDir, "01e_operator_shortcuts_modal.png"), fullPage: true });
    await opPage.keyboard.press("Escape");
    await opPage.waitForTimeout(300);
  }

  await opPage.close();

  // 2. Tourist at 390x844 (iPhone 14 standard)
  console.log("Capturing Tourist (Mobile)...");
  const tourPage = await context.newPage();
  await tourPage.setViewportSize({ width: 390, height: 844 });
  await tourPage.goto("http://localhost:3000/tourist?scenario=bagnoli", { waitUntil: "networkidle" });
  await tourPage.waitForTimeout(1000);
  await tourPage.screenshot({ path: path.join(outDir, "02_tourist_mobile_390.png"), fullPage: true });

  // 2b. Tourist English toggle
  const enButton = tourPage.locator("[data-testid='lang-en']");
  if (await enButton.count() > 0) {
    await enButton.click();
    await tourPage.waitForTimeout(500);
    await tourPage.screenshot({ path: path.join(outDir, "02b_tourist_english_390.png"), fullPage: true });
  }
  await tourPage.close();

  // 3. Citizen at 390x844
  console.log("Capturing Citizen (Mobile)...");
  const citPage = await context.newPage();
  await citPage.setViewportSize({ width: 390, height: 844 });
  await citPage.goto("http://localhost:3000/citizen?scenario=bagnoli", { waitUntil: "networkidle" });
  await citPage.waitForTimeout(1000);
  await citPage.screenshot({ path: path.join(outDir, "03_citizen_mobile_390.png"), fullPage: true });
  await citPage.close();

  // 4. Verify at 1440x900
  console.log("Capturing Verify...");
  const verPage = await context.newPage();
  await verPage.setViewportSize({ width: 1440, height: 900 });
  await verPage.goto("http://localhost:3000/verify?scenario=bagnoli", { waitUntil: "networkidle" });
  await verPage.waitForTimeout(1000);
  await verPage.screenshot({ path: path.join(outDir, "04_verify_initial.png"), fullPage: true });

  // 4b. Verify Replay Click
  console.log("Testing Verify Replay...");
  const replayBtn = verPage.locator("[data-testid='verify-replay-button']");
  if (await replayBtn.count() > 0) {
    await replayBtn.click();
    await verPage.waitForSelector("[data-testid='verify-replay-result']", { timeout: 5000 });
    await verPage.screenshot({ path: path.join(outDir, "04b_verify_idempotence_confirmed.png"), fullPage: true });
  }

  // 4c. Verify Anti-Tamper Avalanche Test Click
  console.log("Testing Verify Anti-Tamper...");
  const tamperBtn = verPage.locator("[data-testid='verify-tamper-button']");
  if (await tamperBtn.count() > 0) {
    await tamperBtn.click();
    await verPage.waitForSelector("[data-testid='verify-tamper-result']", { timeout: 5000 });
    await verPage.screenshot({ path: path.join(outDir, "04c_verify_tamper_avalanche.png"), fullPage: true });
  }
  await verPage.close();

  await browser.close();
  console.log("All screenshots successfully captured into gallery!");
}

capture().catch((err) => {
  console.error("Capture failed:", err);
  process.exit(1);
});
