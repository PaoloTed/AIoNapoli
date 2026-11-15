# Implementazione Ricerca 6 — Superfici AIoNapoli

Stato: implementato il 2026-11-15. Fonte di verità: `ricerche/ricerca6/`.

## 1. Struttura realizzata

### Nucleo condiviso (`lib/`)

| Modulo | Ruolo |
|---|---|
| `lib/types/contracts.ts` | Contratti 1:1 con il backend (`Finding`, `Decision`, `DecisionResponse`, `Refusal`, `ProblemDetail`, `ScenarioSnapshot`). |
| `lib/types/trace.ts` | Eventi SSE, inclusi `route_proposed`, `route_invalidated`, `negotiation_finished`. |
| `lib/api/client.ts` | `apiFetch<T>` con timeout 8s, gestione RFC 7807 e `ApiError`. |
| `lib/api/endpoints.ts` | `GET /api/v1/scenario/{id}`, `POST /api/v1/decision`, `POST /api/v1/finding/{agent}`, URL stream SSE. |
| `lib/api/mockMode.ts` | Fallback trasparente su dataset mock per timeout/errore di rete. |
| `lib/api/mocks/` | `scenario-bagnoli.json`, `decision-bagnoli.json`, `stream-bagnoli.json(.jsonl)`, `refusal-examples.json`. |
| `lib/state/store.tsx` | Store React Context: scenario, decisione, eventi, stato stream, simulazione, target, lingua. |
| `lib/state/useBootstrap.ts` | Bootstrap scenario + decisione con fallback mock e riesecuzione per l'Audit. |
| `lib/sse/useSSEStream.ts` | Consumo SSE ordinato per `seq`, stato connessione e replay mock per la demo offline. |
| `styles/design-tokens-operator.ts` | Token dark del Command Center. |
| `styles/design-tokens-recipient.ts` | Token light della superficie pubblica. |

### Superficie Operatore

| Route | Contenuti |
|---|---|
| `/operator` | Redirect a `/operator/situation`. |
| `/operator/situation` | Mappa 2D Napoli (bbox 40.75–40.95 / 14.10–14.40), marker per severità, flotta con bearing, layer densità, popover, gauge radiali, criticità cliccabili. |
| `/operator/decision` | Piano per target (operator/citizen/tourist), reasoning timeline, filtro step decisivi. |
| `/operator/discard` | Timeline negoziazione con proposte, scarti e accordo; pulsante `Avvia scenario`. |
| `/operator/audit` | Metadati, banco di prova determinismo (`Originale vs riesecuzione`) e registro refusal. |
| Chat (`Ctrl+K`) | Retrieval locale deterministico su piano, reasoning, finding e trace, con `CitationCard`. |

### Superficie Recipient

| Route | Contenuti |
|---|---|
| `/` | Overview con messaggio contestuale, 3 status card, mappa semplificata, chat assistente. |
| Mobile (<1024px) | Colonna singola con CTA sticky "Chiedi all'assistente" che apre il drawer. |
| Desktop (≥1024px) | Overview 60% + Chat 40%. |

Nessun layer tecnico sulla superficie recipient: niente flotta, densità o reasoning. Le risposte chat usano i `PlanItem` del target attivo e la narrativa localizzata IT/EN.

## 2. Modalità dati

| Variabile | Effetto |
|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | Base URL backend (default `http://127.0.0.1:8000`). |
| `NEXT_PUBLIC_USE_MOCKS=true` | Forza i dataset mock senza tentare il backend. |
| Backend spento (USE_MOCKS=false) | Dopo il timeout di 8s l'app passa ai mock, mostra il banner di simulazione e riproduce lo stream di negoziazione. |
| `NEXT_PUBLIC_DEMO_SCENARIO` | Scenario di default (default `bagnoli`). |

## 3. Mappe reali

- Componente condiviso `components/map/SlippyMap.tsx`: tile raster OpenStreetMap (nessuna API key), proiezione Web Mercator, pan/zoom, bbox di Napoli.
- Operatore: tema scuro (filtro CSS sui tile), layer densità, marker zona, flotta con bearing, popover, legenda e controlli zoom.
- Recipient: tile chiari, marker arrotondati per zona, popover in linguaggio naturale, nessun layer tecnico.
- Attribuzione OSM sempre visibile; nessun token richiesto.

## 4. Demo consigliata (90 secondi)

1. `/` — vista Cittadino: messaggio contestuale, card e mappa.
2. Switch su **Turista**: palette corallo e suggerimenti dedicati.
3. Apri la chat e chiedi *"Come arrivo in ufficio?"*: appare una `PlanCard` con tempo stimato.
4. `/operator/situation` — click sul marker Bagnoli: popover con evidenze e confidenza.
5. `/operator/decision` — piano per target e reasoning timeline; attiva "Solo step decisivi".
6. `/operator/discard` — `Avvia scenario`: proposta L2 → scarto per cantiere ANM → proposta R2 → accordo.
7. `/operator/audit` — `Esegui di nuovo`: badge **Identico (Deterministico)**.
8. `Ctrl+K` — chiedi *"Cosa è stato scartato?"* e apri una citazione ("Vedi nella timeline").
9. (Opzionale) arresta il backend e ricarica: banner simulazione e stesso flusso offline.

## 5. QA visiva

Screenshot prodotti in `frontend/.design-refs/results/`:

- `operator-shell.png`, `operator-situation.png`, `operator-decision.png`, `operator-discard.png`, `operator-audit.png`, `operator-chat.png`
- `recipient-shell.png`, `recipient-overview.png`, `recipient-chat.png`, `recipient-tourist.png`

Riferimenti esterni e analisi: `frontend/.design-refs/analysis.md`. Gli screenshot dei riferimenti non sono versionati (vedi `.gitignore`).

## 6. Brand identity

Asset ufficiali copiati da `ricerche/ricerca6/` in `frontend/public/brand/`:

| Asset | Uso |
|---|---|
| `icon-aionapoli.svg` | Punti compatti: rail operatore, avatar chat operatore, avatar chat recipient, favicon. |
| `logo-aionapoli.svg` | Header recipient (logo completo su fondo chiaro). |
| `logo-aionapoli-light.svg` | Header operatore (logo completo con wordmark chiaro per fondo scuro). |
| `wordmark-aionapoli.svg` | Disponibile per usi editoriali/testuali. |

Il componente condiviso è `components/brand/BrandLogo.tsx` (`variant: icon | full | full-light | wordmark`).

## 7. Gate eseguiti

```powershell
cd hackaton2026CDS/frontend
npx tsc --noEmit
npm run lint
npm run build
npm test
```

Esito: typecheck e lint puliti, build di produzione completata, suite Vitest verde.
