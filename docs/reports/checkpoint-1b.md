# CHECKPOINT 1B — Client OTP2, separazione reale/demo, errori e test

> **Revisione post-review:** il client è stato consolidato con validazione
> rigorosa delle risposte reali, coordinate finite prima della rete e ambiente
> installato da `pyproject.toml`. Le sezioni 1–11 restano l'evidenza del primo
> pass; conteggi e versioni aggiornati sono nelle sezioni 12–13.

Data: 2026-11-15. Perimetro: collegare il backend all'OTP 2.10.0 verificato in
1A. Non sono stati modificati database, migrazioni, Docker, agenti diversi da
Mobility, frontend o endpoint di viaggio. Non è stata avviata la Fase 2.

## 1. Base e modifiche

- HEAD iniziale: `12317220bdb208ef9988588cbca72b9143cdc84d`, `main` =
  `origin/main`.
- Modifiche applicative: client OTP, wiring/configurazione Mobility, modelli di
  configurazione/rifiuto, documentazione e test.
- Nessuna modifica a `database/migrations/**`, `infra/postgres/**`,
  `docker-compose.yml`, `backend/app/api/**` o agli agenti Crowding/Context.
- Ambiente di test isolato: `/home/r0x4n/otp-1b-venv`, creato con
  `python3 -m venv --without-pip` (il modulo `venv` del sistema non include
  `ensurepip`; pip è stato inizializzato con `get-pip.py`). I pacchetti globali
  non sono stati modificati.
- Versioni usate: Python 3.14.4, FastAPI 0.163.0, Pydantic 2.14.3, httpx
  0.28.1, pytest 9.2.0, `sse-starlette` 2.1.3. La 3.7.0 installata inizialmente
  non espone `AppStatus.should_exit_event`, usato dal codice SSE esistente;
  è stata fissata a 2.1.3, coerente con `pyproject.toml`.
- Installazione: `python3 -m venv --without-pip /home/r0x4n/otp-1b-venv`,
  `get-pip.py` nel venv, poi `pip install fastapi pydantic httpx PyYAML
  feedparser sse-starlette==2.1.3 pytest pytest-asyncio pytest-socket ruff`.

## 2. Contratto OTP 2.10 verificato sulla release avviata

Endpoint: `POST http://127.0.0.1:8080/otp/gtfs/v1`.

Query `planConnection` con variabili GraphQL tipizzate:

- `$origin`/`$destination: PlanLabeledLocationInput!`
- `$dateTime: PlanDateTimeInput` (`earliestDeparture` o `latestArrival`)
- `$first: Int`
- `$modes: PlanModesInput`
- `$preferences: PlanPreferencesInput`

L'input utente non è concatenato nella query: coordinate, data, modi ed
esclusioni sono valori delle variabili. Il test controlla che l'ID escluso non
compaia nel testo della query.

Campi verificati nello schema 2.10.0: `Itinerary.start/end/duration/walkTime/
walkDistance/numberOfTransfers/generalizedCost`, `Leg.mode/transitLeg/duration`,
`Leg.start/end` (`scheduledTime`, `estimated.time`, `estimated.delay`),
`route.gtfsId/shortName/longName/mode`, `trip.gtfsId`,
`from/to.stop.gtfsId` e `legGeometry.points/length`.

Il client conserva **tutti** gli itinerari in `ItineraryPlan.itineraries`; non
li riduce al primo. Il primo è usato solo dal finding corrente del Mobility
Agent, in attesa dell'orchestrazione.

Esclusioni: `preferences.transit.filters[].exclude[].routes` con ID
feed-scoped (`feedId:routeId`, ad esempio `1:1`). Un ID senza namespace viene
rifiutato prima della richiesta. La copertura verificata è l'esclusione di una
route/agency; non è una prova di chiusura stradale né di tutte le varianti della
linea.

## 3. Errori e separazione reale/demo

Classi distinte:

| Caso | Classe / risultato |
|---|---|
| timeout HTTP | `OtpTimeoutError` |
| servizio non raggiungibile | `OtpUnavailableError` |
| HTTP 4xx/5xx | `OtpHttpError` (status e body troncato) |
| GraphQL errors con HTTP 200 | `OtpGraphQLError` |
| JSON/schema non valido | `OtpInvalidResponseError` |
| nessun itinerario | `OtpNoRouteError`, con `routing_errors` |

`routingErrors` con itinerari utilizzabili non sono un fallimento totale:
restano in `ItineraryPlan.routing_errors`, il piano restituisce gli itinerari e
il Mobility Agent li espone in `content["routing_warnings"]`.

Modalità routing dedicata:

- `ROUTING_MODE=real` (default): nessuna fixture, nessuna coordinata
  predefinita, nessuna durata inventata. Un errore diventa un `Refusal`
  esplicito (`no_route`, `otp_timeout`, `otp_unavailable`, `otp_error`).
- `ROUTING_MODE=demo`: legge `shared/mocks/otp_fixture.json` senza rete e
  restituisce sempre `is_simulated=True` con `fallback_reason=demo_mode_fixture`.
- `ROUTING_TIMEZONE=Europe/Rome` per data/ora e richieste.
- `APP_PROFILE` resta la sola scelta di persistenza; non seleziona il routing.

`MobilityAgent` riceve `OTP_BASE_URL`, `OTP_TIMEOUT_S`, `ROUTING_MODE` e
`ROUTING_TIMEZONE` da `AppConfig`. Con `mode=real` e coordinate mancanti
restituisce `unmapped_point` invece di usare coordinate demo. Le coordinate
predefinite esistono solo nel percorso demo.

## 4. File modificati

- `backend/app/services/agents/mobility/otp_client.py` — riscrittura OTP2,
  variabili GraphQL, parser multi-itinerario, geometrie/ID, errori, demo.
- `backend/app/services/agents/mobility/agent.py` — wiring config, coordinate
  reali obbligatorie, gestione errori/Refusal, warnings, conteggio itinerari.
- `backend/app/domain/models/config.py` — `routing_mode`, `routing_timezone` e
  validazione timezone.
- `backend/app/services/orchestrator/config.py` — variabili `ROUTING_MODE` e
  `ROUTING_TIMEZONE`.
- `backend/app/domain/models/refusal.py` — codici `no_route`, `otp_timeout`,
  `otp_unavailable`, `otp_error`.
- `backend/docs/OPERATIONS.md`, `backend/docs/AGENTS.md` — documentazione.
- `tests/unit/agents/test_otp_client.py` — 16 test del client.
- `tests/fixtures/otp2/*` — payload registrati da OTP 2.10.0.
- Test esistenti aggiornati a `mode="demo"` dove il comportamento atteso è il
  fixture: `test_mobility.py`, `test_contract.py`, `test_offline.py`,
  `test_repositories.py`, `test_rt_freshness.py`.
- `tests/unit/test_config_invalid.py` — validazione routing mode/timezone.
- `infra/otp/probe.py` — manutenzione 1A; `infra/otp/live_client_check.py` —
  controllo live separato; `infra/otp/README.md`.

## 5. Test offline

Comando:

```bash
/home/r0x4n/otp-1b-venv/bin/python -m pytest -q
```

Risultato: **96 passed**, 2 warning (deprecazione `TestClient`/httpx e warning
atteso di `pytest-socket`), 0 failure.

Copertura dei nuovi test:

- più itinerari e campi reali: route/trip/stop ID, tempi, geometria;
- variables GraphQL e assenza dell'ID utente nella query;
- esclusione route feed-scoped;
- `no_route`;
- timeout;
- HTTP 503;
- GraphQL error con HTTP 200;
- JSON non valido e `planConnection` assente;
- itinerari utilizzabili con `routingErrors`;
- demo senza chiamate HTTP e marcato simulato;
- real mode senza fallback;
- validazione ID non feed-scoped;
- configurazione `ROUTING_MODE`/timezone e mapping `no_route` a `Refusal`;
- rifiuto reale senza coordinate, finding demo marcato simulato.

`ruff check` sui file modificati: **All checks passed**.

## 6. Controllo live separato

Comando:

```bash
/home/r0x4n/otp-1b-venv/bin/python infra/otp/live_client_check.py \
  --output /home/r0x4n/otp-1a/live-client-check.json
```

Caso B, stessi parametri per baseline ed esclusione salvo
`exclude_route_ids=("1:1",)`: Napoli P. Garibaldi
(40.851017,14.272976) → Torre Annunziata (40.759526,14.451518),
`2026-11-16T08:00:00+01:00`, `first=8`, modi WALK/BUS/RAIL,
`transit_only=true`.

- Baseline: 6 itinerari; route `1:1`, `1:4`, `1:1.`; primo `08:03:00`,
  durata `1770 s`; `is_simulated=false`, `source_id=otp`.
- Esclusione `1:1`: 4 itinerari; route `1:4` e `1:1.`; nessuna occorrenza di
  `1:1`; primo `08:12:30`, durata `2100 s`.
- Il controllo usa gli ID feed-scoped ottenuti dalla risposta live e verifica
  che esistano nel feed; non assume che `shortName` sia univoco.
- Il risultato è in `/home/r0x4n/otp-1a/live-client-check.json`.

## 7. Manutenzione script 1A

`infra/otp/probe.py` ora:

- salva richiesta (`*-request.json`) e risposta (`*.json`);
- usa le stesse impostazioni di modi per baseline ed esclusione
  (`transitOnly: true`, BUS/RAIL), cambiando soltanto il filtro;
- rifiuta shortName duplicati invece di scegliere un ID arbitrario;
- conserva i risultati in `/home/r0x4n/otp-1a/probe-artifacts-1b-final/`.

Il probe è stato rieseguito dopo la manutenzione: caso A 4→0 itinerari con
`NO_TRANSIT_CONNECTION`; caso B 6→4 itinerari con `1:4`/`1:1.` e assenza di
`1:1`.

## 8. Limiti

- La prova resta sul feed EAV ferroviario del 2026-11-16; non copre autobus,
  ANM, BusOne, real-time o database.
- Non è stato implementato l'endpoint di viaggio né l'orchestrazione; il client
  conserva la lista per una fase successiva.
- L'esclusione di una route non dimostra la gestione di chiusure stradali o di
  tutte le varianti della linea.
- Il fixture demo usa il vecchio payload `otp_fixture.json`, marcato simulato;
  i test offline usano payload OTP2 reali registrati. Il fixture con warning è
  derivato da una risposta reale, con un warning aggiunto per esercitare il
  percorso non-fatal; è documentato in `tests/fixtures/otp2/README.md`.
- OTP è ancora attivo come unità utente `otp-1a`, MainPID `224830`; arresto con
  `systemctl --user stop otp-1a`.
- 1B è fermo qui; la Fase 2 non è stata avviata.

## 12. Revisione post-review

### 12.1 Requisiti minimi delle risposte reali

Il parser ora accetta un itinerario solo se:

- contiene almeno un leg;
- ogni leg ha `mode`, `start.scheduledTime` e `end.scheduledTime`
  interpretabili e con offset di fuso;
- i tempi del leg sono non decrescenti e i leg non si sovrappongono oltre la
  tolleranza di `2 s`;
- `from` e `to` hanno coordinate numeriche finite, lat in `[-90, 90]` e lon in
  `[-180, 180]`;
- ogni leg transit ha `route.gtfsId`, `trip.gtfsId`, `from.stop.gtfsId` e
  `to.stop.gtfsId`;
- la durata dichiarata del leg è finita, non negativa e coerente con i tempi;
  se manca, è calcolata dai tempi validati;
- l'itinerario ha una durata dichiarata valida oppure calcolabile dai tempi;
  se `start`/`end` sono presenti devono essere entrambi interpretabili,
  `end >= start` e coerenti con il primo/ultimo leg;
- se `start`/`end` dell'itinerario mancano, sono ricavati dai tempi dei leg.

Campi legittimamente opzionali: nomi di route/stop, `route.shortName`,
`route.longName`, `route.mode`, `estimated`/`delay`, `legGeometry`,
`walkTime`, `walkDistance`, `numberOfTransfers`, `generalizedCost`. La loro
assenza non rende invalido il percorso.

Una risposta incompleta o incoerente produce `OtpInvalidResponseError`. Non
vengono più applicati `max(0, …)` o altri clamp: una durata negativa o un
`end` precedente a `start` sono errori. La durata è derivata solo da tempi
interpretabili e coerenti.

### 12.2 Coordinate prima della rete

`plan_itineraries` valida subito `from_lat`, `from_lon`, `to_lat`, `to_lon`:
numeri finiti, lat `[-90, 90]`, lon `[-180, 180]`; booleani, stringhe, NaN e
infiniti sono rifiutati con `ValueError` **prima** di costruire la richiesta o
chiamare HTTP. I test usano un transport che fallisce se viene contattato e
verificano che non parta alcuna richiesta.

### 12.3 Test aggiunti

In `tests/unit/agents/test_otp_client.py`:

- itinerario minimo valido con soli campi obbligatori;
- risposta incompleta (esempio `legs: [{mode: RAIL}]`);
- leg con `end` precedente a `start`;
- durata negativa di itinerario e di leg;
- durata dichiarata incoerente con i tempi;
- itinerario incoerente con il primo leg;
- durata calcolata da start/end o dai soli leg quando i campi mancano;
- leg transit senza `trip.gtfsId`;
- coordinate fuori range, NaN, infinito, stringa e booleano, con verifica che
  la rete non venga contattata.

I test sui payload reali OTP 2.10.0 restano invariati e passano con la nuova
validazione.

### 12.4 Ambiente riproducibile

L'ambiente è stato rifatto dal `pyproject.toml`, non con installazioni
individuali delle ultime versioni:

```bash
python3 -m venv --without-pip /home/r0x4n/otp-1b-venv-pyproject
# get-pip.py nel venv (ensurepip non disponibile nel Python di sistema)
/home/r0x4n/otp-1b-venv-pyproject/bin/pip install -e ".[dev]"
/home/r0x4n/otp-1b-venv-pyproject/bin/python -m pytest -q
```

Versioni effettive: Python 3.14.4, FastAPI 0.163.0, Pydantic 2.14.3, httpx
0.28.1, pytest 8.4.2, pytest-asyncio 0.26.0, pytest-socket 0.8.1,
`sse-starlette` 2.4.1, ruff 0.17.5, testcontainers 4.15.0. Le dipendenze
globali non sono state modificate e i vincoli del `pyproject.toml` non sono
stati aggiornati. Il venv precedente, usato per il primo pass, è superato da
questo.

### 12.5 Riesecuzione

- `tests/unit/agents/test_otp_client.py`: **29 passed**.
- Suite completa: **109 passed**, 3 warning attesi/deprecazioni, 0 failure,
  nessun blocco. Non è stato necessario introdurre timeout o esecuzione
  verbosa per diagnosi.
- `ruff check` sui file modificati: **All checks passed**.
- Live check con il nuovo parser:
  `/home/r0x4n/otp-1b-venv-pyproject/bin/python infra/otp/live_client_check.py \
  --output /home/r0x4n/otp-1a/live-client-check-revision.json` → baseline
  6 itinerari (`1:1`, `1:4`, `1:1.`), esclusione `1:1` → 4 itinerari (`1:4`,
  `1:1.`), nessuna occorrenza di `1:1`.
- Il probe 1A manutenuto continua a salvare richieste/risposte e a usare modi
  identici tra baseline ed esclusione.

### 12.6 Perimetro

Nessuna modifica a database, migrazioni, Docker, nuovi agenti, frontend o
endpoint di viaggio. La Fase 2 non è stata avviata. OTP resta attivo come unità
utente `otp-1a`, MainPID `224830`; arresto con
`systemctl --user stop otp-1a`.

## 13. Correzione: coordinate invalide nella risposta OTP

### 13.1 Difetto e correzione

Il difetto era riproducibile impostando `from.lat=None` nel primo leg di
`tests/fixtures/otp2/plan_baseline_b.json`: `_parse_plan()` chiamava
`_coordinate`, che sollevava `ValueError`; `MobilityAgent` non lo intercettava.

Correzione circoscritta:

- `plan_itineraries` continua a usare `_coordinate` per l'input: coordinate
  non numeriche, non finite o fuori range producono `ValueError` **prima**
  della rete.
- il parser della risposta usa il nuovo `_response_coordinate`, che converte
  l'errore al confine della validazione in `OtpInvalidResponseError`;
- non è stato aggiunto un `except ValueError` attorno all'intero metodo né a
  `plan_itineraries` o `MobilityAgent`. La conversione avviene solo nei quattro
  punti `leg.from.*` / `leg.to.*` del parser;
- `MobilityAgent` continua a intercettare `OtpInvalidResponseError` e a
  restituire `Refusal(reason_code="otp_error")`.

### 13.2 Test aggiunti

In `tests/unit/agents/test_otp_client.py`:

- il fixture reale `plan_baseline_b.json` con `from.lat=None` produce
  `OtpInvalidResponseError`;
- risposta con `from.lat=None`: `OtpInvalidResponseError`;
- risposta con `from.lat=91` o `from.lon=181`: `OtpInvalidResponseError`;
- `MobilityAgent` con risposta mancante/fuori range: `Refusal` con
  `reason_code="otp_error"` e nessuna propagazione dell'eccezione;
- restano attivi i test delle coordinate invalide in input, che verificano
  `ValueError` e zero richieste HTTP.

### 13.3 Riesecuzione

- `tests/unit/agents/test_otp_client.py`: **35 passed**.
- Suite completa: **115 passed**, 3 warning attesi/deprecazioni, 0 failure,
  nessun blocco.
- `ruff check` sui file modificati: **All checks passed**.
- Live check con il parser corretto: baseline 6 itinerari, esclusione `1:1`
  → 4 itinerari (`1:4`, `1:1.`), `1:1` assente; output in
  `/home/r0x4n/otp-1a/live-client-check-coord-fix.json`.
- Comandi: venv `otp-1b-venv-pyproject`, `python -m pytest -q`,
  `python infra/otp/live_client_check.py --output ...`.
- Nessuna modifica a database, Docker, fase 2 o altri componenti. OTP resta
  attivo come unità `otp-1a`, MainPID `224830`; arresto con
  `systemctl --user stop otp-1a`.
