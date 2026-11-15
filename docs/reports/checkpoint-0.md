# CHECKPOINT 0 — Audit e proposta

Data audit: 2026-11-15 (Europe/Rome). Nessuna modifica a codice applicativo, configurazioni operative, volumi o dati del progetto. È stato creato solo questo report. L'analisi del GTFS ha usato una copia temporanea in `/tmp/opencode/gtfs_audit`, fuori dal repository.

## 1. Base Git

- HEAD: `1231722` (`Merge remote-tracking branch 'origin/main'`), branch `main`, tracking `origin/main`, nessun commit locale avanti/indietro.
- File non tracciati preesistenti: `docs/PIANO_ALLINEAMENTO_BACKEND.md`, `docs/PROMPT_OPENCODE_DEEPSEEK.md`, `docs/RECUPERO_PROGETTO.md`. Nessuna modifica a file tracciati.
- `git show --stat c84c5f45c5368be64c73ef48b2460b09f04fa68b`: commit "aggiunto docker database gtfs statico", 9 file, 607 righe; aggiunge solo `.env.example`, `.gitignore`, `docker-compose.yml`, `infra/`, script e Dockerfile PostgreSQL.
- `git diff c84c5f4..HEAD -- docker-compose.yml infra .env.example .gitignore`: vuoto. L'infrastruttura non è cambiata dopo quel commit.
- `infra/docker-compose.yml` è una seconda copia della stessa configurazione (solo servizio `db`, con volume `../data`).

## 2. Runtime e servizi

Verificato senza avviare entrypoint, importatori o container.

| Elemento | Esito |
|---|---|
| Docker CLI | ASSENTE (`docker: command not found`) |
| Docker daemon | INATTIVO (`systemctl is-active docker` → `inactive`), socket assente |
| Podman / nerdctl | ASSENTI |
| PostgreSQL locale | ASSENTE (nessun binario, nessun listener sulla 5432) |
| OTP | ASSENTE (nessun processo, JAR o `graph.obj`) |
| Java | PATH: OpenJDK 17.0.14; installato OpenJDK 25.0.5 in `/usr/lib/jvm/java-25-openjdk-amd64` |
| Python | 3.14.4; `fastapi`, `pydantic`, `httpx`, `psycopg` assenti; `pytest` rotto (`AttributeError: __spec__`) |
| Node / npm | ASSENTI: non è possibile eseguire localmente `gtfs-via-postgres` |
| `osmium` / `osm2pgsql` | ASSENTI sull'host |
| Memoria / disco / CPU | 14 GiB RAM (6.8 GiB disponibili), 380 GiB liberi, 16 core |

Conseguenza: database, volumi Docker, migrazioni applicate e servizi non sono verificabili in questo ambiente. Non si assume che siano vuoti o funzionanti.

## 3. Database e import GTFS

- `docker-compose.yml` espone solo `db`; non ci sono servizi backend, OTP, worker o frontend. Non esiste `data/` nel repository (è in `.gitignore`); non ci sono volumi accessibili.
- `database/migrations/001_init.sql` crea in `public` le tabelle `stops`, `routes`, `trips`, `stop_times`, `service_alerts`, ecc. con colonne applicative (`zone_id NOT NULL`, `geometry`, provenienza).
- `infra/postgres/scripts/download-monthly.sh` esegue:
  `gtfs-to-sql --ignore-unsupported --trips-without-shape-id --stops-location-index "$GTFS_CURRENT"/*.txt | psql ...`
  senza `--schema`. `gtfs-via-postgres` crea tabelle con gli stessi nomi (`stops`, `routes`, `trips`, `stop_times`, ...) e di default usa `public`: collisione con lo schema applicativo. La documentazione del tool espone `--schema`; la separazione logica richiesta dal piano è quindi possibile ma non è configurata.
- Non è stato possibile ispezionare il DB: nessun container, nessun volume, nessun listener. Non si dichiara nulla sullo stato delle tabelle importate.
- Difetti rilevati nello script, da correggere prima di usarlo come importatore autorevole:
  - `PBF_TARGET`, `PBF_ARCHIVE`, `PBF_TMP` sono usati alla riga 51 prima di essere assegnati; il ramo di aggiornamento condizionale non funziona come intende.
  - `curl -k` disabilita la verifica TLS per il GTFS.
  - `GTFS_URL` predefinito è una pagina HTML Infoclick, non un GTFS; solo il fallback è un archivio ZIP.
  - `npm install -g gtfs-via-postgres` non è versionato; l'import non è riproducibile.
  - Lo script scarica il PBF ma non invoca `osmium extract` né `osm2pgsql`: non esiste ancora un'importazione territoriale.
- Il Dockerfile installa `osmium-tool` e `osm2pgsql`, ma nessuno script li usa. Installazione degli strumenti ≠ import eseguito.

## 4. GTFS disponibile

### 4.1 File locale

`/home/r0x4n/Scaricati/google-transit.zip`

- Dimensione: 4.105.995 byte.
- SHA-256: `9a3eeba9a84ce7de11e3daf1e1727e60705ab89a0a9f8ea369105ff436716df9`.
- `unzip -tq`: archivio valido.
- Contenuto: `agency.txt`, `routes.txt`, `calendar_dates.txt`, `stop_times.txt`, `stops.txt`, `trips.txt`, `shapes.txt`; niente `calendar.txt`, niente `feed_info.txt`.
- Operatore: **EAV srl** (`NA0004` ferrovia, `EAVO autolinea`), non ANM.

Conteggi verificati:

| File | Righe dati |
|---|---:|
| agency | 2 |
| routes | 124 (108 bus tipo 3, 16 rail tipo 2) |
| trips | 7.415 |
| stops | 4.208 |
| stop_times | 280.889 |
| shapes | 166.625 punti |
| calendar_dates | 8.495 eccezioni, tutte `exception_type=1` |

- 59 `service_id`; date da `2025-09-15` a `2030-12-31`, 1.401 date distinte.
- 2026-11-15 (domenica): 13 servizi attivi, 486 corse. 2026-11-16 (lunedì): 19 servizi, 682 corse; la linea 2 ha 98 corse attive.
- 6.288 arrivi con orario ≥ 24:00: il dato è compatibile con GTFS, ma richiede gestione corretta delle date di servizio.
- 0 corse senza `stop_times`; 0 riferimenti a `trip_id` o `stop_id` inesistenti; 5 route senza corse; 717 corse con `shape_id` vuoto; 0 corse con shape inesistente.
- Il nome `google-transit.zip` **non contiene “gtfs”**. La documentazione OTP richiede che il file GTFS termini in `.zip` e contenga “gtfs” nel nome: così com'è non verrebbe rilevato. Va copiato/rinominato, ad esempio `eav-20261112.gtfs.zip`.

### 4.2 Feed ANM remoto

- `https://www.anm.it/google/google-transit.zip` risponde con redirect Salesforce e poi `200`, `content-type: application/zip`, `content-length: 6.257.032`, senza download effettuato.
- Il file locale EAV (4.105.995 byte) non corrisponde a questa risposta: non è il feed ANM e non è stato validato come ANM. Non si può dichiarare copertura ANM.

### 4.3 PBF

- Nessun PBF locale (ricerca in `/home/r0x4n` e `/tmp`).
- `https://download.geofabrik.de/europe/italy/sud-latest.osm.pbf` → redirect `307` a `sud-261113.osm.pbf`; `200`, `content-length: 423.322.789`, `Last-Modified: 2026-11-14 01:23:15`, MD5 pubblicato `35c90562a87af1ba669b990a1f3896e7`. Non scaricato.

## 5. Routing, client OTP e connettori

### 5.1 Client OTP

`backend/app/services/agents/mobility/otp_client.py`:

- usa `POST {base}/otp/routers/default/index/graphql`, endpoint OTP1;
- invia una query `plan(from: {lat, lon}, to: {lat, lon})` con `legs { mode route duration }`;
- in OTP2 2.10 l'endpoint è `/otp/gtfs/v1`, la query raccomandata è `planConnection` con `origin`/`destination`, e `Leg.route` è un oggetto, non uno scalare. La query attuale non è compatibile con OTP2 e il percorso reale non può funzionare;
- legge solo il primo itinerario, non passa data/ora, non chiede più alternative, non restituisce ID/geometrie/errori;
- su qualunque eccezione carica `shared/mocks/otp_fixture.json` e restituisce `is_simulated=True` senza distinguere profilo reale e demo. `MobilityAgent` usa quel risultato e `allow_simulation` non blocca questo fallback. Un OTP spento può quindi produrre un viaggio fittizio nel profilo reale;
- se non ci sono fermate usa coordinate predefinite (Garibaldi/Campi Flegrei), altro comportamento da eliminare nel flusso reale.

### 5.2 GTFS connector

- `GtfsConnector.run_static()` carica `database/seed/zones.csv` e tre route/corse hardcoded (`L2`, `R2`, `151`); non importa il GTFS reale.
- `GtfsStaticClient.load_from_zip_bytes()` esiste ma non è chiamato da nessun percorso e importa solo stops/routes, non trips, stop_times, calendari o shapes.
- `GtfsConnector.run()` chiama `load_from_zones_seed()` prima di ogni fetch real-time: i `trip_id`/`route_id` del feed BusOne non corrispondono al seed, con rischio di FK violate o dati scartati.
- `GtfsRtClient` usa il proxy BusOne; senza `RT_CLIENT_HEADER` reale le richieste non sono identificabili. In errore restituisce il fixture simulato con timestamp corrente.

### 5.3 RSS, scraper, profilo

- La CLI crea `RssConnector` senza `feed_url`; `run()` chiama `fallback()` e scrive un alert simulato "Guasto Linea 2" con `is_simulated=True`, `valid_to=None`. Se eseguita con profilo PostgreSQL, la simulazione viene persistita. Non c'è deduplicazione, worker o polling applicativo.
- `anm_info/anm_scraper.py` nel repo è versione **1.0.0**; lo strumento fornito dal team in `/home/r0x4n/Scrivania/Documenti utili hackalon/anm_info/anm_scraper.py` è **1.1.0** (gestione `--since-timestamp`, timezone Europe/Rome). Il repository non importa né collega lo scraper. `anm_news.json` fornito: 57 articoli, `scraped_at 2026-11-14T23:59:02+01:00`, 0 errori.
- Profilo predefinito: `APP_PROFILE=memory` (`config.py`, `orchestrator/config.py`). `.env.example` non contiene variabili backend, `DATABASE_URL` o `APP_PROFILE`; non c'è un servizio backend nel compose. Il profilo `postgres` esiste ma richiede `psycopg`, `DATABASE_URL` e un DB raggiungibile.
- Endpoint HTTP: solo `/api/v1/scenario`, `/api/v1/decision`, `/api/v1/findings`; nessun endpoint di viaggio. Il frontend invia `scenario_id`.

## 6. Release OTP proposta

Fonte ufficiale verificata il 2026-11-15:

- release **OpenTripPlanner 2.10.0**, pubblicata 2026-09-09, ultima release stabile; richiede **Java 25+**;
- artifact shaded: `otp-shaded-2.10.0.jar`, 191.382.029 byte, SHA-256 `5a5d1efd30b19295418ac49ad048c5f5cac341af63dd41d5e2ae5ad9e7b37885` (Maven Central, directory `org/opentripplanner/otp-shaded/2.10.0/`);
- endpoint GTFS GraphQL: `POST http://localhost:8080/otp/gtfs/v1`;
- documentazione: Basic Tutorial, Container Image, GTFS GraphQL API, `planConnection`, `TransitFilterInput`.

Input proposti per il primo build:

- GTFS: copia validata del file EAV locale in `data/otp/eav-20261112.gtfs.zip` (nome con “gtfs”), con SHA-256 e intervallo di servizio registrati. Se il revisore richiede ANM come primo operatore, va prima scaricato e validato il feed ANM remoto; il file EAV non va spacciato per ANM.
- OSM: PBF Geofabrik Sud del 2026-11-13, checksum MD5 verificato, estratto con `osmium extract` su un bbox configurabile. Bbox iniziale proposto: `13.80,40.55,14.85,41.40` (min/max delle fermate del feed EAV `13.8549,40.5992,14.7934,41.3511` più circa 0,05° di margine). Comprende Napoli, Sorrento, Aversa, Nola, Benevento e Ischia; non va chiamato “intera area metropolitana”. Se `osmium` non è disponibile e non è installabile senza privilegi, il ripiego è il PBF Sud completo, dichiarato come input provvisorio non definitivo.

Comandi di costruzione e avvio (JAR, senza Docker):

```bash
OTP_JAR=/path/otp-shaded-2.10.0.jar
OTP_DIR=/path/otp-data   # contiene *.gtfs.zip e *.osm.pbf
/usr/lib/jvm/java-25-openjdk-amd64/bin/java -Xmx4g -jar "$OTP_JAR" --build --save "$OTP_DIR"
/usr/lib/jvm/java-25-openjdk-amd64/bin/java -Xmx4g -jar "$OTP_JAR" --load --serve "$OTP_DIR"
```

Prova di routing e di esclusione:

1. `POST /otp/gtfs/v1` con `planConnection`, `dateTime: { earliestDeparture: "2026-11-16T08:00:00+01:00" }`, origine `40.892929,14.239837` (Piscinola Scampia) e destinazione `40.974147,14.213685` (Aversa), `first: 5`, modi `WALK`, `BUS`, `RAIL`. Queste coordinate sono fermate reali della linea 2 EAV; il risultato deve contenere una leg di transit, non un walk-only.
2. Leggere `feeds { feedId }` e `routes { gtfsId shortName }` per ottenere l'ID feed-scoped.
3. Ripetere la query con:
   ```graphql
   preferences: {
     transit: {
       filters: [{ exclude: [{ routes: ["<feedId>:2"] }] }]
     }
   }
   ```
   `TransitFilterInput` supporta `include`/`exclude` con `routes` e `agencies`; l'esclusione è a livello di route/agency. Non è supportata da questa API l'esclusione di un segmento stradale arbitrario: non va dichiarata come tale. Se la linea 2 è l'unica opzione, il risultato atteso è un errore di routing esplicito / nessun itinerario, non il fixture.

## 7. Modifiche minime per il checkpoint successivo

Nessuna modifica applicativa in CHECKPOINT 0. Il primo intervento proposto è una sotto-fase di Fase 1:

**CHECKPOINT 1A — OTP 2.10.0 reale, input validati e prova API (senza modifiche al client)**

File/azioni previsti:

- `data/otp/eav-20261112.gtfs.zip`: copia del GTFS EAV validato, nome compatibile OTP, hash e date registrati; non sovrascrivere l'originale in `~/Scaricati`.
- `data/otp/sud-261113.osm.pbf` + estratto con bbox: download con TLS, retry, file temporaneo, verifica MD5/dimensione, `osmium extract`; registrare URL, data, checksum, attribuzione OSM/ODbL.
- `infra/otp/` (nuovo runbook/script) e, solo se il revisore autorizza Docker, servizio OTP nel compose; in questo ambiente Docker non è disponibile, quindi la prova va fatta con JAR e Java 25.
- `docs/reports/checkpoint-1a.md` con comandi, hash, output di build, query baseline, query con esclusione, errori GraphQL e limiti.

**CHECKPOINT 1B — Client OTP2 e separazione reale/demo** (solo dopo ok a 1A):

- `backend/app/services/agents/mobility/otp_client.py`: endpoint `/otp/gtfs/v1`, `planConnection`, data/ora, `first`, `modes`, `preferences.transit.filters`, parsing di `edges[].node`, `routingErrors`, ID/geometrie e più itinerari.
- `backend/app/services/agents/mobility/agent.py`: nessun fallback simulato nel profilo reale; errori distinti `no_route` / `upstream_unavailable` / `invalid_query`; fixture solo in demo esplicita.
- `backend/app/domain/models/config.py` (già con `otp_base_url`/`otp_timeout_s`), test con payload OTP2 registrato e test di esclusione; `docker-compose.yml`/`infra/otp/` per il servizio.
- Non toccare ancora schema GTFS/PostGIS né gli agenti: quelli sono Fase 2/3.

## 8. Limiti e verifiche non eseguite

- DB, volumi, schema importato e import territoriale: **NON VERIFICATI** per assenza di Docker/PostgreSQL. Non si assume che il DB sia vuoto.
- Test automatici: **NON ESEGUITI** (dipendenze Python assenti; `pytest` in Python 3.14 termina con `AttributeError: __spec__`). Non è una prova di regressione applicativa.
- OTP reale, build grafo, routing e prova di esclusione: **NON ESEGUITI**. Il client OTP2 non è stato ancora corretto.
- GTFS ANM: **NON ACQUISITO/VALIDATO**; l'unico file locale è EAV. Il file remoto ANM è raggiungibile ma non è stato scaricato né aperto.
- PBF: **NON SCARICATO**; `osmium`/`osm2pgsql` non installati sull'host. Il PBF Sud completo è un ripiego da dichiarare, non l'input definitivo.
- La prova di esclusione riguarda route/agency, non segmenti stradali; la chiusura arbitraria di una strada non è supportata dall'API GTFS GraphQL e non va simulata come risolta.
- Nessun commit/push, nessun reset, nessuna cancellazione di file o volumi.
