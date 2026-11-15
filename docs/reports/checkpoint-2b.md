# CHECKPOINT 2B — Territorio OSM in PostGIS

Data: 2026-11-15 (Europe/Rome). Perimetro: import di strade e POI OSM nel
database Docker `mobility`, schema dedicato `osm_territory`, catalogo di
ricerca per il backend. Non sono stati modificati il grafo OTP, gli agenti,
il frontend, gli endpoint di viaggio, il GTFS o le tabelle delle perturbazioni.

## 1. Ambiente e stato iniziale

Docker è stato usato con `sg docker` (l'utente appartiene al gruppo ma il
processo della sessione precedente non lo aveva acquisito); nessun permesso
del socket è stato modificato.

Stato verificato prima dell'import:

- progetto Compose `hackaton2026cds`;
- container `napoli-postgres-mobility`, `healthy`;
- volume `hackaton2026cds_postgres_data`;
- database Docker `mobility`, porta host `5432`;
- PostgreSQL 18.7 + PostGIS 3.6.2;
- GTFS `gtfs_eav`: 7.415 trip, 4.208 stop, 280.889 stop_times;
- `gtfs_imports`: 2 run pubblicate;
- sentinella 2A `checkpoint-2a-docker-sentinel`: presente;
- `/var/log/monthly-download.log`: vuoto.

L'istanza `mobility_2a` sulla porta `55432` è la prova locale precedente e
**non** è stata usata in 2B.

## 2. Sorgente OSM riusata

File già prodotto in 1A, non riscaricato:

| Metadato | Valore |
|---|---|
| Percorso host | `/home/r0x4n/otp-1a/osm/napoli-eav-261113.osm.pbf` |
| Percorso container | `/data/osm/napoli-eav-261113.osm.pbf` |
| Dimensione | 58.877.279 byte |
| SHA-256 | `ca4164b471edd76fb2f5f94aab34aed4e0319104f7ad043e36c4c36ff7a71192` |
| Fonte | Geofabrik `sud-261113.osm.pbf` |
| URL effettivo | `https://download.geofabrik.de/europe/italy/sud-261113.osm.pbf` |
| Last-Modified | `2026-11-14T01:23:15Z` |
| Ultimo oggetto OSM | `2026-11-13T21:03:47Z` |
| Attribuzione | OpenStreetMap contributors, ODbL 1.0 |
| Header bbox | `13.80,40.55,14.85,41.40` |
| Bbox dati effettiva | `9.107,36.794,15.690,41.757` |
| Oggetti | 7.672.022 nodi, 966.954 way, 14.603 relation |

L'header bbox è quello dell'estratto creato in 1A (fermate EAV + margine); la
bbox dei dati è più ampia perché `osmium extract --strategy=complete_ways`
include le way complete. **Non è l'intera area metropolitana** e non è un
confine amministrativo.

`osmium fileinfo -e` e lo SHA-256 sono stati rieseguiti dentro il container
prima dell'import.

Distinzione dei timestamp (verificata in 2C): `osm_datasets.osm_timestamp`
conserva il `Last-Modified` HTTP `2026-11-14T01:23:15Z`; il timestamp
effettivo degli oggetti nel PBF è invece `2026-11-13T21:03:47Z` (ultimo
oggetto, da `osmium fileinfo`) ed è registrato in
`osm_datasets.data_timestamp`. Non sono lo stesso valore e non vanno
confusi.

## 3. Importatore, versione e schema

- `osm2pgsql` effettivamente disponibile nel container: **1.11.0**,
  Libosmium 2.20.0, Proj 9.4.0, Lua 5.3.6.
- `osmium` nel container: 1.16.0 (l'estratto 1A era stato prodotto con
  osmium 1.19.0).
- Output flex, stile `infra/postgres/osm-territory.lua`, SRID **4326**.
- Schema dedicato `osm_territory`, separato da `public` e `gtfs_eav`.
- Con `--extra-attributes` sono conservati `osm_version` e `osm_timestamp`
  dell'oggetto; la versione del dataset è registrata nei metadati.

Tabelle pubblicate:

| Tabella | Geometria | Contenuto |
|---|---|---|
| `osm_territory.osm_ways` | `LineString,4326` | way con `highway` |
| `osm_territory.pois` | `Geometry,4326` + `Point,4326` | nodi, way chiuse, relation POI |

`osm_ways` conserva `osm_key`, `osm_type`, `osm_id`, nome, `ref`, `highway`,
accesso (`access`, `foot`, `bicycle`, `motor_vehicle`, `vehicle`), direzione
(`oneway`, `junction`), `bridge`, `tunnel`, `layer`, superficie, servizio,
limiti, larghezza, `tracktype`, `smoothness`, `wheelchair`, `incline`,
`sidewalk`, `cycleway`, `footway`, `segregated`, `construction`, `route`,
tags JSONB completi, provenienza, versione e timestamp.

`pois` conserva nome, `name:it`, `ref`, operator/brand, indirizzo, telefono,
sito, orari, accessibilità, categoria, tags JSONB, geometria originale e
`label_point` per la ricerca. Per i poligoni la geometria originale resta
poligonale; il punto rappresentativo è calcolato con `ST_PointOnSurface`.

Metadati: `public.osm_imports` (una riga per tentativo, con hash, versione,
staging, stato e conteggi) e `public.osm_datasets` (dataset attivo,
snapshot, timestamp, attribuzione ODbL).

## 4. Import reale e conteggi

Comando eseguito **dentro il container**, con PBF già validato:

```bash
docker exec napoli-postgres-mobility bash /usr/local/bin/import-osm.sh \
  --pbf /data/osm/napoli-eav-261113.osm.pbf \
  --snapshot sud-261113 --osm-timestamp 2026-11-14T01:23:15Z \
  --expected-sha256 ca4164b471edd76fb2f5f94aab34aed4e0319104f7ad043e36c4c36ff7a71192 \
  --source-url https://download.geofabrik.de/europe/italy/sud-261113.osm.pbf \
  --publish
```

Conteggi pubblicati:

| Elemento | Conteggio |
|---|---:|
| way OSM con `highway` | 204.803 |
| POI da nodi | 55.786 |
| POI da way chiuse | 41.068 |
| POI da relation | 1.083 (904 polygon, 179 multipolygon) |
| POI totali | 97.937 |

Tempo: circa **56 s** la prima pubblicazione riuscita (import + validazione +
publish), circa **67 s** la seconda. Il primo tentativo è fallito per
un'opzione CLI errata (`--username` invece di `--user`) ed è rimasto
registrato come `failed`; il comando è stato corretto e le run successive
sono `published`.

Spazio: database Docker circa **1,09 GB** (1.087 MB), volume circa **2,1 GB**;
`osm_ways` 343 MB totali (261 MB heap), `pois` 190 MB totali (125 MB heap).
Lo staging viene rimosso dopo la pubblicazione; l'audit resta in
`osm_imports`.

## 5. Geometrie e indici

Verifiche eseguite sul database Docker:

```text
osm_ways: 204.803, is_current=true; bad geometry/SRID: 0
pois:      97.937, is_current=true; bad geometry/SRID: 0
```

- tutte le geometrie hanno SRID **4326**;
- `osm_ways.geom` è `ST_LineString`;
- `pois.geom` contiene `ST_Point`, `ST_Polygon` e `ST_MultiPolygon`;
- `ST_IsValid` è true per tutte le geometrie e per tutti i `label_point`;
- indici: 15, inclusi GIST su `osm_ways.geom`, `pois.geom` e
  `pois.label_point`, btree/GIN trigram su nome e ref, GIN su tags JSONB.

## 6. Way OSM, non segmento topologico

`osm_territory.osm_ways` contiene **way OSM**, non segmenti di una rete
navigabile. Non sono stati costruiti nodi di giunzione, archi, sensi unici
applicati al routing o curve di svolta. La presenza di geometrie stradali
non dimostra che esista un percorso calcolabile: il routing resta compito di
OTP e il grafo OTP non è stato modificato.

Non sono stati inventati civici, accessibilità, pendenze o altri attributi
assenti: i campi non presenti in OSM restano `NULL`.

## 7. Accesso dal backend

Nuovo `backend/app/repositories/territory.py` (`OSMTerritoryRepository`):

- `search_ways(query, limit)` e `search_pois(query, limit)` con più
  candidati, ordinamento exact/prefix, query parametrizzate;
- `get_way(osm_key)` e `get_poi(osm_key)`;
- `find_ways_near(lon, lat, radius_m, limit)` e
  `find_pois_near(...)` con `ST_DWithin`/`ST_Distance` su `geography`, quindi
  distanze in **metri**;
- `find_ways_intersecting(min_lon, min_lat, max_lon, max_lat, limit)` con
  `ST_Intersects` e `ST_MakeEnvelope` in 4326;
- `get_dataset_info()`.

`BackendService` espone `territory_repository` quando `APP_PROFILE=postgres`;
non è stato aggiunto alcun endpoint HTTP. Il catalogo non è un geocoder
completo: non risolve indirizzi, civici o alias.

Esempi verificati:

| Ricerca | Candidati (osm_key, coordinate label/midpoint) |
|---|---|
| `Via Toledo` | `way/183292041` (14.249297, 40.846098); `way/19067468` (14.249047, 40.843999); `way/208610623` (14.248458, 40.839668) |
| `Riviera di Chiaia` | `way/1136492073` (14.240891, 40.833079); `way/1301846511` (14.240920, 40.832725); `way/339324897` (14.238288, 40.833272) |
| `Castel dell'Ovo` | `way/338168783` (14.248028, 40.827742); `node/4155636414` (14.245950, 40.830455) |
| `Museo archeologico nazionale di Napoli` | `relation/3824019` (14.251150, 40.853606) |

Query spaziale: `find_ways_near(14.2495, 40.8479, 300 m)` restituisce
`Via Toledo` a 2,0 m e altre way entro 300 m;
`find_pois_near(14.2480, 40.8277, 300 m)` restituisce `Castel dell'Ovo` a
5,2 m. `find_ways_intersecting(14.248, 40.846, 14.251, 40.849)` restituisce
10 way, tra cui `Piazza Dante`.

Evidenza JSON: `/home/r0x4n/otp-1a/checkpoint-2b-search.json`.

## 8. Staging, pubblicazione e refresh

`import-osm.sh` importa in `osm_territory_stage_<UTC>` e valida conteggi,
SRID, tipi e validità. La pubblicazione avviene in una transazione con
advisory lock:

1. marca `is_current=false` sulle righe pubblicate precedenti;
2. inserisce/aggiorna per `osm_key` le righe dello staging;
3. aggiorna `osm_datasets` e `osm_imports`;
4. elimina solo lo staging, se non richiesto di conservarlo.

Le tabelle pubblicate **non vengono rinominate**: mantengono lo stesso OID,
quindi eventuali FK future verso `osm_territory.osm_ways(osm_key)` o
`osm_territory.pois(osm_key)` restano valide. Le righe non più presenti in
un nuovo estratto non vengono cancellate: restano con `is_current=false`,
`first_seen_at` e `last_seen_at`. La versione è in `dataset_version` e
`source_sha256`; le future perturbazioni possono referenziare
`osm_key` + `dataset_version`, senza dipendere dal nome di uno schema di
staging.

In questa prova, con lo stesso estratto:

| Controllo | Prima | Dopo seconda |
|---|---:|---:|
| `osm_territory.osm_ways` | 204.803 | 204.803 |
| `osm_territory.pois` | 97.937 | 97.937 |
| duplicati per `osm_key` | 0 | 0 |
| `osm_datasets` | 1 | 1 |
| `osm_imports` pubblicate | 1 | 2 |
| `way/269910733.first_seen_at` | 00:41:32.345 | 00:41:32.345 |
| `way/269910733.last_seen_at` | 00:41:32.345 | 00:43:10.883 |

Nessuna tabella delle perturbazioni è stata creata.

## 9. GTFS invariato e persistenza

Dopo l'import OSM e dopo il secondo import:

```text
gtfs_eav.trips            7.415
gtfs_imports              2
gtfs_datasets             1 (EAV, hash 9a3eeba9a84c...)
checkpoint-2a sentinel    1
osm_territory.osm_ways    204.803
osm_territory.pois        97.937
```

Il container è stato riavviato con `docker restart`: è tornato `healthy` e
tutti i conteggi, il dataset OSM, il GTFS e la sentinella 2A erano ancora
presenti nel volume `hackaton2026cds_postgres_data`.

## 10. Test e riproducibilità

- suite ordinaria: **118 passed, 4 skipped**;
- test PostgreSQL OSM live (`OSM_TEST_DATABASE_URL`): **2 passed**;
- test PostgreSQL GTFS live: **2 passed**;
- `ruff check`: nessun errore;
- `bash -n` su `import-osm.sh`: nessun errore;
- `docker compose build` e avvio: riusciti; container `healthy`;
- `/var/log/monthly-download.log` vuoto: nessun download automatico.

Comandi principali (senza credenziali):

```bash
sg docker -c 'docker context show && docker ps -a && docker volume ls'

RUN_ON_STARTUP=false AUTO_IMPORT_GTFS=false SKIP_PBF_DOWNLOAD=true \
  docker compose up -d --build

APP_PROFILE=postgres DATABASE_URL='postgresql://postgres@127.0.0.1:5432/mobility' \
  python -m app.cli db migrate

docker cp /home/r0x4n/otp-1a/osm/napoli-eav-261113.osm.pbf \
  napoli-postgres-mobility:/data/osm/napoli-eav-261113.osm.pbf

docker exec napoli-postgres-mobility bash /usr/local/bin/import-osm.sh \
  --pbf /data/osm/napoli-eav-261113.osm.pbf \
  --snapshot sud-261113 --osm-timestamp 2026-11-14T01:23:15Z \
  --expected-sha256 ca4164b471edd76fb2f5f94aab34aed4e0319104f7ad043e36c4c36ff7a71192 \
  --source-url https://download.geofabrik.de/europe/italy/sud-261113.osm.pbf \
  --publish
```

## 11. Limiti

- L'estratto non è l'intera area metropolitana: header bbox EAV + margine,
  bbox dati più ampia per `complete_ways`.
- Il catalogo non è una rete topologica e non è usato dal routing; OTP resta
  l'unico motore di percorso.
- Non sono un geocoder completo: nessuna risoluzione di indirizzi, civici,
  alias o ambiguità.
- I POI sono quelli con categorie selezionate dallo stile; non tutti gli
  oggetti OSM e non tutti gli edifici sono importati.
- I campi assenti in OSM restano assenti; nessun civico, accessibilità o
  pendenza è stato dedotto.
- Un solo snapshot OSM è stato importato; il refresh richiede un nuovo PBF e
  una nuova versione/hash, con gli stessi controlli.
- Lo staging viene eliminato dopo la pubblicazione; l'audit è in
  `osm_imports`/`osm_datasets`.
- Fuori perimetro: 2C perturbazioni, matching imprevisti, modifiche a OTP,
  agenti, frontend o endpoint.
