# CHECKPOINT — GTFS ANM, database multi-dataset e grafo OTP EAV+ANM

Data: 2026-11-15 (Europe/Rome). Perimetro: acquisizione/validazione del GTFS
ANM, import nel database Docker `mobility`, supporto multi-dataset del backend,
build OTP con OSM + EAV + ANM, prove di routing e regressione EAV.

**Esito: COMPLETO.** ANM ed EAV sono entrambi presenti nel database Docker e nel
nuovo grafo OTP. Il viaggio Via Giovanni Antonio Campano → Città della Scienza
e il viaggio ingresso metro Chiaiano → Città della Scienza restituiscono
itinerari con trasporto pubblico, anche con `transitOnly=true`. I servizi ANM
richiesti (Linea 1, Chiaiano, Città della Scienza) sono presenti e attivi alla
data di prova. Non è stato integrato BusOne realtime.

## 1. Ricognizione: dove si trova il GTFS ANM

Accesso Docker usato con `sg docker` (l'utente è nel gruppo `docker` ma il
processo della sessione non lo aveva acquisito). Nessun permesso del socket è
stato modificato.

Stato iniziale verificato:

```text
container   napoli-postgres-mobility, healthy
immagine    hackaton2026cds-db
mount       /data -> /home/r0x4n/hackaton2026CDS/data (bind, rw)
            /var/lib/postgresql -> volume hackaton2026cds_postgres_data
/data/gtfs  eav-technical.gtfs.zip (4.105.995 byte)
/data/osm   napoli-eav-261113.osm.pbf (58.877.279 byte)
```

Nel container e sull'host **non esisteva un GTFS ANM**. Gli unici file
candidati erano:

| File | Verifica | Esito |
|---|---|---|
| `/data/gtfs/eav-technical.gtfs.zip` | `agency.txt`: `NA0004` / `EAVO`, “Eav srl” | **EAV**, non ANM |
| `/home/r0x4n/Scaricati/google-transit.zip` | stesso SHA-256 del file EAV | **EAV**, non ANM |
| `anm_info/` e `anm_info.zip` | scraper/news ANM, nessun `agency.txt`/GTFS | non è un GTFS |

Il file chiamato `google-transit.zip` usato nei checkpoint precedenti è quindi
EAV: SHA-256
`9a3eeba9a84ce7de11e3daf1e1727e60705ab89a0a9f8ea369105ff436716df9`.
I metadati `public.gtfs_datasets`/`gtfs_imports` confermavano un solo dataset
pubblicato, `eav` → `gtfs_eav`.

### Acquisizione ANM dalla fonte configurata

Fonte usata: `https://www.anm.it/google/google-transit.zip`, la stessa
configurata in Docker/`.env.example`. La risposta è un redirect HTTPS verso
`anmspa.file.force.com`; contenuto finale:

| Metadato | Valore |
|---|---|
| Content-Type | `application/zip` |
| Content-Length | 6.257.032 byte |
| SHA-256 | `ac0dfd987b734022efde05e98b312b59ddde68a8e49c77564e8bfbdb641f15b4` |
| Test ZIP | `unzip -t`: nessun errore |
| Data interna file | 2026-11-03 |
| `feed_info.txt` | assente |

Copia conservata come
`data/gtfs/anm-google-transit-20261103.gtfs.zip` e verificata nel container con
lo stesso SHA-256. Non è stata dedotta la copertura dal nome del file.

**Nota sui nomi.** L’URL configurato è ANM e la risposta HTTP ha
`Content-Disposition: attachment; filename="google-transit.zip"`, ma il file
locale `google-transit.zip` usato nei checkpoint precedenti
(`/home/r0x4n/Scaricati/google-transit.zip`, 4.105.995 byte) contiene EAV:
verificato da `agency.txt` (`NA0004`, `EAVO`). Lo script
`download-monthly.sh` salva il download ANM in `gtfs-latest.zip`, non in
`google-transit.zip`; al momento dell’ispezione nel container non esisteva
alcun `gtfs-latest.zip` né alcun `google-transit.zip`. I due file ora presenti
sono distinti:

| File container | Byte | `agency.txt` | SHA-256 |
|---|---:|---|---|
| `eav-technical.gtfs.zip` | 4.105.995 | `NA0004`, `EAVO` | `9a3eeba9...` |
| `anm-google-transit-20261103.gtfs.zip` | 6.257.032 | `ANM`, `FS` | `ac0dfd98...` |

Quindi “google-transit” nel nome/URL non identifica l’operatore: l’operatore
è stato stabilito solo dal contenuto `agency.txt`.

## 2. Validazione del dataset ANM

Contenuto del feed:

| Entità | Conteggio |
|---|---:|
| `agency` | 2 (`ANM`, `FS`/Trenitalia) |
| `routes` | 112 |
| `trips` | 32.177 |
| `stops` | 2.392 |
| `stop_times` | 705.644 |
| `calendar_dates` | 1.239 |
| `shapes` (punti) | 34.250 |
| `service_days` | 1.239 |
| `calendar.txt` | assente |

Calendario: **2026-11-09 .. 2026-12-31**, tutte le 1.239 righe
`calendar_dates` sono `exception_type=1` (servizi aggiunti). Non sono stati
prolungati calendari scaduti né create corse. Sulla data di prova
**2026-11-16** risultano attive **10.900 corse / 109 route**.

Copertura richiesta, verificata per ID e non per nome dell'operatore:

| Elemento | ID / dato | Verifica |
|---|---|---|
| Metro Linea 1 | route `4955`, `route_short_name=L1`, `route_type=1`, “METRO LINEA L1” | 706 corse totali, 226 attive il 2026-11-16 |
| Chiaiano | stop `6312`, “CHIAIANO”, 40.890978, 14.223564 | servita da L1 |
| Città della Scienza | stop `2002` 40.805264,14.174026 e `2167` 40.804463,14.174222, “COROGLIO - CITTÀ DELLA SCIEZA” | servita da R7 e C1 |
| R7 | route `3216`, bus | 72 corse attive il 2026-11-16 |
| C1 | route `3438`, bus | 48 corse attive il 2026-11-16 |

Il nome della fermata contiene il refuso “SCIEZA”: è il dato originale ANM,
non è stato corretto né reinterpretato. Il feed include anche la route `4778`
“METRO LINEA L2” dell’agenzia `FS` (Trenitalia), quindi `agency_ids` del
dataset è `ANM,FS`. Non mancano servizi necessari per i due viaggi richiesti.

## 3. Integrazione nel database Docker `mobility`

### 3.1 Correzione dell’importatore

`infra/postgres/import-gtfs.sh` calcolava `TARGET_SCHEMA` e `STAGING_SCHEMA`
prima di leggere `--dataset-key`/`--schema`. Con `GTFS_SCHEMA=gtfs_eav`
nell’ambiente, un import ANM creava uno staging chiamato `gtfs_eav_stage_*`.
La correzione deriva target e staging **dopo** il parsing degli argomenti:

```bash
TARGET_SCHEMA="${TARGET_SCHEMA:-gtfs_${DATASET_KEY}}"
STAGING_SCHEMA="${STAGING_SCHEMA:-${TARGET_SCHEMA}_stage_$(date -u +%Y%m%d%H%M%S)}"
```

Lo script corretto è stato copiato nel container e verificato con lo stesso
SHA-256 del repository (`fc089037...`).

### 3.2 Import controllato

Comando eseguito nel container (prima due validazioni, poi pubblicazione):

```bash
docker exec -e PGUSER=postgres -e PGDATABASE=mobility \
  napoli-postgres-mobility bash /usr/local/bin/import-gtfs.sh \
  --zip /data/gtfs/anm-google-transit-20261103.gtfs.zip \
  --dataset-key anm --schema gtfs_anm --operator-id ANM \
  --operator-name "Azienda Napoletana Mobilità" \
  --source-url https://www.anm.it/google/google-transit.zip --publish
```

Run registrate in `public.gtfs_imports`:

| Run | Dataset | Esito | Note |
|---:|---|---|---|
| 4 | anm | validated | primo staging, nome `gtfs_eav_stage_...` precedente alla correzione |
| 5 | anm | validated | staging corretto `gtfs_anm_stage_...`, non pubblicato |
| 6 | anm | published | pubblicazione atomica in `gtfs_anm` |

`public.gtfs_datasets` contiene ora due righe attive:

| dataset | schema | operatore | agenzie | validità | SHA-256 |
|---|---|---|---|---|---|
| `eav` | `gtfs_eav` | Eav srl | EAVO,NA0004 | 2025-09-15..2030-12-31 | `9a3eeba9...` |
| `anm` | `gtfs_anm` | Azienda Napoletana Mobilità | ANM,FS | 2026-11-09..2026-12-31 | `ac0dfd98...` |

Conteggi DB ANM: 2 agency, 112 route, 32.177 trip, 2.392 stop, 705.644
stop_times, 1.239 calendar_dates, 34.250 shape point, 1.239 service_days.

### 3.3 Supporto multi-dataset nel backend

Il repository non è stato commutato da EAV ad ANM. Sono state aggiunte più
fonti contemporanee:

- `AppConfig.gtfs_datasets: dict[str, str]` e variabile
  `GTFS_DATASETS`, default `eav:gtfs_eav,anm:gtfs_anm`;
- `PostgresSourceRepository(..., gtfs_datasets=[...])` legge tutti i dataset
  configurati e verifica che `gtfs_datasets.gtfs_schema` corrisponda allo
  schema richiesto;
- con più dataset gli ID esposti sono **dataset-scoped**
  (`eav:6238`, `anm:6238`), mentre gli ID originali restano disponibili in
  `gtfs_stop_id`, `gtfs_route_id`, `gtfs_trip_id`, `gtfs_shape_id`;
- `get_datasets_info()` restituisce tutti i feed; `get_dataset_info()` resta
  compatibile e restituisce il primario;
- EAV e ANM hanno tre `stop_id` numericamente uguali (`6238`, `6278`, `6323`):
  il namespace impedisce la collisione.

Verifica live del repository sul database Docker:

```text
datasets            eav/gtfs_eav, anm/gtfs_anm
stops               6.600 = 4.208 EAV + 2.392 ANM
routes              236 = 124 EAV + 112 ANM
active trips        11.582 = 682 EAV + 10.900 ANM (2026-11-16)
collisioni          eav:6238 / anm:6238, eav:6278 / anm:6278, eav:6323 / anm:6323
L1                  anm:4955, gtfs_route_id=4955
Chiaiano            anm:6312, gtfs_stop_id=6312
```

La migrazione `005_gtfs_reference_namespaces.sql` rende distinti anche gli
`entity_key` del catalogo delle perturbazioni:
`gtfs:{dataset_key}:{entity_type}:{entity_id}`. Dopo la migrazione è stata
rieseguita la sincronizzazione EAV: `reference_entities` GTFS contiene 124
route, 4.208 stop e 7.415 trip EAV, più 112 route, 2.392 stop e 32.177 trip
ANM. I link esistenti sono rimasti risolti; nessun dato è stato cancellato.

Conservati: `gtfs_eav`, `gtfs_anm`, `osm_territory` (204.803 way, 97.937 POI),
metadati, sentinella `checkpoint-2a-docker-sentinel`, volumi e schemi di
staging/backup precedenti.

## 4. Nuovo grafo OTP OSM + EAV + ANM

Build eseguita in una directory nuova, **senza sovrascrivere** il grafo EAV
funzionante:

```text
/home/r0x4n/otp-1a/otp-data/graph.obj        vecchio grafo EAV, 62 MB
/home/r0x4n/otp-1b-anm/otp-data/graph.obj    nuovo grafo, 94,7 MB
```

Input e hash:

| Input | SHA-256 |
|---|---|
| `napoli-eav-261113.osm.pbf` | `ca4164b471edd76fb2f5f94aab34aed4e0319104f7ad043e36c4c36ff7a71192` |
| `eav-technical.gtfs.zip` | `9a3eeba9a84ce7de11e3daf1e1727e60705ab89a0a9f8ea369105ff436716df9` |
| `anm-google-transit-20261103.gtfs.zip` | `ac0dfd987b734022efde05e98b312b59ddde68a8e49c77564e8bfbdb641f15b4` |
| `build-config.json` | `d32437f1bb70a4aa8982565d9e2daa2a25f3330c0d634d5010e3980ad77355d0` |

Config: `transitServiceStart=2025-09-15`, `transitServiceEnd=2030-12-31`,
`transitModelTimeZone=Europe/Rome`. Comando:

```bash
/usr/lib/jvm/java-25-openjdk-amd64/bin/java -Xms1g -Xmx4g \
  -jar /home/r0x4n/otp-1a/otp-shaded-2.10.0.jar \
  --build --save /home/r0x4n/otp-1b-anm/otp-data
```

Risultato: build in 48,2 s, max RSS 1.798.156 KiB (~1,7 GiB), 0 swap, grafo
94,7 MB, SHA-256
`3e22452fafe53656c13cf10639310262b4e287f80f5e06c816938ed2ec92941f`.
OTP ha caricato 6.600 fermate, 790 pattern, 27.043 transfer vincolati.
Warning noti: “stop index contains holes” (EAV 4.208 su 6.600) e island
pruning; non hanno impedito i collegamenti provati. Disco disponibile prima
della build: 373 GB; memoria disponibile: ~7,2 GiB.

Mapping feed osservato sul grafo (non assunto). Il `feedId` **cambia tra
build**: la build iniziale aveva feed `1`=EAV e `2`=ANM; la build successiva
del servizio persistente ha assegnato feed `1`=ANM e `2`=EAV. Non è quindi
lecito usare un prefisso fisso.

| Build | Feed `1` | Feed `2` |
|---|---|---|
| iniziale | EAV (`NA0004`,`EAVO`) | ANM (`ANM`,`FS`) |
| persistente attuale | ANM (`ANM`,`FS`) | EAV (`NA0004`,`EAVO`) |

Esempi attuali: OTP `1:4955` → `gtfs_anm.routes.route_id=4955`; OTP `2:2` →
`gtfs_eav.routes.route_id=2`; OTP `1:6312` →
`gtfs_anm.stops.stop_id=6312`; OTP `1:388_CodUdp:D600_31935133` →
`gtfs_anm.trips.trip_id=388_CodUdp:D600_31935133`.
Il mapping va sempre riletto da `feeds` e da `routes.agency.gtfsId`; è ciò
che fanno `OtpClient` e `verify_multi_dataset_itinerary.py`.

### Avvio, sostituzione e rollback

Il nuovo grafo è stato prima avviato sulla porta 8081 e validato. Solo dopo è
stato sostituito il servizio sulla 8080:

```bash
systemctl --user stop otp-1a
systemctl --user stop otp-1b-anm
systemd-run --user --unit=otp-1b-anm --collect \
  --working-directory=/home/r0x4n/otp-1b-anm \
  /bin/bash -lc 'exec /usr/lib/jvm/java-25-openjdk-amd64/bin/java \
    -Xms512m -Xmx2g -jar /home/r0x4n/otp-1a/otp-shaded-2.10.0.jar \
    --load --serve otp-data >> artifacts/otp-server.log 2>&1'
```

Il vecchio grafo EAV non è stato cancellato. Rollback:

```bash
systemctl --user stop otp-1b-anm
systemd-run --user --unit=otp-1a --collect \
  --working-directory=/home/r0x4n/otp-1a \
  /bin/bash -lc 'exec /usr/lib/jvm/java-25-openjdk-amd64/bin/java \
    -Xms512m -Xmx2g -jar otp-shaded-2.10.0.jar \
    --load --serve otp-data >> artifacts/otp-server.log 2>&1'
```

Dopo la validazione iniziale il servizio transiente `otp-1b-anm` è stato
sostituito dall’unità persistente `otp-mobility.service` (sezione 9), che
serve `/home/r0x4n/otp-live` sulla 8080. `otp-1a` resta ferma ma riavviabile
con il suo grafo originale.

## 5. Coordinate e prove di routing

### 5.1 Coordinate risolte

| Punto | Coordinate | Come è stato risolto |
|---|---|---|
| Via Giovanni Antonio Campano | 40.8943044, 14.2308735 | Nominatim → OSM way `511690651`; confermato in `osm_territory.osm_ways` (nome “Via Giovanni Antonio Campano”, centroide 40.894307,14.230873) |
| Ingresso metro Chiaiano | 40.8909785, 14.2235638 | fermata ANM `6312` “CHIAIANO” in `gtfs_anm.stops` |
| Città della Scienza | 40.8047221, 14.1745403 | Nominatim (museo, OSM way `1495677472`); la fermata ANM `2167` è a 40.804463,14.174222 |

La via è composta da più segmenti OSM; è stato usato il punto del segmento
`way/511690651`, il più orientale, come origine riproducibile. Non è stato
inventato un civico.

### 5.2 Prove dirette su OTP (porta 8080)

Data/ora: `2026-11-16T08:00:00+01:00` Europe/Rome. Modi:
`WALK, BUS, RAIL, SUBWAY`. Ricerca normale e `transitOnly=true` restituiscono
gli stessi 5 itinerari; sotto è riportato il primo.

**Caso A — Via Giovanni Antonio Campano → Città della Scienza**

Partenza richiesta 08:00. Primo itinerario: 08:08:02 → 09:31:31, durata
**5.009 s (83 min 29 s)**, 2 cambi, cammino 1.595 s.

| Leg | Orario | Route / trip / stop | Operatore |
|---|---|---|---|
| WALK | 08:08:02 → 08:24:00 (958 s) | Origin → `1:6311` PISCINOLA | — |
| SUBWAY L1 | 08:24:00 → 08:48:00 (1.440 s) | `1:4955`; trip `1:388_1000000002869_31909605`; `1:6311` → `1:6324` DANTE | ANM |
| WALK | 08:48:00 → 08:56:18 (498 s) | `1:6324` DANTE → `2:6801` Montesanto | — |
| *attesa* | *222 s* | | |
| RAIL 9. | 09:00:00 → 09:10:00 (600 s) | `2:9.`; trip `2:90900_opttp2026-2030-9`; `2:6801` → `2:6804` Mostra | EAV |
| WALK | 09:10:00 → 09:10:48 (48 s) | `2:6804` Mostra → `1:2153` TECCHIO - MOSTRA | — |
| *attesa* | *462 s* | | |
| BUS C1 | 09:18:30 → 09:30:00 (690 s) | `1:3438`; trip `1:388_CodUdp:D600_31935133`; `1:2153` → `1:2167` Città della Scienza | ANM |
| WALK | 09:30:00 → 09:31:31 (91 s) | `1:2167` → Destination | — |

Attesa iniziale 482 s; attese intermedie 222 s e 462 s.

**Caso B — ingresso metro Chiaiano → Città della Scienza**

Primo itinerario: 08:08:00 → 09:21:31, durata **4.411 s (73 min 31 s)**,
2 cambi, cammino 900 s.

| Leg | Orario | Route / trip / stop | Operatore |
|---|---|---|---|
| SUBWAY L1 | 08:08:00 → 08:30:00 (1.320 s) | `1:4955`; trip `1:388_1000000002869_31942551`; `1:6312` CHIAIANO → `1:6324` DANTE | ANM |
| WALK | 08:30:00 → 08:38:18 (498 s) | `1:6324` DANTE → `2:6801` Montesanto | — |
| *attesa* | *402 s* | | |
| RAIL 9 | 08:45:00 → 09:01:30 (990 s) | `2:9`; trip `2:9082_opttp2026-2030-8`; `2:6801` → `2:6808` Bagnoli | EAV |
| WALK | 09:01:30 → 09:06:41 (311 s) | `2:6808` Bagnoli → `1:2940` COROGLIO - ARENILE | — |
| *attesa* | *439 s* | | |
| BUS R7 | 09:14:00 → 09:20:00 (360 s) | `1:3216`; trip `1:388_CodUdp:D600_31900310`; `1:2940` → `1:2167` Città della Scienza | ANM |
| WALK | 09:20:00 → 09:21:31 (91 s) | `1:2167` → Destination | — |

Attesa iniziale 480 s; attese intermedie 402 s e 439 s.

Artefatti: `probe-artifacts-8080/`, `routing-summary.json`,
`verify-8080-*.json`. La prova è stata ripetuta identica sulla 8081 prima del
passaggio in produzione; i risultati coincidono.

### 5.3 Prova tramite backend

Il backend non espone un endpoint HTTP di travel planning; la prova è stata
fatta con `BackendService` + `MobilityAgent` reali, con
`APP_PROFILE=postgres`, `OTP_BASE_URL=http://127.0.0.1:8080` e configurazione
di default. Il repository ha letto entrambi i dataset e il client ha usato
`http://127.0.0.1:8080/otp/gtfs/v1`.

Caso Chiaiano (`anm:6312` → `anm:2167`), `now=2026-11-16T08:00 Europe/Rome`:

```text
config datasets      eav:gtfs_eav, anm:gtfs_anm
repository datasets  eav/gtfs_eav, anm/gtfs_anm
endpoint             http://127.0.0.1:8080/otp/gtfs/v1
result               Finding
itineraries          5
duration             4.320 s
recommended_route    SUBWAY L1 -> WALK -> RAIL 9 -> WALK -> BUS R7
```

La route usata dal backend è `1:4955` (ANM L1), poi `2:9` (EAV), poi
`1:3216` (ANM R7): ANM ed EAV sono entrambi effettivamente raggiunti dal
backend. L’agente usa `DEFAULT_MODES`, che include `SUBWAY`; la verifica è
stata ripetuta dopo il rebuild e il mapping feed è stato ricalcolato. Non sono
stati modificati frontend o perturbazioni.

## 6. Coerenza ID, regressioni ed esclusione

Verifica multi-dataset degli itinerari OTP:
`infra/otp/verify_multi_dataset_itinerary.py`. Lo script mappa ogni feed OTP
alle agenzie esposte da `routes.agency.gtfsId` e a
`public.gtfs_datasets.agency_ids`; non assume `feedId=1` = EAV.

Risultato:

```text
build iniziale: feed 2 -> anm, feed 1 -> eav
build persistente attuale: feed 1 -> anm, feed 2 -> eav
Caso A: 12 leg transit verificati; tutti route/trip/stop/tempi corretti
Caso B: 13 leg transit verificati; tutti route/trip/stop/tempi corretti
```

Esempi attuali: `1:4955` → `gtfs_anm.routes.4955`; `2:9.` →
`gtfs_eav.routes.9.`; `1:388_CodUdp:D600_31935133` →
`gtfs_anm.trips.388_CodUdp:D600_31935133`; partenza 09:18:30 e arrivo 09:30:00
coincidono con `gtfs_anm.stop_times`. La verifica è stata ripetuta dopo il
rebuild: il mapping feed→dataset è stato ricalcolato dalle agenzie, non
copiato dalla build precedente.

Regressione EAV sul nuovo grafo (prova eseguita sulla build iniziale, dove
feed `1`=EAV; nella build persistente gli stessi route_id EAV hanno prefisso
`2:`):

- caso A precedente (Piscinola Scampia → Aversa): 5 itinerari, tutti con
  `1:2`; gli 5 leg transit trovano route/trip/stop in `gtfs_eav`;
- caso B precedente (Napoli P. Garibaldi → Torre Annunziata): 8 itinerari con
  `1:1`, `1:4`, `1:1.`; tutti gli 8 leg transit trovano corrispondenza in
  `gtfs_eav`;
- esclusione EAV `1:2`: non rimane nessun `1:2`; ora esiste un’alternativa
  reale con ANM `2:4568` + EAV `1:7` (prima del checkpoint ANM non esisteva);
- esclusione ANM `2:4955` (L1) da Chiaiano: nessun itinerario usa L1, ma
  restano 5 alternative con ANM bus + EAV rail.

Dopo il rebuild la verifica `verify_multi_dataset_itinerary.py` è stata
rieseguita sull’artefatto corrente: feed `1`→ANM e feed `2`→EAV, 13 leg del
caso Chiaiano tutti coerenti con i rispettivi schemi e orari.

Test eseguiti:

```text
pytest (suite ordinaria)                         129 passed, 12 skipped
pytest live GTFS PostgreSQL (EAV+ANM)            3 passed
pytest live disruptions PostgreSQL               5 passed
ruff check backend infra tests                   All checks passed
bash -n import-gtfs.sh download-monthly.sh       OK
docker compose config                            valido
docker compose build db                          immagine ricostruita
sync request path unit / rebuild forzato        OK (build, 8081, switch, 8080)
```

Stato conservato: container `healthy`; volume
`hackaton2026cds_postgres_data`; OSM 204.803 way/97.937 POI; sentinella 2A
presente; `gtfs_eav` invariato; `gtfs_anm` attivo; logging e schemi di staging
non cancellati.

## 7. Limiti e servizi lasciati attivi

- ANM ufficiale è valido solo **2026-11-09..2026-12-31**; non è stato esteso.
  La data di prova è interna. Dopo il 2026-12-31 servirà un nuovo feed o una
  fonte che ne dichiari la validità.
- Il feed ANM non ha `feed_info.txt`; la versione è content-addressed
  (`anm-ac0dfd987b734022`).
- Il feed ANM contiene anche la L2 di Trenitalia (`agency_id=FS`); non è stato
  separato in un dataset distinto.
- Il nome “CITTÀ DELLA SCIEZA” è il testo originale ANM; non è stato corretto.
- Il backend di default espone entrambi i feed; `GTFS_SCHEMA=gtfs_eav` resta
  il fallback singolo e non è stato sostituito. La configurazione Docker di
  default per il download automatico è ora ANM (`gtfs_anm`), così un futuro
  aggiornamento non sovrascrive EAV.
- L’agente Mobility usa i modi di default del client OTP. Al momento del
  checkpoint erano `WALK,BUS,RAIL`, quindi la metro L1 era raggiungibile solo
  dalle prove dirette; il 2026-11-15 `SUBWAY` è stato aggiunto a
  `DEFAULT_MODES` e l’agente ora usa la L1 (verificato con Via Domenico Biondi
  → Città della Scienza).
- Il container Docker è stato aggiornato nei file/script ma **non ricreato**:
  il database e il grafo attivi sono stati validati sul processo corrente.
  Un recreate successivo deve usare `RUN_ON_STARTUP=false`,
  `AUTO_IMPORT_GTFS=false`, `SKIP_PBF_DOWNLOAD=true`.
- Il vecchio grafo EAV resta in `/home/r0x4n/otp-1a/otp-data/graph.obj` per
  rollback. Gli staging ANM non pubblicati restano come audit.
- **BusOne realtime non integrato.** Per mantenere coerenti gli ID del
  realtime BusOne servirebbe il suo statico `/anm/gtfs.zip` (namespace `anm`),
  non un feed ANM generico: verificato il 2026-11-15, SHA-256
  `de242717bbf5c67d81b3b288c56204bea03f3269fb3082742dea3c8b970ec1ef`,
  6.179.024 byte, Last-Modified 2026-11-15T07:14:16Z. Condivide gli stessi
  112 route_id, 2.392 stop_id e 32.177 trip_id del feed ANM ufficiale, ma ha
  1.248 calendar_dates (9 date di servizio aggiunte) e 705.464 stop_times,
  oltre a `busone_calendar.json`/`blocks.txt`. Va importato in uno schema
  dedicato e confrontato con il realtime BusOne prima di sostituire il feed
  ANM ufficiale.

## 8. Comandi riproducibili

```bash
# Docker
sg docker -c 'docker ps -a && docker inspect napoli-postgres-mobility --format "{{json .Mounts}}"'

# Import ANM validato (dentro il container)
sg docker -c 'docker exec -e PGUSER=postgres -e PGDATABASE=mobility \
  napoli-postgres-mobility bash /usr/local/bin/import-gtfs.sh \
  --zip /data/gtfs/anm-google-transit-20261103.gtfs.zip \
  --dataset-key anm --schema gtfs_anm --operator-id ANM \
  --operator-name "Azienda Napoletana Mobilità" \
  --source-url https://www.anm.it/google/google-transit.zip --publish'

# Metadati e conteggi
sg docker -c 'docker exec -e PGUSER=postgres -e PGDATABASE=mobility \
  napoli-postgres-mobility psql -X -c \
  "select dataset_key,gtfs_schema,source_sha256,service_start,service_end,is_active from public.gtfs_datasets order by 1;"'

# OTP: build nuovo grafo (non sovrascrive il vecchio)
/usr/lib/jvm/java-25-openjdk-amd64/bin/java -Xms1g -Xmx4g \
  -jar /home/r0x4n/otp-1a/otp-shaded-2.10.0.jar \
  --build --save /home/r0x4n/otp-1b-anm/otp-data

# Sonde dirette OTP e verifica multi-dataset
python infra/otp/probe_anm.py \
  --base-url http://127.0.0.1:8080/otp/gtfs/v1 \
  --artifacts /home/r0x4n/otp-1b-anm/probe-artifacts-8080
python infra/otp/verify_multi_dataset_itinerary.py \
  --artifact /home/r0x4n/otp-1b-anm/probe-artifacts-8080/routing-chiaiano-cds-transitOnly-true.json \
  --database-url 'postgresql://postgres:postgres@127.0.0.1:5432/mobility' \
  --datasets eav:gtfs_eav,anm:gtfs_anm

# Backend (in-process; non esiste un endpoint HTTP travel)
APP_PROFILE=postgres DATABASE_URL='postgresql://postgres:postgres@127.0.0.1:5432/mobility' \
OTP_BASE_URL='http://127.0.0.1:8080' ROUTING_MODE=real \
python - <<'PY'
from datetime import datetime, timezone
from app.services.facade import BackendService
from app.services.agents.mobility.agent import MobilityAgent
s = BackendService()
print([(i["dataset_key"], i["gtfs_schema"]) for i in s.repository.get_datasets_info()])
r = MobilityAgent(s.repository, config=s.config).evaluate(
    origin_stop_id="anm:6312", destination_stop_id="anm:2167",
    now=datetime(2026, 11, 16, 7, 0, tzinfo=timezone.utc))
print(r.model_dump(mode="json"))
PY
```

## 9. Sincronizzazione automatica DB → OTP

`download_monthly.sh` ora, dopo un import GTFS pubblicato:

1. ricalcola lo SHA-256 di `/data/gtfs/gtfs-latest.zip`;
2. lo confronta con `public.gtfs_datasets.source_sha256`;
3. scrive atomicamente `/data/otp-rebuild/request.json` con dataset, schema,
   hash, percorso ZIP, date di servizio e `import_id`.

Sull'host sono installate unità utente:

| Unità | Ruolo |
|---|---|
| `otp-mobility.service` | OTP live su 8080, `WorkingDirectory=/home/r0x4n/otp-live` |
| `otp-graph-sync.path` | reagisce alla comparsa di `request.json` |
| `otp-graph-sync.service` | esegue `sync_graph_from_request.sh` |
| `otp-graph-sync.timer` | riconciliazione di sicurezza ogni 15 minuti |

`sync_graph_from_request.sh` verifica gli hash dei file EAV/ANM contro il
database, costruisce in `/home/r0x4n/otp-graphs/graph-*`, valida il nuovo
grafo sulla porta 8081 (almeno 2 feed, route con corse, L1/C1/R7), sposta
atomicamente il symlink `otp-live` e riavvia il servizio. In caso di errore
ripristina il grafo precedente. Lo stato è in
`data/otp-rebuild/{current.json,last-result.json,sync.log}`. Il timer
`otp-graph-sync.timer` riconcilia ogni 15 minuti anche se la richiesta è
andata persa; se gli hash coincidono non ricostruisce nulla. Rebuild manuale:
`systemctl --user start otp-graph-sync.service` oppure
`infra/otp/sync_graph_from_request.sh --force`.

Nota critica: OTP può cambiare `feedId` a ogni build. La build persistente ha
feed `1`=ANM e feed `2`=EAV, l’opposto della build iniziale; client e
verificatore ricalcolano il mapping dalle agenzie e non usano prefissi fissi.

Prove eseguite: `download-monthly.sh` reale → import ANM run 8 → richiesta
`20261115T085522Z-20274` → path unit → “grafo OTP già sincronizzato con gli
hash del database” (stesso hash). Rebuild completo con
`sync_graph_from_request.sh --force`: build, validazione 8081, switch e health
check 8080 riusciti. Simulazione di un nuovo hash (stato precedente alterato,
richiesta con hash DB corrente): path unit → build → validazione → switch →
health check, tutto riuscito. Grafo attivo
`/home/r0x4n/otp-graphs/graph-ac0dfd98-9a3eeba9-20261115T085616Z`,
SHA-256 `12f508a7c639cc67fa8d29c37a6c0c4adb3e8cc036cdc73b22cfa5daf46e66c5`;
versioni precedenti conservate in `/home/r0x4n/otp-1b-anm` e
`/home/r0x4n/otp-graphs/graph-ac0dfd98-9a3eeba9-20261115T085004Z`.

## 10. Criterio di completamento

ANM ed EAV sono entrambi presenti in `public.gtfs_datasets` e nei rispettivi
schemi `gtfs_anm`/`gtfs_eav`; il nuovo grafo OTP contiene entrambi i feed e il
backend li legge contemporaneamente. I due viaggi richiesti hanno itinerari
transit con L1, Chiaiano e Città della Scienza coperti, e gli ID dei leg sono
stati riconciliati con il dataset corretto. Non ci sono servizi ANM mancanti
per i casi richiesti: l’esito è **COMPLETO**, con i limiti operativi elencati
sopra.
