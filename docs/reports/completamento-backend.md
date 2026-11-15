# Completamento backend — acquisizione, agenti e viaggio reale

Data: 2026-11-15 (Europe/Rome). Base Git: `main`, HEAD `95c5ea1`, con le
modifiche locali preesistenti conservate. Nessun commit/push. Frontend non
modificato. BusOne escluso dal nuovo percorso, dal polling e da `ingest --all`.

## 1. Esito sintetico

| Obiettivo | Esito | Evidenza |
|---|---|---|
| A — Agente Imprevisti + orchestratore sul viaggio reale | **COMPLETATO** | perturbazione persistita simulata → route ANM L1 risolta → esclusione OTP `1:4955` → 5 alternative reali, 1 sola chiamata OTP; perturbazione scaduta non applicata |
| B — Acquisizione periodica di tutte le fonti + catalogazione | **PARZIALE** | 96 fonti censite, 90 tentate, 85 OK, 5 errori persistiti, 2.351 documenti; ANM 57 documenti; interpretazione AI live non attestata per credenziali mancanti. Catalogazione verificata con estrazione mock su documento ANM reale, alert `is_simulated=true` |
| C — Agenti AI collegati a modello, strumenti e output validati | **PARZIALE** | adattatore OpenAI-compatible, prompt versionati, schema Pydantic, cache DB, resolver GTFS/OSM e tool applicativi implementati e testati con transport mock; nessuna chiamata live riuscita perché manca la chiave |
| D — Agente Input: prompt, luoghi, date/preferenze, chiarimenti | **COMPLETATO** | tre esempi accettati; “da qui” chiede le coordinate; luogo ambiguo restituisce candidati stabili; “senza scale” chiede conferma; stesso percorso OTP del piano coordinate |

Blocco esterno residuo: provider AI. `python -m app.cli llm check` con
`LLM_MODE=live` restituisce `not_configured` e richiede esattamente
`LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL` (oltre a
`LLM_PROVIDER=openai_compatible`). Non è stata riutilizzata la credenziale
DeepSeek di OpenCode: non è una configurazione del backend e non è stata
estratta né stampata.

## 2. Cosa è stato implementato

### 2.1 Acquisizione

- `backend/app/config/sources.yaml`: 96 fonti uniche — 95 URL unici presenti nei due elenchi del team, inclusi
  testati/scartati e tentativi `non_rss` censiti, più lo scraper ANM. Nessun URL di documento è escluso.
- `backend/app/services/ingestion/`:
  - `worker.py`: processo separato dall'API, ciclo singolo e periodico, lock
    advisory PostgreSQL, job/lease, retry/backoff, `Retry-After`, GET
    condizionale `ETag`/`Last-Modified`, timeout e concorrenza configurabili;
  - `repository.py`: fonti, documenti, fetch audit, job, lease, cache
    interpretazioni;
  - `parsing.py`: RSS/Atom, encoding, date italiane, ANM;
  - `relevance.py`: prefiltro deterministico locale/mobilità prima dell'AI;
  - `extraction.py`: JSON di estrazione validato e cache per hash + versione
    prompt/schema/modello + lingua;
  - `resolver.py`: route/trip/stop ANSI/EAV con dataset esplicito, strade/POI
    OSM raggruppati per nome e vicinanza;
  - `catalogue.py`: scrittura transazionale tramite `DisruptionRepository`,
    rettifiche/riaperture sullo stesso avviso quando il match è univoco,
    `is_simulated` per mock/replay.
- `backend/app/services/ingestion/vendor/anm_scraper.py`: copia invariata
  dello scraper del team, SHA-256
  `33e44664a8f0ab30685b1d0a66631c180087e58f74cb0a859d9ac65cda2acbec`.
- Migrazione additiva `006_ingestion_pipeline.sql`; nessuna modifica alle
  tabelle GTFS/OSM, nessun secondo archivio delle perturbazioni.

### 2.2 Agenti AI

- `backend/app/services/llm/client.py`: adapter OpenAI-compatible, timeout,
  budget token, retry, 429/Retry-After, `LLM_MODE=off|replay|mock|live`,
  nessun replay silenzioso in `live`.
- `prompts.py`: prompt di estrazione notizie con testo esterno delimitato come
  dato non affidabile; prompt dell’Agente Input.
- `extraction.py`: schema `NewsExtraction` con effetto, severità, lifecycle,
  validità, ricorrenza, direzioni, modi, evidenze e incertezza. La data della
  notizia non è automaticamente l’inizio del problema.
- `input/agent.py`, `input/prompt_parser.py`, `input/geocoder.py`: parsing
  italiano, date relative, Europe/Rome, preferenze supportate, vincoli non
  supportati con richiesta di conferma, risoluzione locale e adattatore
  Nominatim opzionale.
- `agents/incidents/`: valutazione deterministica su GTFS (dataset, route,
  trip, stop, service day, direzione, intervallo, GTFS >24:00) e OSM/PostGIS
  (distanze metriche, overlap, tunnel/bridge/layer), con esiti `blocked`,
  `penalized`, `uncertain`.

### 2.3 Orchestrazione e API

- `JourneyPlanner.plan` carica le perturbazioni reali prima del primo calcolo,
  esclude le route bloccate scoperte dal grafo corrente, valuta i leg, esclude
  i candidati bloccati, usa al massimo 3 chiamate OTP e un budget configurabile,
  riconosce i percorsi ripetuti e ordina i verificati per arrivo/durata, cambi,
  cammino e preferenze. Le penalizzazioni non aggiungono minuti inventati.
- Chiusure stradali: nessun parametro OTP finto. I candidati sono filtrati
  geometricamente; se non resta un’alternativa verificabile la risposta è
  `no_verified_route`, con i candidati incerti in `unverified_itineraries`.
- Endpoint:
  - `POST /api/v1/journeys/plan` (coordinate, contratto esistente esteso);
  - `POST /api/v1/journeys` (prompt naturale, `client_location`, contesto e
    chiarimenti);
  - `GET /api/v1/disruptions`, `GET /api/v1/disruptions/{source}/{alert}`;
  - `GET /api/v1/ingestion/status|sources|documents|fetches`.
- Il percorso FastAPI esegue DB/OTP sincroni in threadpool per non bloccare
  l’event loop; il worker usa una connessione separata.
- Le perturbazioni simulate sono escluse per default **in lettura** da
  `find_applicable` e `list_relevant`; `include_simulated=true` è solo
  diagnostica/test.

## 3. Acquisizione reale — risultati

Primo ciclo `--once --force`, `LLM_MODE=off`:

| Metrica | Valore |
|---|---:|
| Fonti censite | 96 |
| Fonti abilitate / tentate | 90 |
| Fonti `non_rss` censite e non chiamate | 6 |
| Fetch OK | 85 |
| Fetch falliti | 5 |
| Documenti nuovi | 2.328 |
| Documenti filtrati dal prefiltro | 1.293 |
| Documenti in attesa AI | 1.044 |
| Alert scritti (senza provider) | 0 |
| ANM | 57 documenti reali, 7 filtrati, 50 in attesa |

Errori persistiti attesi dalle verifiche del team: `abc_napoli` feed vuoto,
`corriere_mezzogiorno` 404, `mann` dominio non raggiungibile,
`napolitoday_feed` 404 sul percorso errato (il feed corretto `/rss` è OK),
`pompeiisites` HTML non RSS. Dettaglio per tutte le 96 fonti:
`docs/reports/ingestion-sources.md`.

Secondo polling:

- `--source eav_rail --force`: `documents_new=0`, `documents_updated=0`,
  `interpretations_*=0`, nessun duplicato.
- Polling completo: 34 risposte `304 Not Modified`, 13 nuovi item reali e 1
  aggiornamento (CCISS), gestiti come revisione `revision=2`; non è una
  duplicazione dello stesso contenuto.
- Il ticker CCISS cambia per natura; le fonti stabili non producono nuove
  interpretazioni.

Catalogazione AI:

- Test opt-in `tests/integration/test_ingestion_catalogue_live.py` usa un
  documento ANM reale e un transport LLM statico dichiarato mock. Produce un
  alert `is_simulated=true` con link `gtfs:anm:route:4955`, verifica che il
  percorso reale non lo veda e che `include_simulated=true` lo veda. Poi crea
  una rettifica `resolved` sullo stesso avviso (`revision=2`) e pulisce tutto.
- Nessun alert reale è stato inventato. Non esiste una falsa chiusura L1
  attiva come notizia reale.

## 4. Prove sul viaggio reale

Coordinate: `40.8943044,14.2308735` → `40.8047221,14.1745403`,
2026-11-16 08:00 Europe/Rome, modi `WALK,BUS,RAIL,SUBWAY`.

| Caso | Esito |
|---|---|
| baseline senza perturbazioni | `ok`, 5 itinerari, L1 presente, 1 chiamata OTP, durata migliore 5.009 s |
| perturbazione simulata L1 attiva (`valid_from=2026-11-16`, `valid_to=2026-11-16`) | `ok`, 5 alternative reali, **L1 assente**, route escluse `['1:4955']`, 1 chiamata OTP, `avoided_problems` con l’alert |
| stessa perturbazione scaduta (`valid_to=2026-11-12`) | `ok`, L1 presente, `disruptions_considered=0` |
| chiusura simulata di `way/511690651` sul primo leg pedonale | `no_verified_route`, nessun candidato presentato come sicuro, motivo esplicito; nessun finto parametro OTP |
| metropolitana/tunnel | i leg `SUBWAY`/`RAIL` sono esclusi dal controllo stradale; le way tunnel/bridge/layer non producono blocchi in superficie (logica applicativa, senza prova live dedicata) |

La prova L1 è una fixture chiaramente simulata, creata e cancellata nel test;
non è una notizia reale. Il percorso reale non la vede perché
`is_simulated=true` è filtrato in lettura.

### Prompt naturale

```bash
curl -sS http://127.0.0.1:8000/api/v1/journeys \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"Da via Giovanni Antonio Campano a Città della Scienza domani alle 8","timezone":"Europe/Rome","first":5}'
```

Esiti verificati:

- esempio 1: `ok`, origine strada OSM approssimata, destinazione POI,
  partenza 2026-11-16 08:00, 5 itinerari reali;
- “Dalla metro Chiaiano al MANN, con meno cammino possibile”: `ok`, stop
  `METRO CHIAIANO`, POI `Museo archeologico nazionale di Napoli`, preferenza
  cammino applicata;
- “Da qui a Piazza Garibaldi, devo arrivare entro le 10”: senza
  `client_location` → `needs_clarification`; con coordinate → `ok`, arrivo
  vincolato, 5 itinerari;
- “Da via Roma a Piazza Garibaldi”: `needs_clarification` con 8 candidati
  “Via Roma” distinti per cluster; la selezione `selected_candidates.origin`
  porta a `ok`;
- “senza scale”: `needs_clarification` sul vincolo; con
  `accept_unsupported_constraints=true` prosegue e dichiara il limite;
- “Da qui...” senza coordinate: nessuna posizione inventata.

## 5. Test eseguiti

| Comando | Esito |
|---|---|
| `python -m pytest -q` | **186 passed, 16 skipped, 5 deselected** |
| `pytest -q --force-enable-socket tests/db` con URL PostgreSQL | **21 passed** |
| `pytest -q -m live_otp --force-enable-socket tests/integration/test_otp_live.py` | **5 passed** |
| `pytest -q --force-enable-socket tests/integration/test_ingestion_catalogue_live.py` | **1 passed** |
| `ruff check backend shared tests infra` | **All checks passed** |
| `python infra/otp/check_pipeline_consistency.py` | **PIPELINE COERENTE** |
| `python -m app.cli llm check` con `LLM_MODE=live` | `not_configured`, exit 2: mancano le tre variabili |

La suite include nuovi test per registro fonti, parser RSS/Atom/ANM,
prefiltro, adapter LLM (mock transport), cache/idempotenza, parser prompt,
Agente Input, chiarimenti e isolamento dei fixture. I test PostgreSQL
preesistenti sono stati aggiornati al filtro `include_simulated` esplicito.

## 6. Stato dei processi e dati

- PostgreSQL `napoli-postgres-mobility`: healthy; database `mobility`;
  volume `hackaton2026cds_postgres_data` intatto.
- OTP `http://127.0.0.1:8080`: feed 1/2 presenti; pipeline DB = ZIP = build
  OTP = grafo live coerente.
- Conteggi finali: GTFS ANM 112 route, EAV 124 route; OSM 204.803 way e
  97.937 POI; `service_alerts` 2 fixture simulate preesistenti; nessuna
  perturbazione reale o simulata residua dai test (pulizia eseguita).
- API uvicorn usata per le prove: arrestata. Worker periodico: non lasciato
  attivo; comandi nel runbook. Nessun timer installato automaticamente.
- BusOne non chiamato; nessun header/termine richiesto.

## 7. File principali

- `backend/app/config/sources.yaml`, `backend/app/services/ingestion/*`
- `backend/app/services/llm/*`, `backend/app/services/input/*`
- `backend/app/services/agents/incidents/*`, `backend/app/services/journeys.py`
- `backend/app/api/v1/journeys.py`, `backend/app/api/v1/operations.py`
- `shared/schemas/journeys.py`
- `database/migrations/006_ingestion_pipeline.sql`
- `tests/unit/test_*`, `tests/db/test_ingestion_postgres.py`,
  `tests/integration/test_ingestion_catalogue_live.py`
- `docs/BACKEND_RUNBOOK.md`
- `docs/reports/ingestion-sources.md`
- `docs/CONTRACT_JOURNEY_PLAN.md`

## 8. Limiti reali residui

1. **Provider AI assente**: senza `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`
   non c’è interpretazione live delle notizie e gli Agenti AI non possono
   essere attestati come operativi sul provider. I 1.051 documenti in attesa
   restano `pending`; non vengono classificati a caso né trasformati in
   avvisi. Le prove di estrazione/catalogazione usano mock/replay dichiarato.
2. **Copertura stradale**: le chiusure sono verificate solo dove esistono way
   OSM e polilinee OTP; un’intersezione 2D non è un blocco. Le chiusure
   arbitrarie non sono un parametro OTP 2.10.
3. **Blocchi trip/stop**: OTP 2.10 non espone un filtro equivalente; la route
   viene esclusa conservativamente e la risposta lo dichiara.
4. **Rettifiche cross-source**: una riapertura viene collegata all’avviso
   esistente solo se la fonte è la stessa e il match di entità è univoco;
   altrimenti viene conservata come nuovo avviso con evidenza.
5. **ANM**: il feed ufficiale copre 2026-11-09..2026-12-31; oltre quella data
   serve un nuovo GTFS. Lo scraper dipende dagli endpoint Aura/Apex del sito.
6. **Geocodifica**: il resolver locale copre catalogo GTFS/OSM; per indirizzi
   fuori catalogo serve Nominatim (opzionale) o un fornitore configurato.
   Nessun civico o precisione GPS viene inventato.
7. **BusOne**: escluso per istruzione; non è un prerequisito e non è una
   copertura mancante del nuovo percorso.

Nessun commit/push è stato creato. I dati, i volumi, gli schemi, i grafi e le
modifiche locali preesistenti sono stati preservati.
