# CHECKPOINT P1+P2 — regressioni OTP, pipeline DB → OTP, journey API

Data: 2026-11-15 (Europe/Rome). Perimetro: P1.1, P1.2, P2.2, P2.3.
P2.1 è fermo alla preflight documentata: mancano identificativo
`X-BusOne-Client` e conferma dei termini per l'organizzazione.

**Esito sintetico**

- test suite ordinaria: **157 passed, 12 skipped, 5 deselected**;
- test live OTP+DB: **5 passed**;
- test DB PostgreSQL: **12 passed**;
- `ruff check`: nessun errore;
- L1 chiusa: 10 itinerari, 0 con L1, `routing_errors=[]`, ID route/trip/stop
  e orari verificati contro `gtfs_anm`/`gtfs_eav`;
- pipeline: DB = ZIP = build OTP; switch e rollback provati;
- container ricreato con volume preservato; conteggi, sentinella e due feed
  intatti;
- nessuna perturbazione L1 persistita; nessun cleanup distruttivo eseguito.

## 1. P1.1 — Test di regressione

Nuovi file:

- `tests/unit/agents/test_mobility_default_modes.py`
- `tests/unit/agents/test_l1_closed.py`
- `tests/unit/agents/test_otp_graph.py`
- `tests/integration/test_journeys_api.py`
- `tests/integration/test_otp_live.py`
- `tests/unit/test_pipeline_consistency.py`

Copertura:

1. `DEFAULT_MODES` contiene `SUBWAY`; `MobilityAgent` passa **la stessa
   tupla** a `OtpClient` (test di identità, nessuna copia nell'agente).
2. L1 chiusa:
   - discovery dal grafo con `shortName=L1` e agenzia ANM, senza assumere il
     feed ID. Sul grafo corrente: `feed=1`, route originale `4955`,
     scoped `1:4955`.
   - `OtpClient.plan_itineraries(..., exclude_route_ids=(l1.scoped_id,))`;
   - nessun itinerario contiene L1, almeno un'alternativa, `routing_errors=[]`;
   - test live: ogni leg transit viene riconciliato con lo schema del dataset
     corretto (route, trip, stop, `departure_time`, `arrival_time`).
3. Multi-dataset:
   - `map_feeds_to_datasets()` usa solo `agencies` e
     `public.gtfs_datasets.agency_ids`; feed arbitrari `17`/`91` nei test
     offline, `1`/`2` solo come osservazione live;
   - feed ambiguo (agenzie di due dataset) viene rifiutato, non indovinato;
   - gli ID originali `gtfs_route_id`, `gtfs_trip_id`, `gtfs_stop_id`
     restano disponibili e distinti.
4. Offline: `httpx.MockTransport` per discovery, piano, errori, esclusione,
   `routing_errors`, no-route. Nessuna rete obbligatoria in CI.
5. Live opt-in:

```bash
OTP_LIVE_BASE_URL=http://127.0.0.1:8080 \
OTP_LIVE_DATABASE_URL='postgresql://postgres:postgres@127.0.0.1:5432/mobility' \
pytest -q -m live_otp --force-enable-socket tests/integration/test_otp_live.py
```

Risultato: **5 passed**. Il modulo è escluso dalla suite ordinaria
(`-m 'not network'` in `pyproject.toml`).

### 1.1 L1 chiusa — numeri correnti

Via Domenico Biondi → Città della Scienza, 2026-11-16 08:00 Europe/Rome,
`first=10`, `transit_only=true`, modi `WALK,BUS,RAIL,SUBWAY`:

| Scenario | Itinerari | Leg transit | Durata migliore | L1 | routingErrors |
|---|---:|---:|---:|---|---|
| baseline | 10 | 26 | 4.709 s | presente | `[]` |
| L1 chiusa | 10 | 29 | 4.855 s | assente | `[]` |

Route nell'alternativa senza L1: `167`, `168`, `178`, `R7`, `C1`, EAV `9`/`9.`.
La verifica live ha controllato tutti i 29 leg transit contro i rispettivi
schemi (`anm` per feed 1, `eav` per feed 2 nella build corrente).

## 2. P1.2 — Pipeline DB → OTP

### 2.1 Stato container e script

| Controllo | Esito |
|---|---|
| Container | `napoli-postgres-mobility`, healthy |
| Immagine | `hackaton2026cds-db:latest`, `sha256:0de66c651cfe54f85a48f3cb913d070908b67e6357e94b4a1122ae301181e3c9` |
| PostgreSQL | 18.7 + PostGIS |
| `gtfs-to-sql` | v4.13.0 |
| Script nel container vs repository | SHA-256 identici |
| `download-monthly.sh` | `e8de0b01c721304bdcd0e7ccbb839ff95c0d7b78cb0416d46c0f17f691cad0a7` |
| `import-gtfs.sh` | `bac7c6ea6c203a967e46c94166cf1aba6bff31f74b635a8f22fada872d35c9cc` |
| `sync_graph_from_request.sh` | host-only, `fa57df6753d9a546adb7be7057ae7b2f9d235c1c1ad0bb70c26fbb6a376d4541` |

`/etc/environment` finale (container ricreato senza download all'avvio):

```text
GTFS_SCHEMA=gtfs_anm
GTFS_DATASET_KEY=anm
GTFS_DATASETS=eav:gtfs_eav,anm:gtfs_anm
AUTO_IMPORT_GTFS=true
OTP_REBUILD_ENABLED=true
RUN_ON_STARTUP=false
SKIP_PBF_DOWNLOAD=true
```

Nota: la finestra controllata richiesta è stata eseguita con
`AUTO_IMPORT_GTFS=false`; dopo le verifiche il container è stato ricreato con
`AUTO_IMPORT_GTFS=true` e `RUN_ON_STARTUP=false`, così il cron mensile torna
operativo senza avviare un download al boot. `SKIP_PBF_DOWNLOAD=true` resta
impostato dalla finestra controllata: il cron aggiorna il GTFS ma non il PBF
OSM. Per riabilitare l'aggiornamento OSM periodico va impostato
`SKIP_PBF_DOWNLOAD=false` in una finestra pianificata, verificando spazio e
tempo di download.

### 2.2 Recreate e preservazione

Comando della finestra controllata:

```bash
RUN_ON_STARTUP=false AUTO_IMPORT_GTFS=false SKIP_PBF_DOWNLOAD=true \
  docker compose up -d --build
```

Dopo il recreate:

| Dato | Prima | Dopo |
|---|---:|---:|
| `gtfs_eav.routes` | 124 | 124 |
| `gtfs_anm.routes` | 112 | 112 |
| `osm_territory.osm_ways` | 204.803 | 204.803 |
| `osm_territory.pois` | 97.937 | 97.937 |
| `public.gtfs_datasets` | 2 | 2 |
| finding `checkpoint-2a-docker-sentinel` | 1 | 1 |

Volume `hackaton2026cds_postgres_data` invariato. OTP health su `:8080`,
feed presenti (`1`, `2`).

### 2.3 Aggiornamento reale e rebuild

Eseguito:

```bash
docker exec napoli-postgres-mobility /usr/local/bin/download-monthly.sh
```

Esito:

- ZIP ANM scaricato da `https://www.anm.it/google/google-transit.zip`,
  6.257.032 byte, SHA-256
  `ac0dfd987b734022efde05e98b312b59ddde68a8e49c77564e8bfbdb641f15b4`;
- import in staging `gtfs_anm_stage_20261115094947`, validazione conteggi,
  pubblicazione atomica (precedente `gtfs_anm_prev_20261115095128`);
- `gtfs_datasets` aggiornato, import run `9` pubblicata;
- richiesta `20261115T095131Z-86` scritta in
  `data/otp-rebuild/request.json`;
- `otp-graph-sync.path` ha avviato `otp-graph-sync.service`; poiché hash DB e
  grafo erano già uguali, il servizio ha chiuso con
  `grafo OTP già sincronizzato con gli hash del database` (nessun rebuild
  inutile).

Rebuild completo forzato per provare build/validazione/switch:

```bash
infra/otp/sync_graph_from_request.sh --force
```

- build: `graph-ac0dfd98-9a3eeba9-20261115T095141Z`;
- validazione su porta 8081, feed ≥2, route con corse = DB, L1/C1/R7 presenti;
- switch atomico di `/home/r0x4n/otp-live`;
- `graph.obj` SHA-256
  `373330aa17cd4cd4a14e89401b15355b47488db633ee61e0db18281e8907ed48`,
  uguale a `current.json`;
- ZIP nella build:
  - `anm.gtfs.zip` = `ac0dfd98…` = DB = `data/gtfs/gtfs-latest.zip`;
  - `eav.gtfs.zip` = `9a3eeba9…` = DB = `data/gtfs/eav-technical.gtfs.zip`.

### 2.4 Rollback provato

Con `previous_version = graph-ac0dfd98-9a3eeba9-20261115T085616Z`:

1. stop di `otp-mobility.service`;
2. symlink atomico `otp-live` al grafo precedente;
3. start del servizio, feed `1`/`2` presenti, servizio healthy;
4. ripristino del grafo corrente, start, feed `1`/`2` presenti.

Nessun grafo precedente è stato cancellato. Il grafo live finale è
`graph-ac0dfd98-9a3eeba9-20261115T095141Z`.

### 2.5 Controllo di coerenza

Nuovo `infra/otp/check_pipeline_consistency.py` (solo lettura):
confronta `gtfs_datasets.source_sha256` con `current.json` e
`last-result.json`, verifica gli ZIP e `graph.obj` della build attiva, il
symlink `otp-live` e il numero di route esposte da OTP.

```bash
python3 infra/otp/check_pipeline_consistency.py
# PIPELINE COERENTE: dataset DB = current.json = last-result.json,
# ZIP e graph.obj della build attiva allineati, symlink live corretto.
# OTP: feed e numero route coerenti con il database.
```

Test negativo con hash alterato: exit **1** e messaggio
`current.json: hash diverso per 'anm'`. Il controllo è integrato in
`otp-graph-sync.service` come `ExecStartPost`; se fallisce, l'unità fallisce.
Unità installata e `daemon-reload` eseguito.

### 2.6 Retention

Policy manuale in `docs/reports/retention-policy.md`. Non è stato eseguito
alcun cleanup. Restano intatti grafi correnti/precedenti, schemi
`gtfs_*_stage_*`/`gtfs_*_prev_*`, volumi e dati OSM.

## 3. P2.2 — Endpoint HTTP travel planning

Implementato `POST /api/v1/journeys/plan`:

- `shared/schemas/journeys.py`: contratto Pydantic;
- `backend/app/services/journeys.py`: validazione, chiamata OTP, mapping
  errori distinti;
- `backend/app/api/v1/journeys.py`: router HTTP;
- wiring in `backend/app/main.py` e `BackendService`;
- contratto in `docs/CONTRACT_JOURNEY_PLAN.md`.

Caratteristiche:

- coordinate origine/destinazione, `depart_at` **oppure** `arrive_by`,
  `timezone`, `modes`, `transit_only`, `first`;
- output con durata, cambi, leg, route/trip/stop ID feed-scoped, agenzia e
  operatore, `routing_errors`, `source`;
- `no_route` è HTTP 200 con `status=no_route`, non un errore di trasporto;
- errori trasporto distinti: 504 timeout, 503 unavailable, 502 HTTP/GraphQL/
  risposta non valida; 422 input non valido;
- nessuna perturbazione P0, nessun `exclude_route_ids` esposto;
- frontend non modificato.

Test offline: `tests/integration/test_journeys_api.py` (mock, 16 casi).
Test live opt-in: incluso in `tests/integration/test_otp_live.py`; risposta
reale con itinerari, ID e operatori. Tutti verdi.

## 4. P2.3 — Casi limite e documentazione

### 4.1 Matrice date

Stessa origine/destinazione, 08:00 Europe/Rome, `first=10`, `transit_only=true`:

| Data | Esito | Itinerari | L1 |
|---|---|---:|---|
| 2026-11-16 (lunedì) | ok | 10 | presente |
| 2026-11-21 (sabato) | ok | 10 | presente |
| 2026-11-22 (domenica) | ok | 10 | presente |
| 2026-12-31 (ultimo giorno ANM) | ok | 10 | presente |
| 2027-01-01 (fuori validità ANM) | `NO_TRANSIT_CONNECTION_IN_SEARCH_WINDOW` | 0 | assente |

Il grafo contiene ANM `2026-11-09..2026-12-31` ed EAV
`2025-09-15..2030-12-31`; il 2027-01-01 l'endpoint restituisce
`status=no_route` con `routing_errors`, non una fixture.

### 4.2 Feed mancante, ZIP invalido, calendario vuoto, hash diverso

- feed mancante: `import-gtfs.sh` rifiuta l'archivio se manca uno tra
  `agency.txt`, `routes.txt`, `trips.txt`, `stops.txt`, `stop_times.txt`;
- ZIP invalido: `unzip -tq` fallisce → nessun import;
- calendario vuoto: aggiunto controllo esplicito in `import-gtfs.sh`
  (`service_days` senza date → import fallito, staging conservato);
- hash diverso: `sync_graph_from_request.sh` confronta gli hash di
  `gtfs_datasets`, file ZIP e richiesta; in caso di divergenza esce senza
  toccare il grafo live;
- feed ID cambiati: discovery e mapping usano `agencies`, non un numero
  fisso; test offline con feed `17`/`91`.

### 4.3 L2 Trenitalia (FS)

`gtfs_anm.agency` contiene `ANM` (Azienda Napoletana Mobilità) e `FS`
(Trenitalia). La route L2 è `gtfs_anm.routes.route_id=4778`, `agency_id=FS`,
`route_type=1`. È quindi una linea FS dentro il feed ANM: non è stata
separata né rinominata. Un'eventuale separazione richiede una decisione di
prodotto e un import dedicato.

### 4.4 Documentazione aggiornata

- `docs/CONTRACT_JOURNEY_PLAN.md`
- `docs/reports/busone-realtime-preflight.md`
- `docs/reports/retention-policy.md`
- `infra/otp/README.md`
- questo report

## 5. P2.1 — BusOne realtime

Preflight completa in `docs/reports/busone-realtime-preflight.md`.
Sintesi:

- endpoint disponibili e termini leggibili;
- `X-BusOne-Client` **non configurato** (`RT_CLIENT_HEADER=""`) e
  autorizzazione dell'organizzazione non confermata;
- lo statico BusOne ha hash diverso da `gtfs_anm` (anche se gli ID
  route/trip/stop campionati coincidono);
- nessun dataset `anm_busone`, nessun import, nessuna modifica al routing.

L'integrazione resta dietro approvazione esplicita.

## 6. Comandi di verifica

```bash
# suite ordinaria
/home/r0x4n/otp-1b-venv-pyproject/bin/python -m pytest -q

# ruff
/home/r0x4n/otp-1b-venv-pyproject/bin/ruff check backend shared tests infra

# live OTP + DB
OTP_LIVE_BASE_URL=http://127.0.0.1:8080 \
OTP_LIVE_DATABASE_URL='postgresql://postgres:postgres@127.0.0.1:5432/mobility' \
/home/r0x4n/otp-1b-venv-pyproject/bin/python -m pytest -q -m live_otp \
  --force-enable-socket tests/integration/test_otp_live.py

# test DB PostgreSQL
GTFS_TEST_DATABASE_URL='postgresql://postgres:postgres@127.0.0.1:5432/mobility' \
DISRUPTION_TEST_DATABASE_URL='postgresql://postgres:postgres@127.0.0.1:5432/mobility' \
OSM_TEST_DATABASE_URL='postgresql://postgres:postgres@127.0.0.1:5432/mobility' \
/home/r0x4n/otp-1b-venv-pyproject/bin/python -m pytest -q --force-enable-socket \
  tests/db/test_gtfs_postgres.py tests/db/test_osm_postgres.py \
  tests/db/test_disruptions_postgres.py tests/db/test_disruption_namespaces_postgres.py

# coerenza pipeline
/home/r0x4n/otp-1b-venv-pyproject/bin/python infra/otp/check_pipeline_consistency.py
```

## 7. Limiti

- La data 2027-01-01 non ha servizio per l'origine/destinazione scelta; il
  comportamento è esplicitato come `no_route`, non generalizzato a tutta la
  rete.
- L'esclusione L1 è solo un test: nessun `service_alert`, nessuna persistenza,
  nessun routing perturbato dal database.
- Il check di coerenza confronta numero di route e hash degli input, non
  l'identità byte-per-byte di ogni trip nel grafo.
- BusOne non è integrato finché mancano identificativo e autorizzazione.
- La policy di retention è manuale; nessun cleanup è stato eseguito.
