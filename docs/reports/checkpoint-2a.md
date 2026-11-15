# CHECKPOINT 2A / 2A-D — GTFS autorevole, backend e infrastruttura Docker

Data: 2026-11-15 (Europe/Rome). Perimetro: database GTFS, schema autorevole,
adattatore repository, import controllato, corrispondenza con il grafo OTP
2.10.0 e verifica dell'infrastruttura Docker recuperata da `c84c5f4`. Non sono
stati eseguiti import territoriali OSM, perturbazioni, nuovi agenti, frontend
o orchestrazione.

**Esito:** **COMPLETO per 2A-D**. L'import è stato eseguito sul database
PostgreSQL/PostGIS del container Docker del progetto, con volume persistente,
doppia importazione e lettura tramite repository backend. Restano fuori
perimetro 2B e 2C.

## 1. Accesso a Docker e stato iniziale

La prima sessione aveva riportato `permission denied` perché il processo non
aveva acquisito il gruppo `docker`. Il revisore ha verificato che l'utente
`r0x4n` è già nel gruppo; in 2A-D l'accesso è stato usato con `sg docker`,
**senza modificare permessi del socket**.

```text
id                         uid=1000(r0x4n), gruppi correnti senza docker
sg docker -c 'docker ...'  accesso funzionante
docker context show        default
docker ps -a               nessun container
docker volume ls           nessun volume
docker info                Docker 29.9.3, root /var/lib/docker
```

Al momento della verifica non esistevano container o volumi del progetto:
quindi non c'erano dati preesistenti da ispezionare o preservare. Non sono
stati cancellati volumi, reinizializzati database o cambiati permessi.

Infrastruttura Compose effettiva:

| Elemento | Valore |
|---|---|
| Progetto Compose | `hackaton2026cds` |
| Container | `napoli-postgres-mobility` |
| Immagine | `hackaton2026cds-db:latest` |
| Volume dati | `hackaton2026cds_postgres_data` |
| Mount | `/var/lib/postgresql` (volume), `/data` (bind `./data`) |
| Network | `hackaton2026cds_default` |
| Database / utente | `mobility` / `postgres` (password non riportata) |
| Porta host | `5432` |
| Versione runtime | PostgreSQL 18.7 + PostGIS 3.6.2 |

La prova locale precedente resta un'evidenza indipendente: PostgreSQL 18.6 +
PostGIS 3.6.2, database `mobility_2a`, porta `55432`, data directory
`/tmp/opencode/pgdata`. **Non è lo stesso database**: `mobility` su porta
`5432` è l'istanza Docker del progetto; `mobility_2a` su porta `55432` è
solo la verifica locale precedente.

## 2. Importatore fissato e schema realmente prodotto

Infrastruttura recuperata dal commit `c84c5f4` (`docker-compose.yml`,
`infra/postgres/Dockerfile`, entrypoint, cron e `download-monthly.sh`) e
corretta senza cancellare volumi o database. `gtfs-via-postgres` è fissato a
**4.13.0** (`npm install -g gtfs-via-postgres@4.13.0` nel Dockerfile). Lo
script di import verifica `gtfs-to-sql --version` e rifiuta versioni diverse.

Opzioni usate:

```bash
gtfs-to-sql --schema gtfs_eav \
  --require-dependencies --ignore-unsupported \
  --trips-without-shape-id --stops-location-index --import-metadata \
  -- <gtfs>/*.txt | psql -v ON_ERROR_STOP=1 -b
```

Tabelle create nello schema dedicato: `agency`, `calendar`, `calendar_dates`,
`routes`, `trips`, `stops`, `stop_times`, `shapes`, `frequencies`.
Viste: `service_days` (materializzata), `arrivals_departures`, `connections`,
`shapes_aggregated`. Funzioni di metadati: `gtfs_data_imported_at()`,
`gtfs_via_postgres_version()`, `gtfs_via_postgres_options()`,
`gtfs_feed_digest()`.

Lo schema `public` non riceve le tabelle GTFS: restano separate le tabelle
applicative. In `public` sono state aggiunte solo `gtfs_imports`,
`gtfs_datasets` e la funzione di mutex
`public.gtfs_via_postgres_import_version()`. La migrazione 002 rende
`public.stops.zone_id` nullable: una fermata reale non classificata ha
`zone_id = NULL`, non una zona inventata.

Il SQL generato dall'importatore contiene solo `CREATE SCHEMA/TABLE` nello
schema di staging; non contiene `DROP TABLE`, `TRUNCATE` o `DELETE FROM`.
L'importatore rifiuta uno schema di staging già esistente. La pubblicazione
usa uno schema nuovo e non tocca le tabelle applicative.

## 3. Dataset importato

Fonte: `/home/r0x4n/Scaricati/google-transit.zip` (file locale, non ANM).

| Metadato | Valore |
|---|---|
| Dimensione | 4.105.995 byte |
| SHA-256 | `9a3eeba9a84ce7de11e3daf1e1727e60705ab89a0a9f8ea369105ff436716df9` |
| Operatore | EAV srl — `NA0004` (ferrovia), `EAVO` (autolinea) |
| `feed_info.txt` | assente |
| Versione dataset | `eav-9a3eeba9a84ce7de` (content-addressed; nessuna data inventata) |
| Schema | `gtfs_eav` |
| Intervallo servizio | 2025-09-15 .. 2030-12-31 |

Confronto conteggi sorgente CSV vs database:

| File / tabella | Sorgente | Database |
|---|---:|---:|
| `agency` | 2 | 2 |
| `routes` | 124 | 124 |
| `trips` | 7.415 | 7.415 |
| `stops` | 4.208 | 4.208 |
| `stop_times` | 280.889 | 280.889 |
| `calendar_dates` | 8.495 | 8.495 |
| `shapes` (punti) | 166.625 | 166.625 |
| `service_days` | — | 8.495 |
| `shapes_aggregated` | — | 493 shape |

Validità e oltre 24:00:

- ferrovia: 717 corse, servizi dal 2026-11-12 al 2030-12-31;
- autolinea: 6.698 corse, servizi dal 2025-09-15 al 2025-10-31;
- **2026-11-16** (data di prova): 682 corse attive, tutte `route_type=2`
  (ferrovia), 11 route;
- nessuna estensione delle autolinee scadute;
- 6.288 passaggi complessivi con orario `>= 24:00:00`, massimo `30:30:00`;
- su `2025-09-22` (data valida per le autolinee) risultano 2.860 passaggi
  attivi oltre 24:00. Sulla data di prova 2026-11-16 non ci sono corse
  ferroviarie oltre 24:00: il caso è stato verificato su una data
  effettivamente attiva, senza prolungare la validità.

## 4. Mapping identificativi GTFS / persistiti / OTP

Il database conserva **gli identificativi originali GTFS senza prefisso**.
OTP aggiunge il namespace del feed al momento della build:

| Entità | GTFS originale | Persistito | OTP osservato |
|---|---|---|---|
| Route | `route_id=2` | `gtfs_eav.routes.route_id=2` | `1:2` |
| Trip | `trip_id=2080_opttp2026-2030-12` | `gtfs_eav.trips.trip_id=2080_opttp2026-2030-12` | `1:2080_opttp2026-2030-12` |
| Stop | `stop_id=6711` | `gtfs_eav.stops.stop_id=6711` | `1:6711` |
| Stop | `stop_id=6112` | `gtfs_eav.stops.stop_id=6112` | `1:6112` |

Il `feedId` **non è una costante**: `1` è solo l'ID assegnato da OTP al grafo
di questa prova. Il client e il verificatore leggono il prefisso dagli ID
restituiti (`feeds` / `routes.gtfsId`) e lo validano con
`backend/app/services/agents/mobility/gtfs_ids.py`. Un ID senza namespace
viene rifiutato; non viene mai assunto `1`.

Coerenza database/grafo:

1. OTP e database devono essere costruiti dallo stesso archivio, verificato
   con lo stesso SHA-256. `gtfs_datasets.source_sha256` registra l'hash usato
   dal database.
2. Il grafo OTP va ricostruito quando cambia l'archivio; il `feedId` va
   riletto dalla nuova istanza, non copiato da una build precedente.
3. Il database conserva gli ID originali: un itinerario OTP si riconcilia
   rimuovendo il prefisso del feed, non modificando gli ID persistiti.
4. Non vanno mescolati feed diversi (es. database EAV con grafo ANM): la
   chiave `dataset_key` e l'hash rendono esplicita la coppia.

## 5. Adattatore del backend

File principali:

- `database/migrations/001_init.sql`: `stops.zone_id` nullable.
- `database/migrations/002_gtfs_authoritative.sql`: metadati di import e
  dataset; nessuna copia della rete.
- `backend/app/repositories/postgres.py`: quando `GTFS_SCHEMA` è impostato,
  `get_stops/get_routes/get_trips/get_stop_times` leggono lo schema GTFS;
  `get_shapes`, `get_active_trips`, `get_active_stop_times`,
  `get_dataset_info` completano l'accesso.
- `backend/app/domain/models/config.py` e
  `backend/app/services/orchestrator/config.py`: `GTFS_SCHEMA` (default
  `gtfs_eav`) e `GTFS_DATASET_KEY` (default `eav`).
- `backend/app/services/facade.py`: passa lo schema al repository solo per
  `APP_PROFILE=postgres`; SQLite e memoria restano invariati.
- `backend/app/services/agents/mobility/gtfs_ids.py`: mapping esplicito.
- `backend/app/services/connectors/gtfs/connector.py`: il seed demo non viene
  più caricato automaticamente prima del real-time; resta solo nel comando
  `db seed` e nei test/demo.

Geometrie PostGIS: il repository usa `ST_AsText(stop_loc)` e
`ST_AsText(shape)` e non assume che psycopg restituisca WKT. Gli intervalli
GTFS sono convertiti in `HH:MM:SS` senza modulo 24 (`30:30:00` resta
`30:30:00`). Le fermate reali hanno `zone_id = NULL`; il `zone_id` GTFS
originale è esposto separatamente come `gtfs_zone_id` e non viene confuso con
la zona operativa.

## 6. Import e riesecuzione controllati

Nuovo script `infra/postgres/import-gtfs.sh`:

- verifica ZIP, hash, versione e file obbligatori;
- importa in `gtfs_eav_stage_<UTC>` con `gtfs-via-postgres` 4.13.0;
- confronta i conteggi CSV con quelli DB e controlla riferimenti orfani;
- registra fonte, hash, versione, operatore e conteggi in `gtfs_imports`;
- con `--publish`, in una transazione con advisory lock, rinomina l'eventuale
  schema attivo in `gtfs_eav_prev_<UTC>`, rinomina lo staging in `gtfs_eav` e
  aggiorna `gtfs_datasets`; nessuna tabella applicativa viene troncata.

Avvio del container senza download automatico, per usare solo l'EAV validato:

```bash
RUN_ON_STARTUP=false AUTO_IMPORT_GTFS=false SKIP_PBF_DOWNLOAD=true \
  docker compose up -d --build
docker cp /home/r0x4n/Scaricati/google-transit.zip \
  napoli-postgres-mobility:/data/gtfs/eav-technical.gtfs.zip
```

Il file è stato verificato dentro il container con lo stesso SHA-256. Il log
`/var/log/monthly-download.log` è rimasto vuoto: nessun feed ANM o PBF è stato
scaricato automaticamente.

Migrazioni applicate al database Docker con il migration runner del backend
(`001_init.sql`, `002_gtfs_authoritative.sql`). Import eseguito **dentro il
container**:

```bash
docker exec napoli-postgres-mobility bash /usr/local/bin/import-gtfs.sh \
  --zip /data/gtfs/eav-technical.gtfs.zip \
  --publish --source-url file:///data/gtfs/eav-technical.gtfs.zip
```

Due esecuzioni consecutive sullo stesso archivio nel database Docker:

| Controllo | Prima | Dopo seconda |
|---|---:|---:|
| `gtfs_eav.stops` | 4.208 | 4.208 |
| `gtfs_eav.routes` | 124 | 124 |
| `gtfs_eav.trips` | 7.415 | 7.415 |
| `gtfs_eav.stop_times` | 280.889 | 280.889 |
| `gtfs_eav.calendar_dates` | 8.495 | 8.495 |
| `gtfs_eav.shapes` | 166.625 | 166.625 |
| `gtfs_datasets` (righe) | 1 | 1 |
| `gtfs_imports` (righe pubblicate) | 1 | 2 |
| finding sentinella `checkpoint-2a-docker-sentinel` | presente | presente |

La seconda esecuzione ha lasciato lo schema precedente come
`gtfs_eav_prev_20261115003337`, aggiornato il dataset attivo e non ha creato
duplicati. Le viste e le funzioni interne (`service_days`,
`arrivals_departures`, `shapes_aggregated`, `gtfs_data_imported_at()`) sono
state rilette con successo dopo il rename dello schema. Il container è stato
poi riavviato (`docker restart`): è tornato `healthy` e i conteggi, la
sentinella e le due run di import erano ancora presenti nel volume
`hackaton2026cds_postgres_data`.

## 7. Difetti GTFS corretti

- URL HTML Infoclick sostituito con un URL ZIP in `.env.example`,
  `docker-compose.yml`, `infra/docker-compose.yml`, Dockerfile e script.
- Rimosso `curl -k`; TLS resta verificato.
- `gtfs-via-postgres` fissato a 4.13.0 (Dockerfile + controllo script).
- Collisione `public`: import in schema dedicato `gtfs_eav`.
- Variabili PBF usate prima dell'assegnazione: corrette in
  `download-monthly.sh`.
- Import diretto con `rm -rf` della directory corrente: sostituito con
  staging temporaneo e pubblicazione atomica.
- Seed demo non più eseguito automaticamente dal connettore real-time.
- Nessun download/import territoriale avviato in questo checkpoint.

## 8. Verifiche di accettazione

Lettura tramite repository backend (`BackendService` con
`APP_PROFILE=postgres`, `GTFS_SCHEMA=gtfs_eav`):

```text
dataset       eav-9a3eeba9a84ce7de
sha256        9a3eeba9a84c...
routes        124
stops         4.208 (zone_id NULL su tutte; gtfs_zone_id conservato)
trips route2  98
stop_times    5 per 2080_opttp2026-2030-12
active trips  682 su 2026-11-16
shapes        493
```

Corrispondenza con l'itinerario OTP 1B (Piscinola Scampia → Aversa,
2026-11-16T08:00+01:00):

```text
OTP 1:2                          -> route persistita 2
OTP 1:2080_opttp2026-2030-12     -> trip 2080_opttp2026-2030-12
OTP 1:6711                       -> stop 6711 (Piscinola Scampia)
OTP 1:6112                       -> stop 6112 (Aversa)
OTP 08:00:00 .. 08:12:30         -> stop_times 08:00:00 .. 08:12:30
```

Tutti i 4 leg di trasporto pubblico dell'artefatto OTP risultano presenti nel
database Docker. Il verificatore è
`infra/otp/verify_persisted_itinerary.py`; gli output sono in
`/home/r0x4n/otp-1a/checkpoint-2a-docker-itinerary.json` e
`checkpoint-2a-docker-itinerary-after-restart.json` (e, per la prova locale,
`checkpoint-2a-itinerary.json`).

Test:

- suite ordinaria: **118 passed, 2 skipped**;
- test PostgreSQL live contro il database Docker (`GTFS_TEST_DATABASE_URL`):
  **2 passed**;
- `ruff check`: nessun errore;
- `bash -n` sugli script: nessun errore;
- `docker compose config`: valido;
- `docker compose build` e avvio: riusciti; healthcheck `healthy`.

Lettura repository contro il database Docker, dopo il restart:

```text
dataset       eav-9a3eeba9a84ce7de
gtfs_schema   gtfs_eav
routes        124
stops         4.208 (zone_id NULL su tutte)
trips route2  98
active trips  682 su 2026-11-16
shapes        493
```

## 9. Limiti e stato

- **Docker/volume verificato in 2A-D**: container `napoli-postgres-mobility`
  `healthy`, volume `hackaton2026cds_postgres_data` persistente anche dopo
  `docker restart`.
- La prova locale `mobility_2a` sulla porta `55432` resta un'evidenza
  separata e NON è il database Docker `mobility` sulla porta `5432`.
- Copertura EAV: il giorno di prova contiene solo ferrovia; le autolinee EAV
  sono scadute e non sono state estese. Non è ANM, non è BusOne.
- Nessuna classificazione operativa delle fermate reali: `zone_id` resta
  `NULL` finché non esisterà una mappatura esplicita; non sono state create
  zone artificiali.
- Gli schemi precedenti restano come backup; la retention/cleanup è manuale.
- Il `feedId` OTP è specifico della build; non va riusato come costante.
- Fuori perimetro: 2B OSM/PostGIS, 2C perturbazioni, nuovi agenti/frontend.
  Nessun download o import territoriale è stato avviato.

## 10. Comandi riproducibili (senza credenziali)

```bash
# Accesso Docker senza cambiare permessi
sg docker -c 'docker context show && docker ps -a && docker volume ls'

# Build/avvio evitando download automatici
RUN_ON_STARTUP=false AUTO_IMPORT_GTFS=false SKIP_PBF_DOWNLOAD=true \
  docker compose up -d --build

# Migrazioni dal backend (DATABASE_URL verso il container)
APP_PROFILE=postgres DATABASE_URL='postgresql://postgres@127.0.0.1:5432/mobility' \
  python -m app.cli db migrate

# Import EAV già validato
docker cp /home/r0x4n/Scaricati/google-transit.zip \
  napoli-postgres-mobility:/data/gtfs/eav-technical.gtfs.zip
docker exec napoli-postgres-mobility bash /usr/local/bin/import-gtfs.sh \
  --zip /data/gtfs/eav-technical.gtfs.zip --publish \
  --source-url file:///data/gtfs/eav-technical.gtfs.zip

# Verifiche
docker exec napoli-postgres-mobility psql -U postgres -d mobility \
  -c "select count(*) from gtfs_eav.trips;"
python infra/otp/verify_persisted_itinerary.py \
  --artifact /home/r0x4n/otp-1a/probe-artifacts-1b-final/baseline-a.json \
  --database-url 'postgresql://postgres@127.0.0.1:5432/mobility' \
  --schema gtfs_eav
```

La password non è inclusa: il container usa l'autenticazione locale del
compose. Il container è lasciato attivo; l'arresto è
`docker compose stop` (senza `down -v`).
