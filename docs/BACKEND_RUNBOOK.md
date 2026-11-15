# Backend Runbook — Napoli Agentic City

Ultimo aggiornamento: 2026-11-15. Perimetro: backend, worker di acquisizione,
PostgreSQL/PostGIS e OTP già presenti sulla macchina. Frontend e BusOne non
fanno parte di questo percorso.

## 1. Prerequisiti attivi

| Componente | Valore verificato |
|---|---|
| Container DB | `napoli-postgres-mobility`, healthy, porta 5432 |
| Database | `mobility`; volume `hackaton2026cds_postgres_data` |
| Schemi GTFS | `gtfs_anm`, `gtfs_eav`; territorio `osm_territory` |
| OTP | `http://127.0.0.1:8080`, servizio utente `otp-mobility` |
| Python | `/home/r0x4n/otp-1b-venv-pyproject/bin/python` |
| Migrazioni | 001–006 applicate (`006_ingestion_pipeline.sql`) |

Docker può richiedere `sg docker -c '...'`. Non modificare i permessi del
socket. Non serve ricostruire GTFS/OSM/OTP per avviare backend e worker.

## 2. Configurazione

Esportare le variabili principali (oppure copiarle da `.env.example`):

```bash
export APP_PROFILE=postgres
export DATABASE_URL='postgresql://postgres:postgres@127.0.0.1:5432/mobility'
export OTP_BASE_URL='http://127.0.0.1:8080'
export OTP_TIMEOUT_S=30
export ROUTING_MODE=real
export ROUTING_TIMEZONE='Europe/Rome'
export LLM_MODE=live
export LLM_PROVIDER=openai_compatible
export LLM_BASE_URL='<base-url-provider>/v1'
export LLM_API_KEY='<chiave-dedicata-al-backend>'
export LLM_MODEL='<modello-piccolo-con-output-json>'
```

`LLM_MODE` accetta `off`, `replay`, `mock`, `live`. `replay`/`mock` sono
dichiarati separati e producono avvisi `is_simulated=true`. Con
`LLM_MODE=live` e credenziali assenti il worker **non** inventa risposte:
lascia i documenti `pending`/`needs_review`.

Variabili worker principali:

| Variabile | Default | Uso |
|---|---:|---|
| `INGESTION_REGISTRY_PATH` | `backend/app/config/sources.yaml` | registro fonti |
| `INGESTION_POLL_INTERVAL_S` | 30 | pausa del loop periodico |
| `INGESTION_LEASE_S` | 300 | lease dei job/documenti |
| `INGESTION_MAX_RETRIES` | 3 | retry HTTP/job |
| `INGESTION_TIMEOUT_S` | 20 | timeout per fonte |
| `INGESTION_MAX_CONCURRENCY` | 4 | limite di concorrenza (worker singolo con lock advisory) |
| `JOURNEY_MAX_PLANS` | 3 | massimo chiamate OTP per richiesta |
| `JOURNEY_BUDGET_S` | 15 | budget temporale routing |
| `GEOCODER_PROVIDER` | `local` | `local`, `none` o `nominatim` |

Nessun header BusOne, nessuna conferma termini e nessun secondo feed sono
richiesti. `ingest --all` e l'avvio predefinito non chiamano BusOne.

## 3. Avvio e arresto API

```bash
cd /home/r0x4n/hackaton2026CDS
APP_PROFILE=postgres \
DATABASE_URL='postgresql://postgres:postgres@127.0.0.1:5432/mobility' \
OTP_BASE_URL='http://127.0.0.1:8080' OTP_TIMEOUT_S=30 ROUTING_MODE=real \
LLM_MODE=off \
/home/r0x4n/otp-1b-venv-pyproject/bin/uvicorn app.main:app \
  --host 127.0.0.1 --port 8000
```

Arresto: `Ctrl-C` se in foreground, oppure `kill <pid>`. Il backend non avvia
polling: l'acquisizione è nel worker separato.

Verifica:

```bash
curl -sS -o /dev/null -w '%{http_code}\n' http://127.0.0.1:8000/openapi.json
curl -sS http://127.0.0.1:8000/api/v1/ingestion/status
```

## 4. Worker di acquisizione

Ciclo singolo per diagnosi (tutte le fonti dovute):

```bash
cd /home/r0x4n/hackaton2026CDS
APP_PROFILE=postgres \
DATABASE_URL='postgresql://postgres:postgres@127.0.0.1:5432/mobility' \
LLM_MODE=off \
/home/r0x4n/otp-1b-venv-pyproject/bin/python -m app.cli ingestion run --once
```

Forzare subito tutte le fonti o una sola:

```bash
... python -m app.cli ingestion run --once --force
... python -m app.cli ingestion run --once --force --source anm_news
... python -m app.cli ingestion run --once --force --source eav_rail
```

Modalità periodica continua (processo separato):

```bash
... python -m app.cli ingestion run --interval 30
```

Il worker prende un lock advisory PostgreSQL: una seconda istanza esce con
errore invece di duplicare il polling. I job e i documenti hanno lease e
recupero dopo crash. Per fermarlo: `Ctrl-C`/`SIGTERM`; con systemd usare
`systemctl --user stop napoli-ingestion-worker`.

I log sono su stdout (JSON strutturato). Stato, fonti, documenti e fetch:

```bash
... python -m app.cli ingestion status
... python -m app.cli ingestion sources
... python -m app.cli ingestion documents --status pending --limit 20
... python -m app.cli ingestion fetches --limit 20
```

Unità systemd di riferimento (non installata automaticamente):
`infra/systemd/napoli-ingestion-worker.service`. Prima di installarla,
verificare i path e creare un drop-in con le variabili d'ambiente, senza
salvare la chiave in un file leggibile da altri. La prevenzione delle doppie
istanze è nel lock applicativo, non nel timer.

## 5. Chiamate curl

### 5.1 Coordinate

```bash
curl -sS http://127.0.0.1:8000/api/v1/journeys/plan \
  -H 'Content-Type: application/json' \
  -d '{
    "origin": {"lat": 40.8943044, "lon": 14.2308735},
    "destination": {"lat": 40.8047221, "lon": 14.1745403},
    "depart_at": "2026-11-16T08:00:00",
    "timezone": "Europe/Rome",
    "modes": ["WALK", "BUS", "RAIL", "SUBWAY"],
    "transit_only": true,
    "first": 5
  }'
```

### 5.2 Prompt naturale

```bash
curl -sS http://127.0.0.1:8000/api/v1/journeys \
  -H 'Content-Type: application/json' \
  -d '{
    "prompt": "Da via Giovanni Antonio Campano a Città della Scienza domani alle 8",
    "timezone": "Europe/Rome",
    "first": 5
  }'
```

```bash
curl -sS http://127.0.0.1:8000/api/v1/journeys \
  -H 'Content-Type: application/json' \
  -d '{
    "prompt": "Da qui a Piazza Garibaldi, devo arrivare entro le 10",
    "client_location": {"lat": 40.8943044, "lon": 14.2308735},
    "timezone": "Europe/Rome"
  }'
```

Se la risposta è `needs_clarification`, scegliere un `candidate_id` e
rimandare la stessa richiesta con:

```json
{"prompt": "Da via Roma a Piazza Garibaldi", "timezone": "Europe/Rome",
 "context": {"selected_candidates": {"origin": "osm:way-group:..."}}}
```

Per un vincolo non supportato (es. "senza scale") la risposta chiede conferma;
per procedere:

```json
{"prompt": "Da Chiaiano al MANN senza scale domani alle 8",
 "timezone": "Europe/Rome",
 "context": {"accept_unsupported_constraints": true}}
```

### 5.3 Ispezione perturbazioni e acquisizione

```bash
curl -sS 'http://127.0.0.1:8000/api/v1/disruptions?include_simulated=false&limit=20'
curl -sS 'http://127.0.0.1:8000/api/v1/disruptions/ingest:eav_rail/<alert_id>'
curl -sS 'http://127.0.0.1:8000/api/v1/ingestion/status'
curl -sS 'http://127.0.0.1:8000/api/v1/ingestion/sources'
curl -sS 'http://127.0.0.1:8000/api/v1/ingestion/documents?status=pending&limit=20'
curl -sS 'http://127.0.0.1:8000/api/v1/ingestion/fetches?limit=20'
```

CLI equivalente:

```bash
... python -m app.cli disruptions list
... python -m app.cli disruptions get ingest:eav_rail <alert_id>
... python -m app.cli disruptions expire
```

Le risposte distinguono `is_simulated`. Il percorso reale esclude i fixture
anche in lettura: `include_simulated=true` serve solo per diagnosi/test.

## 6. Verifica provider AI

```bash
LLM_MODE=live LLM_BASE_URL=... LLM_API_KEY=... LLM_MODEL=... \
  /home/r0x4n/otp-1b-venv-pyproject/bin/python -m app.cli llm check
```

Esce `0` solo con una chiamata effettiva riuscita e stampa modello/latenza.
Non stampa la chiave. Senza le tre variabili esce `not_configured` e il
worker lascia i documenti in attesa.

## 7. Test e diagnostica

```bash
# suite ordinaria
/home/r0x4n/otp-1b-venv-pyproject/bin/python -m pytest -q

# ruff
/home/r0x4n/otp-1b-venv-pyproject/bin/ruff check backend shared tests infra

# PostgreSQL opt-in
GTFS_TEST_DATABASE_URL='postgresql://postgres:postgres@127.0.0.1:5432/mobility' \
DISRUPTION_TEST_DATABASE_URL='postgresql://postgres:postgres@127.0.0.1:5432/mobility' \
OSM_TEST_DATABASE_URL='postgresql://postgres:postgres@127.0.0.1:5432/mobility' \
INGESTION_TEST_DATABASE_URL='postgresql://postgres:postgres@127.0.0.1:5432/mobility' \
/home/r0x4n/otp-1b-venv-pyproject/bin/python -m pytest -q --force-enable-socket tests/db

# OTP live
OTP_LIVE_BASE_URL=http://127.0.0.1:8080 \
OTP_LIVE_DATABASE_URL='postgresql://postgres:postgres@127.0.0.1:5432/mobility' \
/home/r0x4n/otp-1b-venv-pyproject/bin/python -m pytest -q -m live_otp \
  --force-enable-socket tests/integration/test_otp_live.py

# coerenza DB/ZIP/build/live
/home/r0x4n/otp-1b-venv-pyproject/bin/python infra/otp/check_pipeline_consistency.py
```

## 8. Problemi comuni

| Sintomo | Controllo |
|---|---|
| `disruptions_unavailable` | `APP_PROFILE=postgres`, `DATABASE_URL`, migrazione 006 |
| `input_agent_unavailable` | profilo postgres e cataloghi GTFS/OSM |
| `otp_unavailable` | `curl $OTP_BASE_URL/otp/gtfs/v1`; servizio `otp-mobility` |
| documenti `pending` | provider AI non configurato o `LLM_MODE=off` |
| fonte con `last_error` | `ingestion sources`; la fonte resta censita |
| `no_verified_route` | chiusura attiva su un leg; non è un errore di trasporto |
| dati simulati visibili | usare `include_simulated=false` (default) |

Non eseguire `db reset`, non cancellare volumi, non ricostruire il grafo per
applicare una notizia. Le perturbazioni sono lette dal database a ogni
richiesta; OTP non va ricostruito.
