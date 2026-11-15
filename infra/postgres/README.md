# PostgreSQL 18 + PostGIS + GTFS / OSM Ingestion Container

Container Docker basato su **Ubuntu Server 24.04 (Noble LTS)** configurato per la gestione dei dati geospaziali e di trasporto pubblico di Napoli per l'Hackathon 2026.

## Componenti inclusi

- **Ubuntu 24.04 LTS (Noble Numbat)** come sistema operativo base.
- **PostgreSQL 18** (da repository ufficiale PGDG `apt.postgresql.org`).
- **PostGIS 3** (`postgresql-18-postgis-3` + estensione di topologia).
- **Node.js 22 LTS & npm**.
- **`gtfs-via-postgres` 4.13.0** (versione fissata nel Dockerfile, comando `gtfs-to-sql`).
- **Cron daemon** attivo nel container con schedulazione automatica ogni primo del mese (`0 3 1 * *`).
- **Script di Ingestion (`download-monthly.sh`)**:
  - Download del file PBF da Geofabrik (`https://download.geofabrik.de/europe/italy/sud-latest.osm.pbf`).
  - Download di un archivio ZIP GTFS (`https://www.anm.it/google/google-transit.zip` di default).
  - Import controllato in schemi dedicati (`gtfs_anm` per il download ANM, `gtfs_eav` per il feed EAV validato), con staging, confronto conteggi e pubblicazione atomica tramite `import-gtfs.sh`.
- **Tool spaziali addizionali**: `osm2pgsql`, `osmium-tool`, `unzip`, `curl`.

---

## Architettura delle Directory

All'interno del container e sui volumi persistenti:

```
/data/
├── gtfs/
│   ├── gtfs-latest.zip             # Ultimo archivio GTFS valido
│   └── gtfs-download-YYYYMMDD.bin  # Storico dei download
└── osm/
    ├── sud-latest.osm.pbf          # Ultimo estratto OpenStreetMap PBF
    └── sud-YYYYMMDD.osm.pbf        # Copia archiviata con data
```

---

## Come Avviare il Container

### Con Docker Compose (consigliato se docker è installato)
Dalla root del repository:
```bash
docker compose up -d --build
```

### Con Podman (presente sul sistema host)
È possibile effettuare il build ed avviare il container direttamente con Podman:

```bash
# 1. Build dell'immagine
podman build -t napoli-postgres-mobility:latest -f infra/postgres/Dockerfile infra/postgres

# 2. Creazione della directory dati locale
mkdir -p data/gtfs data/osm

# 3. Avvio del container
podman run -d \
  --name napoli-postgres-mobility \
  -p 5432:5432 \
  -e POSTGRES_DB=mobility \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e RUN_ON_STARTUP=true \
  -e SKIP_PBF_DOWNLOAD=false \
  -v postgres_data:/var/lib/postgresql:Z \
  -v $(pwd)/data:/data:Z \
  napoli-postgres-mobility:latest
```

---

## Variabili di Configurazione (.env)

| Variabile | Default | Descrizione |
|---|---|---|
| `POSTGRES_DB` | `mobility` | Nome del database PostgreSQL da creare |
| `POSTGRES_USER` | `postgres` | Nome dell'utente amministratore |
| `POSTGRES_PASSWORD` | `postgres` | Password dell'utente |
| `POSTGRES_PORT` | `5432` | Porta esposta sull'host |
| `GTFS_URL` | `https://www.anm.it/google/google-transit.zip` | URL di un archivio ZIP GTFS (non una pagina HTML) |
| `GTFS_FALLBACK_URL` | vuoto | URL ZIP alternativo opzionale |
| `GTFS_SCHEMA` | `gtfs_anm` | schema PostgreSQL aggiornato dal download automatico (ANM) |
| `GTFS_DATASET_KEY` | `anm` | chiave del dataset ANM nei metadati |
| `GTFS_DATASETS` | `eav:gtfs_eav,anm:gtfs_anm` | feed esposti insieme dal backend; EAV resta visibile |
| `OTP_REBUILD_ENABLED` | `true` | dopo un import valido scrive la richiesta di rebuild OTP |
| `OTP_REBUILD_REQUEST_DIR` | `/data/otp-rebuild` | directory di scambio con il servizio OTP sull'host |
| `OSM_SCHEMA` | `osm_territory` | schema PostgreSQL del catalogo OSM/PostGIS |
| `OSM_DATASET_KEY` | `osm_napoli` | chiave del dataset OSM nei metadati |
| `GTFS_OPERATOR_ID` | `ANM` | operatore registrato per il download automatico |
| `GTFS_OPERATOR_NAME` | `Azienda Napoletana Mobilità` | nome operatore registrato |
| `PBF_URL` | `https://download.geofabrik.de/europe/italy/sud-latest.osm.pbf` | URL del file OpenStreetMap PBF |
| `RUN_ON_STARTUP` | `true` | Esegue un ciclo di download immediato all'avvio |
| `AUTO_IMPORT_GTFS` | `true` | Importa automaticamente il GTFS con staging e pubblicazione controllata |
| `SKIP_PBF_DOWNLOAD` | `false` | Se impostato su `true`, evita il download del file PBF (~420MB) |

---

## Schedulazione Cron

Il cron job è configurato in `/etc/cron.d/monthly-downloads`:
```cron
0 3 1 * * root /usr/local/bin/download-monthly.sh >> /var/log/monthly-download.log 2>&1
```
Esegue il download alle **03:00 del primo giorno di ogni mese**.

Per forzare l'esecuzione manuale del download in qualsiasi momento:
```bash
# Con Docker:
docker exec -it napoli-postgres-mobility /usr/local/bin/download-monthly.sh

# Con Podman:
podman exec -it napoli-postgres-mobility /usr/local/bin/download-monthly.sh
```

---

## Verifica e Accesso al Database

### Test connessione PostgreSQL e PostGIS:
```bash
# Connessione interattiva tramite psql
podman exec -it napoli-postgres-mobility psql -U postgres -d mobility -c "SELECT version();"
podman exec -it napoli-postgres-mobility psql -U postgres -d mobility -c "SELECT PostGIS_Full_Version();"
```

### Import manuale controllato:
```bash
infra/postgres/import-gtfs.sh --zip /percorso/feed.gtfs.zip \
  --dataset-key eav --schema gtfs_eav --publish
```

Lo schema precedente viene conservato come `gtfs_eav_prev_<timestamp>`.
Gli identificativi originali GTFS restano invariati; il prefisso OTP
`feedId:` è assegnato dal grafo e va letto da OTP, non assunto.

Import OSM/PostGIS controllato:

```bash
infra/postgres/import-osm.sh --pbf /percorso/estratto.osm.pbf \
  --snapshot sud-261113 --osm-timestamp 2026-11-14T01:23:15Z \
  --expected-sha256 <sha256> --publish
```

`osm2pgsql` 1.11.0 usa lo stile flex `osm-territory.lua` e scrive in staging.
La pubblicazione aggiorna per `osm_key` le tabelle stabili
`osm_territory.osm_ways` e `osm_territory.pois`; le righe non più presenti
restano con `is_current=false`. Non è una rete topologica e non sostituisce
OTP. Il catalogo è interrogabile dal backend con `OSMTerritoryRepository`.

`osm_datasets.osm_timestamp` registra il `Last-Modified` HTTP della sorgente;
`osm_datasets.data_timestamp` registra il timestamp effettivo dell'ultimo
oggetto OSM nel PBF (da `osmium fileinfo`). Non sono lo stesso valore.

Se `OTP_REBUILD_ENABLED=true`, dopo una pubblicazione GTFS riuscita
`download-monthly.sh` verifica che l'hash del file coincida con
`gtfs_datasets.source_sha256` e scrive una richiesta atomica in
`/data/otp-rebuild/request.json`. Sull'host il servizio utente
`otp-graph-sync.path` avvia `infra/otp/sync_graph_from_request.sh`, che
ricostruisce il grafo OTP dagli stessi ZIP, lo valida sulla porta 8081 e
sostituisce il servizio live solo dopo health check. Il timer
`otp-graph-sync.timer` riconcilia ogni 15 minuti anche in caso di richiesta
persa. Il vecchio grafo resta come versione precedente.

Gli import GTFS/OSM sincronizzano anche `public.reference_entities`, il
catalogo stabile usato dalle FK delle perturbazioni. Le tabelle
`service_alerts`, `service_alert_links` e `service_alert_revisions` sono
create dalla migrazione 004; nessun oggetto del catalogo viene cancellato
durante un refresh.

### Visualizzazione dei log del cron e del download:
```bash
podman exec -it napoli-postgres-mobility tail -f /var/log/monthly-download.log
```
