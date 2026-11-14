[PIANIFICATO]

# Stack frontend

Tecnologie dell'interfaccia, con ruolo e motivo. Le voci `[PROPOSTA]` non sono ancora fissate in `package.json`: la versione si pina alla prima installazione.

Contesto: la traccia indica Next.js con mappa e componenti chat. Questo documento traduce l'indicazione in una lista di dipendenze precisa.

## 1. Base

| Tecnologia | Versione | Ruolo | Stato |
|---|---|---|---|
| Node.js | 20 LTS | runtime di sviluppo e build | `[PROPOSTA]` |
| pnpm | 9 | gestore pacchetti, lockfile versionato | `[PROPOSTA]` |
| Next.js | 15, App Router | routing, rendering, route handler per il proxy opzionale | `[PROPOSTA]` |
| React | 19 | componenti, `use` e streaming | `[PROPOSTA]` |
| TypeScript | 5.x, `strict: true` | tipi dei contratti | deciso |

Motivo dell'App Router: le tre schermate sono raggiungibili per rotta (`/operator`, `/tourist`, `/citizen`) e caricano un solo dato iniziale per volta. Un router client non aggiunge nulla. Alternative scartate: Pages Router, scartato perche' non aggiunge nulla su questo progetto; Vite + React Router, scartato perche' la traccia chiede Next.js.

Regola TypeScript: `strict`, `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`. I tipi dei contratti vivono in un solo file, `lib/contracts.ts`, e non si duplicano nei componenti.

## 2. Mappa

| Tecnologia | Versione | Ruolo |
|---|---|---|
| mapbox-gl | 3.x | mappa vettoriale, marker dei mezzi, poligoni delle zone |
| react-map-gl | 7.x | wrapper React, `Source` e `Layer` dichiarativi |

Motivo: la traccia indica Mapbox GL JS. La mappa deve mostrare tre cose e nient'altro: posizioni dei mezzi con eta' del dato, geo-fence della zona dell'evento, percorso o alternativa quando disponibile.

La chiave Mapbox sta in `NEXT_PUBLIC_MAPBOX_TOKEN`, letta a runtime. Se manca, la mappa mostra uno stato vuoto dichiarato ("mappa non configurata") e il resto dell'interfaccia funziona: la decisione non dipende dalla mappa.

## 3. Dati e stato

| Tecnologia | Versione | Ruolo |
|---|---|---|
| fetch nativo | — | client HTTP, nessun wrapper esterno |
| TanStack Query | 5.x | cache delle richieste, stati `loading`/`error`/`degraded` |
| zod | 3.x | validazione runtime delle risposte e controllo di `contract_version` |
| EventSource nativo | — | stream SSE della trace |

Motivo di TanStack Query: gli stati di caricamento sono parte del requisito (FE-REQ-11) e riscriverli a mano in tre schermate produce tre comportamenti diversi. Alternativa scartata: SWR, equivalente ma con meno strumenti per la gestione dell'errore.

Motivo di zod: il contratto viaggia su JSON e il backend puo' essere un commit indietro. Validare a runtime trasforma un disallineamento in un avviso visibile invece che in un `undefined` a schermo.

Stato locale: `useState` e `useReducer`. Nessuno store globale. Alternative scartate: Redux, scartato perche' non c'e' stato condiviso tra schermate; Zustand, scartato per la stessa ragione.

## 4. Stile

| Tecnologia | Versione | Ruolo |
|---|---|---|
| Tailwind CSS | 4.x | token e utility, un solo sistema di stile |
| next/font | — | Inter come font di interfaccia, self-hosted |
| clsx | 2.x | composizione delle classi |

Nessun CSS-in-JS e nessuna libreria di componenti preconfezionata: i componenti sono pochi e specifici, e una libreria imporrebbe la propria direzione visiva sopra [DESIGN.md](DESIGN.md). Le icone sono SVG inline, non un pacchetto.

## 5. Test e qualita'

| Tecnologia | Versione | Ruolo |
|---|---|---|
| Vitest | 2.x | test dei componenti e delle funzioni di mappatura |
| @testing-library/react | 16.x | test per comportamento, non per implementazione |
| Playwright | 1.4x | test end-to-end delle tre rotte, con backend in modalita' fixture |
| ESLint | 9.x | flat config, `next/core-web-vitals` |
| Prettier | 3.x | formattazione, nessuna discussione a mano |

Il test end-to-end della demo e' quello che conta: apre `/operator`, attende la timeline, verifica che il piano abbia tre target, ripete la decisione e confronta il `decision_id`.

## 6. Variabili d'ambiente

| Variabile | Default | Significato |
|---|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | `http://localhost:8000` | base URL del backend |
| `NEXT_PUBLIC_MAPBOX_TOKEN` | vuota | chiave della mappa, obbligatoria solo per la mappa |
| `NEXT_PUBLIC_DEMO_SCENARIO` | `bagnoli` | scenario caricato all'avvio, allineato a `DEMO_SCENARIO` del backend |

Nessun'altra variabile. Nessun segreto lato server: il frontend non ha un backend proprio e non parla con il database.

## 7. Fuori dallo stack, per scelta

| Tecnologia | Perche' non c'e' |
|---|---|
| libreria di componenti UI | la direzione visiva e' una scelta del progetto, non un default |
| Redux o Zustand | nessuno stato condiviso tra rotte |
| axios | `fetch` basta, e `EventSource` non si sostituisce |
| client GraphQL | l'API e' REST |
| libreria i18n | due lingue, un dizionario tipizzato in `lib/i18n.ts` |
| date-fns o moment | `Intl.DateTimeFormat` con `Europe/Rome` basta |
| proxy route handler | il backend espone CORS; il proxy si aggiunge solo se il CORS si rivela insufficiente in demo |
