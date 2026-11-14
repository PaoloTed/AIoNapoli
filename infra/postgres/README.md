# PostgreSQL 18 + PostGIS + GTFS / OSM Ingestion Container

Container Docker basato su **Ubuntu Server 24.04 (Noble LTS)** configurato per la gestione dei dati geospaziali e di trasporto pubblico di Napoli per l'Hackathon 2026.

## Componenti inclusi

- **Ubuntu 24.04 LTS (Noble Numbat)** come sistema operativo base.
- **PostgreSQL 18** (da repository ufficiale PGDG `apt.postgresql.org`).
- **PostGIS 3** (`postgresql-18-postgis-3` + estensione di topologia).
- **Node.js 22 LTS & npm**.
- **`gtfs-via-postgres`** (con comandi CLI `gtfs-to-sql` e alias `gtfs-via-postgres`).
- **Cron daemon** attivo nel container con schedulazione automatica ogni primo del mese (`0 3 1 * *`).
- **Script di Ingestion (`download-monthly.sh`)**:
  - Download del file PBF da Geofabrik (`https://download.geofabrik.de/europe/italy/sud-latest.osm.pbf`).
  - Download del file GTFS dalla sorgente specificata (`https://www2.anm.it/infoclick/infoclick.php?palina=3010`, con supporto a fallback o URL personalizzati).
  - Estrazione automatica ed import dei feed GTFS nel database PostgreSQL/PostGIS tramite `gtfs-to-sql`.
- **Tool spaziali addizionali**: `osm2pgsql`, `osmium-tool`, `unzip`, `curl`.

---

## Architettura delle Directory

All'interno del container e sui volumi persistenti:

```
/data/
├── gtfs/
│   ├── current/                    # File .txt decompressi dal feed GTFS
│   ├── gtfs-latest.zip             # Ultimo archivio GTFS valido
│   ├── infoclick-palina-3010.html  # Dump della risposta se la sorgente è HTML
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
| `GTFS_URL` | `https://www2.anm.it/infoclick/infoclick.php?palina=3010` | URL primario da scaricare |
| `GTFS_FALLBACK_URL` | URL Open Data Napoli (`google_transit.zip`) | URL alternativo GTFS se l'URL primario è un endpoint HTML/web |
| `PBF_URL` | `https://download.geofabrik.de/europe/italy/sud-latest.osm.pbf` | URL del file OpenStreetMap PBF |
| `RUN_ON_STARTUP` | `true` | Esegue un ciclo di download immediato all'avvio |
| `AUTO_IMPORT_GTFS` | `true` | Importa automaticamente i dati GTFS in Postgres con `gtfs-to-sql` |
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

### Visualizzazione dei log del cron e del download:
```bash
podman exec -it napoli-postgres-mobility tail -f /var/log/monthly-download.log
```
