# Napoli Agentic City — Visual References Analysis & Design System

## 1. Executive Summary & Design System Architecture

The frontend of **Napoli Agentic City** embodies an intentional architectural duality: **Two Visual Registers, One Shared System**. Rather than employing a generic light/dark toggle across identical layouts, the application tailors each visual register to its operational context, cognitive workload, and physical viewing environment:

1. **Operator Surface (`/operator`)**:
   - **Environment**: Municipal control room, multi-monitor displays, low ambient lighting, projection screens (1440px+).
   - **Visual Register**: Dark mode (`#0B1016` background, `#131A23` surface, `#22303D` border, `#4FB3D9` cyan accent). Zero drop shadows; separation is achieved strictly through crisp 1px borders.
   - **Information Density**: High-density dashboard presenting simultaneous streams of data: live telemetry, 2D geofence map, finding cards, SSE reasoning timeline, plan matrices, discard/negotiation traces, and audit replays.
   - **Key Principle**: Maximum contrast, zero decorative fluff, absolute data transparency, and technical provenance tracking.

2. **Recipient Surface (`/`, `/tourist`, `/citizen`)**:
   - **Environment**: Mobile-first pocket guide (390px target viewport, e.g. iPhone 14/15), direct sunlight, single-thumb interaction.
   - **Visual Register**: Warm light mode (`#FAFAF8` background, `#FFFFFF` card surface, `#E2E0DA` border, `#0B6E8F` deep petroleum blue accent). Subtle card elevation (`box-shadow`) provides depth under bright ambient illumination.
   - **Information Density**: Progressive disclosure, single-column focus, contextual synthesized narrative, actionable recommendations, and natural language route querying.
   - **Key Principle**: Immediate legibility, calm typography, accessible touch targets, and clear distinction between real and simulated municipal feeds.

Both registers share identical geometric semantics for severity, data provenance, monospace technical identification, and accessibility compliance.

---

## 2. Visual Reference Screenshot Catalog

The 10 reference screenshots captured via headless Playwright browser automation (`capture_screens.mjs`) serve as the verified ground truth for the user interface.

### 2.1 Operator Control Room Reference Suite (`.design-refs/operator/`)

| File Name | Resolution | View Type | Core UI Features & Invariants Demonstrated |
|---|---|---|---|
| `01_operator_1440.png` | 1440 × 3622 px | Full Page Dashboard | Complete control room view at 1440px desktop: Header with scenario selector (`bagnoli`), system state dot (`live`), contract version pill (`1.0.0`), 2D map with geofence zones & real-time vehicle positions, 3 vertical Finding cards with confidence scores & sources, SSE RuleTimeline with monotonic event progression, PlanColumn split by target, Relevance contribution bars, and bit-for-bit determinism replay trigger. |
| `01b_operator_zone_highlighted.png` | 1440 × 900 px | Interactive Map Binding | Card-click bi-directional binding: clicking a mobility Finding card highlights the associated geographic zone (`zone_id: z-bagnoli-coroglio`) on the SVG/Mapbox 2D map with accent border (`#4FB3D9`) and semi-transparent fill (`rgba(79, 179, 217, 0.25)`). |
| `01c_operator_grounded_answer.png` | 1396 × 338 px | Local Retrieval Panel | Grounded query assistant responding to *"Perché hai scartato la linea?"*: displays deterministic citation cards linking to specific negotiation traces, constraint tokens, and supervisor reasoning steps without LLM hallucination. |
| `01d_operator_sensor_inspector.png` | 1440 × 3832 px | Telemetry Drawer | Slide-over telemetry inspector drawer displaying live camera feeds (Intel RealSense D435i depth stream, YOLOv11 crowd detection bounding boxes, pedestrian density counts, and FPS metrics). |
| `01e_operator_shortcuts_modal.png` | 1440 × 3832 px | Keyboard Navigation Modal | Accessible dialog overlay triggered by `?` or keyboard button: lists global hotkeys (`Alt+O`, `Alt+T`, `Alt+C`, `Escape`, `Space`) with keycap badges (`kbd`), accessible backdrop overlay (`rgba(0,0,0,0.6)`), and focus trap. |

### 2.2 Recipient Pocket Guide Reference Suite (`.design-refs/recipient/`)

| File Name | Resolution | View Type | Core UI Features & Invariants Demonstrated |
|---|---|---|---|
| `00_home_1440.png` | 1440 × 1194 px | Desktop Overview | Desktop landing view at `/`: displays header with system status, scenario switcher, three distinct viewpoint selection cards (Operator, Tourist, Citizen), and natural language route assistant input bar with sample query chips. |
| `00b_home_route_query.png` | 960 × 400 px | NL Assistant Query | Route request assistant executing sample query *"Da Piazza Garibaldi a Bagnoli alle 18"*: displays parsed location chips (origin, destination, departure time), multimodal transit route recommendations, and negotiation status banner. |
| `02_tourist_mobile_390.png` | 390 × 1764 px | Mobile Tourist View | Mobile view at 390×844 (iPhone 14 standard) under `/tourist`: Italian localized narrative banner, compact interactive 2D route map, top-3 plan recommendations with estimated travel times, and subtle provenance badges. |
| `02b_tourist_english_390.png` | 390 × 1801 px | English Localized View | Instant language toggle to English (`lang="en"`): header language selector toggled, translated narrative recommendations, internationalized transit terminology, and formatted time stamps. |
| `03_citizen_mobile_390.png` | 390 × 1846 px | Mobile Citizen View | Mobile view at 390×844 under `/citizen`: commuter-focused presentation prioritizing public transit service status, disruption alerts (ANM strike / line maintenance), crowd congestion warnings, and alternate bus line frequencies. |

---

## 3. Visual Palettes & Contrast Ratios

### 3.1 Operator Surface (Dark Control Room Mode)

Designed for low-glare environments with strict WCAG 2.1 AA / AAA contrast ratios:

| Token Name | CSS Custom Property | HEX Value | RGBA Equivalent | Contrast vs BG (`#0B1016`) | Contrast vs Surface (`#131A23`) | Purpose |
|---|---|---|---|---|---|---|
| Background | `--bg` | `#0B1016` | `rgb(11, 16, 22)` | 1:1 (base) | 1.09:1 | Viewport and page canvas background |
| Surface | `--surface` | `#131A23` | `rgb(19, 26, 35)` | 1.09:1 | 1:1 (base) | Card, panel, rail, and drawer background |
| Border | `--border` | `#22303D` | `rgb(34, 48, 61)` | 1.42:1 | 1.31:1 | 1px card borders, dividing rules, table separators |
| Text Primary | `--text` | `#E8EDF2` | `rgb(232, 237, 242)` | **16.2:1** (AAA) | **14.9:1** (AAA) | Headings, active values, high-priority labels |
| Text Muted | `--text-muted` | `#93A2B1` | `rgb(147, 162, 177)` | **7.3:1** (AAA) | **6.7:1** (AA) | Secondary descriptions, timestamps, metadata |
| Accent | `--accent` | `#4FB3D9` | `rgb(79, 179, 217)` | **8.0:1** (AAA) | **7.3:1** (AAA) | Active navigation tab, map highlights, focus ring |
| Accent Soft | `--accent-soft` | — | `rgba(79, 179, 217, 0.14)` | — | — | Background highlight on hovered/active items |

*Note on Elevation*: In the Operator dark register, `box-shadow` is **strictly 0**. Elevation is communicated exclusively through layer stacking and 1px border contrast (`#22303D`).

*Note on Severity Token Contrast*: While primary and muted text tokens satisfy WCAG AA/AAA thresholds on both background and surface, chromatic severity colors (e.g. Critical `#C2382F` on Surface `#131A23` yields 3.25:1) fall below the 4.5:1 text requirement. Consequently, severity is never communicated through bare colored text alone; it strictly pairs with dual-channel geometric glyphs (`●`, `▲`) and textual badges.

### 3.2 Recipient Surface (Light Pocket Guide Mode)

Designed for high-ambient daylight viewing and optimal mobile readability:

| Token Name | CSS Custom Property | HEX Value | RGBA Equivalent | Contrast vs BG (`#FAFAF8`) | Contrast vs Surface (`#FFFFFF`) | Purpose |
|---|---|---|---|---|---|---|
| Background | `--bg` | `#FAFAF8` | `rgb(250, 250, 248)` | 1:1 (base) | 1.05:1 | Viewport and mobile body background |
| Surface | `--surface` | `#FFFFFF` | `rgb(255, 255, 255)` | 1.05:1 | 1:1 (base) | Elevated card, modal, and drawer canvas |
| Border | `--border` | `#E2E0DA` | `rgb(226, 224, 218)` | 1.26:1 | 1.21:1 | 1px card boundaries and subtle dividers |
| Text Primary | `--text` | `#141A20` | `rgb(20, 26, 32)` | **16.8:1** (AAA) | **17.5:1** (AAA) | Primary narrative, action titles, route instructions |
| Text Muted | `--text-muted` | `#5C6874` | `rgb(92, 104, 116)` | **5.4:1** (AA) | **5.7:1** (AA) | Ancillary guidance, travel times, transit line numbers |
| Accent | `--accent` | `#0B6E8F` | `rgb(11, 110, 143)` | **5.5:1** (AA) | **5.8:1** (AA) | Active buttons, route path lines, primary CTA |
| Accent Soft | `--accent-soft` | — | `rgba(11, 110, 143, 0.10)` | — | — | Selected chip background, active tab pill |

*Note on Elevation*: Recipient cards use a single, delicate elevation shadow:
`box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.06), 0 1px 2px 0 rgba(0, 0, 0, 0.04)`.

---

## 4. Typography System

The typography hierarchy balances human readability with technical auditability.

### 4.1 Font Families

- **Primary UI Typeface**: `Inter, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif`
  Used for all narrative copy, headings, buttons, and status labels. Selected for neutral geometric clarity and tall x-height.
- **Technical Monospace Typeface**: `ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace`
  Mandatory for all machine-generated identifiers, cryptographic hashes, sequence numbers, and JSON telemetry keys.

### 4.2 Type Scale & Style Tokens

| Role | Family | Weight | Size | Line Height | Tracking | Text Transform | Example Usage |
|---|---|---|---|---|---|---|---|
| Display / H1 | Inter | 600 (SemiBold) | 32px (2rem) | 1.20 | -0.02em | Normal | Page title, Surface switch title |
| Heading 2 / H2 | Inter | 600 (SemiBold) | 24px (1.5rem) | 1.25 | -0.015em | Normal | View headers (`Mappa`, `Decisione`, `Audit`) |
| Heading 3 / H3 | Inter | 600 (SemiBold) | 20px (1.25rem) | 1.30 | -0.01em | Normal | Card headings, Drawer titles |
| Body Regular | Inter | 400 (Regular) | 15px (0.9375rem) | 1.50 | normal | Normal | Narrative recommendations, reasoning steps |
| Body Medium | Inter | 500 (Medium) | 15px (0.9375rem) | 1.50 | normal | Normal | Action buttons, highlighted list items |
| Caption / Meta | Inter | 400 (Regular) | 13px (0.8125rem) | 1.40 | normal | Normal | Timestamps, agent names, helper text |
| Badges & Chips | Inter | 600 (SemiBold) | 11px (0.6875rem) | 1.20 | +0.05em | Uppercase / Small-Caps | `SIMULATO`, `LIVE`, `NON DISPONIBILE` |
| Monospace IDs | Monospace | 400 (Regular) | 13px (0.8125rem) | 1.40 | normal | None | `dec_20261115_001`, `fnd_mob_04`, `z-bagnoli` |
| Keycap Labels | Monospace | 500 (Medium) | 11px (0.6875rem) | 1.00 | normal | None | `<kbd>Esc</kbd>`, `<kbd>Alt+O</kbd>` |

---

## 5. Layout, Spacing & Responsive Grid

### 5.1 Base Grid System

The spatial layout strictly adheres to an **8-point base grid** with a **4px half-step** for tight component padding:

- `4px`: Micro-padding within chips, badges, icon gaps.
- `8px`: Standard button inner padding, card item gap.
- `12px`: Input field internal padding, table cell padding.
- `16px`: Standard card inner padding, list spacing.
- `24px`: Major section gutters, container margins.
- `32px`: Main dashboard column spacing.
- `48px`: Hero section padding, view-level top margins.

### 5.2 Responsive Target Viewports & Breakpoints

In adherence to `docs/DESIGN.md` Section 5, layouts are engineered for distinct operational tiers without wide horizontal tables:

| Viewport Tier | Breakpoint Range | Target Surface | Key Layout Behavior |
|---|---|---|---|
| **Desktop Master** | `≥ 1280px` (Baseline: 1280px, Master: 1440px) | `/operator` | Multi-column 12-col grid, persistent 64px `SidebarRail`, 7-col 2D map + 5-col findings, 3-column plan matrices (`tourist`, `citizen`, `operator`). Optimized for high-resolution control monitors and projectors. |
| **Tablet / Compact** | `768px – 1279px` | `/operator`, `/`, `/tourist`, `/citizen` | Fluid 2-column layout or stacked view; telemetry drawer overlays canvas rather than docking inline. |
| **Mobile / Sub-768px Fallback** | `< 768px` | `/operator` (Fallback) | **Operator below 768px**: Collapses into a single column. The 2D map is constrained to a fixed height of `240px`. The 3-target plan switches to a **tabbed plan interface** with tab toggles (`Operatore`, `Turista`, `Cittadino`) rather than horizontal columns. `SidebarRail` collapses into an accessible mobile navigation header/drawer. |
| **Mobile Recipient** | `< 768px` (Master: 390px iPhone 14/15) | `/`, `/tourist`, `/citizen` | 100% fluid single-column stack. Sticky top header (52px) with language toggle and `TargetSwitch`. Main narrative message pinned above the 240px map card. Touch targets strictly ≥ 44×44px. No data tables (all lists rendered as card decks). |

#### 5.2.1 Desktop 1440px Specification (Operator Master Target, 1280px Baseline)
- Desktop baseline: 1280px; Master target: 1440px with `max-w-[1440px]`.
- 64px width persistent `SidebarRail` navigation on left.
- Header spanning 100% width with 56px height.
- Multi-column 12-column CSS Grid:
  - Map + Data panel: 7 columns map (min 580px width, 420px height) + 5 columns finding cards.
  - Decision + Plan panel: 3 equal 4-column cards for Operator, Tourist, and Citizen targets.
  - Audit / Trace panel: Full width 12-column collapsible row.

#### 5.2.2 Mobile 390px Specification (Recipient Master Target)
- Target viewport: 390 × 844 px (iPhone 14/15 standard).
- 100% fluid single-column stack.
- Sticky top header (52px height) with language switcher and target toggle.
- Map card: 240px fixed height, optimized for touch panning.
- Recommendations: Vertical list of cards with 16px horizontal page margins and 12px item gaps.
- Touch targets: Minimum 44 × 44 px for all buttons, toggles, and expandable items.

#### 5.2.3 Sub-768px Operator Responsive Behavior
When the Operator control room is viewed below `768px` (e.g. tablet portrait, mobile diagnostics):
- Single column flow: sidebar rail hidden or transformed into a compact top bar menu.
- Map component reduced to `240px` fixed height to prevent vertical viewport domination.
- Target plan columns (`Operator`, `Tourist`, `Citizen`) collapsed into a single card with segmented tab controls (`tabbed plan`), ensuring zero horizontal clipping.

### 5.3 Motion, Transitions & Reduced Motion Specifications

In accordance with `docs/DESIGN.md` Section 2.5 and Section 4:
- **Zero Decorative Animation**: No animated gradients, no pulsating decorative badges, and no gratuitous bounce effects. All motion must communicate a genuine state change or streaming update.
- **Micro-Transitions**:
  - **Color & Opacity**: `120 ms` (`120ms ease`) for color, background-color, border-color, and opacity state transitions (hover, active, focus, tab selection).
    ```css
    transition: color 120ms ease, background-color 120ms ease, border-color 120ms ease, opacity 120ms ease;
    ```
- **RuleTimeline Step Entrance**:
  - **Entrance Animation**: `200 ms` (`200ms ease-out`) for the progressive entrance of new reasoning steps and rule evaluation rows arriving from the SSE stream.
    ```css
    transition: transform 200ms ease-out, opacity 200ms ease-out;
    ```
- **Reduced Motion Compliance (`prefers-reduced-motion: 0.01ms`)**:
  - Must strictly respect user operating system settings for reduced motion:
    ```css
    @media (prefers-reduced-motion: reduce) {
      *, *::before, *::after {
        animation-duration: 0.01ms !important;
        animation-iteration-count: 1 !important;
        transition-duration: 0.01ms !important;
        scroll-behavior: auto !important;
      }
    }
    ```
  - Under `prefers-reduced-motion`:
    - All entrance animations are disabled.
    - Timeline steps appear instantaneously without translation or fade delays.
    - State transitions occur instantaneously (`0.01ms`), eliminating perceptual disorientation or motion sickness triggers while preserving state changes.

---

## 6. Recurring Visual Patterns & Invariants

### 6.1 Shared Severity Tokens (Dual-Channel: Color + Geometric Shape)

In accordance with WCAG 1.4.1 (Use of Color), severity is **never communicated by color alone**. Because projected screens in municipal control rooms wash out reddish hues, every severity level combines a specific color with an unmistakable geometric shape:

| Severity Level | Color Token | Hex Code | Geometric Shape | Symbol / Glyph | Visual Rendering |
|---|---|---|---|---|---|
| `low` | `--sev-low` | `#5B8C6E` (Muted Green) | Small Solid Circle | `●` | 6px circle with 2px padding badge |
| `medium` | `--sev-medium` | `#C79A3A` (Warm Amber) | Solid Circle | `●` | 8px circle with 2px padding badge |
| `high` | `--sev-high` | `#D06A32` (Deep Orange) | Triangle Outline / Solid | `▲` | 9px equilateral triangle |
| `critical` | `--sev-critical` | `#C2382F` (Crimson Red) | Solid Triangle | `▲` | 10px bold equilateral triangle |

### 6.2 Data Provenance & Simulation Semantics

The visual representation of data provenance is the foundational trust mechanism of the application:

| Data Status | Card Border Style | Chip Badge | Status Indicator | Semantics & Rule |
|---|---|---|---|---|
| **Real Data** | `1px solid var(--border)` | *None* | Solid green dot (`#5B8C6E`) | Data originated from live physical sensors, OTP GTFS feed, or official ANM RSS. |
| **Simulated Data** (`is_simulated: true`) | `1px dashed var(--border)` | `SIMULATO` (11px, small-caps, border 1px dashed) | Hollow circle dot (`○`) | Synthesized scenario fallback. **Never colored red** (simulation is not an error). |
| **Missing / Refused Data** | `1px dashed var(--border)` with `opacity: 0.6` | `NON DISPONIBILE` | En-dash glyph (`—`) | Vertical agent refused or timed out. Displays `reason_code` (e.g. `agent_timeout`). |

### 6.3 Card Elevation & Border Radii

- **Border Radii**:
  - Cards & major panels: `10px` (`rounded-[10px]`).
  - Chips, buttons, inputs: `6px` (`rounded-[6px]`).
  - Pills, status dots: `9999px` (`rounded-full`).
- **Borders & Dividers**:
  - Always `1px solid` or `1px dashed`. Never 2px or heavy borders, preserving clean architectural drafting aesthetic.
- **Card Focus & Hover States**:
  - Operator: Hover transitions background to `var(--surface)` with border highlight `#4FB3D9`.
  - Recipient: Hover elevates shadow to `0 4px 6px -1px rgba(0, 0, 0, 0.08)`.

### 6.4 Focus Rings & Keyboard Accessibility

- **Focus Ring Invariant**:
  - Every interactive element (buttons, tabs, inputs, cards) must have an explicit focus indicator:
    `outline: 2px solid var(--accent); outline-offset: 2px;`.
  - `outline: none` without replacement is strictly forbidden.
- **Keyboard Shortcuts**:
  - `?`: Toggle keyboard shortcuts modal.
  - `Esc`: Close any active modal, drawer, or search panel.
  - `Alt+O`: Navigate to Operator surface.
  - `Alt+T`: Navigate to Tourist surface.
  - `Alt+C`: Navigate to Citizen surface.

### 6.5 Drawers, Modals & Slide-Overs

- **Telemetry Drawer (`01d_operator_sensor_inspector.png`)**:
  - Fixed right slide-over panel (width 480px on desktop).
  - Background: `#131A23` with 1px left border `#22303D`.
  - Accessible header with close button (`X`) and `Esc` key listener.
- **Shortcuts Modal (`01e_operator_shortcuts_modal.png`)**:
  - Centered dialog overlay (width 540px).
  - Backdrop: `rgba(0, 0, 0, 0.65)` with CSS backdrop-blur `2px`.
  - Keyboard accessible trap with autofocus on dismiss button.

### 6.6 Real-Time SSE Stream Accessibility & Screen Reader Compliance

The Server-Sent Events (SSE) stream dynamically pushes monotonic reasoning events (`TraceEvent`, `seq`) into the Operator's `RuleTimeline` and negotiation views during scenario evaluation. To maintain compliance with WCAG 2.1 (Section 4.1.3 Status Messages and Section 2.1 Keyboard Accessible):

1. **Live Region Configuration (`aria-live="polite"`)**:
   - The stream container hosting the `RuleTimeline` must explicitly set:
     ```html
     <div role="log" aria-live="polite" aria-atomic="false" aria-relevant="additions text">
     ```
   - Using `aria-live="polite"` guarantees that assistive technologies announce new reasoning steps and negotiation outcomes during natural pauses, preventing jarring interruptions of ongoing speech.
2. **Focus-Safe Appending (Never Steal Focus)**:
   - When new steps arrive over SSE (`route_proposed`, `route_invalidated`, `negotiation_finished`), the application appends them directly to the timeline feed **without shifting DOM focus**.
   - Invoking `.focus()` on dynamically appended stream elements is strictly prohibited. Active user focus in input fields (such as the Chat Drawer or search bar) or active keyboard navigation among existing finding cards must remain intact.
   - Any visual auto-scrolling to follow the streaming tail must be executed via container scroll adjustments (`element.scrollTop = element.scrollHeight`) or non-focus-shifting visual alignment (`scrollIntoView({ behavior: 'smooth', block: 'nearest' })`), preserving `document.activeElement`.
3. **Screen-Reader-Only Status Context**:
   - Each timeline step includes visually hidden context (`.sr-only`) indicating sequence number, rule outcome, and confidence score, ensuring full semantic comprehension for non-visual operators.

---

## 7. Implementation Checklist for Subsequent Milestones

- [x] **M0 (FASE 0)**: 10 screenshots acquired and validated in `.design-refs/`, `analysis.md` compiled with complete visual palette, typography, responsive breakpoints (<768px, 1280px baseline, 1440px master), motion tokens (120 ms / 120ms ease, 200 ms / 200ms ease-out, reduced motion 0.01ms), and SSE stream accessibility (`aria-live="polite"`, focus-safe appending).
- [ ] **M1 (FASE 1)**: TypeScript tokens implemented in `styles/design-tokens-operator.ts` and `styles/design-tokens-recipient.ts`.
- [ ] **M2 (FASE 2)**: Operator shell, situation map, decision cards, RuleTimeline with motion tokens, and telemetry drawer matching dark mode tokens.
- [ ] **M3 (FASE 3)**: Recipient shell, target switcher, responsive cards, and language toggle matching light mode tokens.
- [ ] **M4 (FASE 4)**: Cross-browser visual regression testing against screenshots in `.design-refs/`.
