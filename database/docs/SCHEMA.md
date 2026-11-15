[PIANIFICATO]

# Schema del database

Schema del database: tabelle, colonne, tipi, chiavi, indici, vincoli e unita'. Comprende le tabelle dichiarate dalla traccia, le due tabelle aggiunte per il real-time e le tabelle interne necessarie al funzionamento, dichiarate come tali.

## 1. Principi

| Principio | Regola operativa |
|---|---|
| Tracciabilita' a livello di riga | ogni tabella sorgente porta `source_id`, `data_reference`, `is_simulated`, `ingested_at` |
| Append-only sulle serie temporali | `weather_snapshots`, `occupancy_estimates`, `vehicle_positions` e `trip_updates` non si aggiornano, si aggiungono |
| Idempotenza | ogni ingestion scrive con upsert su chiave naturale |
| Unita' dichiarate | ogni colonna numerica dichiara l'unita' nel nome o nel commento |
| Nessun tipo proprietario | enum tramite `CHECK` testuale, non tipi Postgres, per portabilita' |
| Geometria in EPSG:4326 | punti e poligoni in coordinate geografiche standard |

## 2. Tabelle sorgente

Le tabelle 2.1-2.8 sono nominate dalla traccia. Le tabelle 2.9-2.10 sono aggiunte dal progetto per il real-time e sono marcate come tali.

### 2.1 `stops`

| Colonna | Tipo | Vincolo | Note |
|---|---|---|---|
| `stop_id` | text | chiave primaria | identificatore GTFS |
| `stop_name` | text | not null | |
| `zone_id` | text | nullable, indice | zona operativa, vedi 3.1; `NULL` = non ancora classificata |
| `geometry` | geography(Point,4326) | not null | posizione della fermata |
| `source_id` | text | not null | ANM o EAV |
| `data_reference` | text | not null | |
| `is_simulated` | boolean | not null default false | |
| `ingested_at` | timestamptz | not null default now() | |

### 2.2 `routes`

| Colonna | Tipo | Vincolo | Note |
|---|---|---|---|
| `route_id` | text | chiave primaria | |
| `route_short_name` | text | | es. `L2`, `R7` |
| `route_type` | integer | not null | codice GTFS |
| `source_id` | text | not null | |
| `data_reference` | text | not null | |
| `is_simulated` | boolean | not null default false | |
| `ingested_at` | timestamptz | not null default now() | |

### 2.3 `trips`

| Colonna | Tipo | Vincolo | Note |
|---|---|---|---|
| `trip_id` | text | chiave primaria | |
| `route_id` | text | not null, FK `routes` | |
| `service_id` | text | not null, indice | riferimento al calendario GTFS |
| `source_id` | text | not null | |
| `is_simulated` | boolean | not null default false | |

### 2.4 `stop_times`

| Colonna | Tipo | Vincolo | Note |
|---|---|---|---|
| `trip_id` | text | not null, FK `trips` | |
| `stop_id` | text | not null, FK `stops` | |
| `stop_sequence` | integer | not null | |
| `arrival_time` | interval | | istante relativo al servizio |
| `departure_time` | interval | | |

Chiave primaria `(trip_id, stop_sequence)`. Indice su `(stop_id, departure_time)`.

### 2.5 `service_alerts`

Colonne dalla traccia: `route_id`, `stop_id`, `severity`, `valid_from`, `valid_to`, `source_id`, `confidence`.

| Colonna | Tipo | Vincolo | Note |
|---|---|---|---|
| `alert_id` | text | chiave primaria | derivato dal guid o da chiave composta, vedi 4.1 |
| `route_id` | text | FK `routes`, nullable | null se l'alert non e' legato a una linea |
| `stop_id` | text | FK `stops`, nullable | |
| `severity` | text | not null, CHECK nei quattro valori | derivata, non estratta, vedi 4.2 |
| `valid_from` | timestamptz | not null | |
| `valid_to` | timestamptz | nullable | vedi 4.3 |
| `source_id` | text | not null | identificatore della fonte, non del feed aggregatore |
| `confidence` | numeric(3,2) | not null, CHECK 0..1 | derivata, vedi 4.2 |
| `title` | text | not null | |
| `body` | text | | testo normalizzato |
| `zone_id` | text | nullable, indice | zona dedotta dalla mappatura |
| `is_simulated` | boolean | not null default false | |
| `data_reference` | text | not null | URL o guid originale |
| `ingested_at` | timestamptz | not null default now() | |

Chiave naturale per upsert: `(source_id, alert_id)`.

### 2.6 `events`

Colonne dalla traccia: geo-fence, affluenza attesa, finestra.

| Colonna | Tipo | Vincolo | Note |
|---|---|---|---|
| `event_id` | text | chiave primaria | |
| `name` | text | not null | |
| `zone_id` | text | not null, indice | |
| `geofence` | geography(Polygon,4326) | not null | geo-fence dell'evento |
| `expected_attendance` | integer | not null, CHECK > 0 | attesa di affluenza |
| `window_start` | timestamptz | not null | |
| `window_end` | timestamptz | not null, CHECK > window_start | |
| `source_id` | text | not null | |
| `data_reference` | text | not null | |
| `is_simulated` | boolean | not null default true | dataset dichiarato simulato |
| `ingested_at` | timestamptz | not null default now() | |

### 2.7 `weather_snapshots`

Colonne dalla traccia: previsione, livello di allerta, impatto stimato.

| Colonna | Tipo | Vincolo | Note |
|---|---|---|---|
| `snapshot_id` | bigint | chiave primaria, identity | |
| `snapshot_at` | timestamptz | not null | istante della previsione |
| `forecast_at` | timestamptz | not null | istante previsto |
| `zone_id` | text | nullable | null se nazionale |
| `precipitation_mm` | numeric(6,2) | | |
| `alert_level` | text | CHECK `verde`, `gialla`, `arancione`, `rossa` | |
| `heavy_rain` | boolean | not null default false | derivato dal livello, vedi 4.4 |
| `expected_impact` | text | | impatto stimato dalla fonte |
| `source_id` | text | not null | |
| `data_reference` | text | not null | |
| `is_simulated` | boolean | not null default false | |
| `ingested_at` | timestamptz | not null default now() | |

Chiave naturale per upsert: `(source_id, zone_id, forecast_at)`.

### 2.8 `occupancy_estimates`

Colonne dalla traccia: `vehicle_id`, `line`, `occupancy_pct`, `is_simulated`.

| Colonna | Tipo | Vincolo | Note |
|---|---|---|---|
| `estimate_id` | bigint | chiave primaria, identity | |
| `vehicle_id` | text | not null | |
| `line` | text | not null | linea o route_id |
| `occupancy_pct` | numeric(5,2) | not null, CHECK 0..100 | percentuale |
| `observed_at` | timestamptz | not null | |
| `source_id` | text | not null | sensore o simulazione |
| `data_reference` | text | not null | |
| `is_simulated` | boolean | not null default true | |
| `ingested_at` | timestamptz | not null default now() | |

Chiave naturale per upsert: `(vehicle_id, line, observed_at)`.

### 2.9 `vehicle_positions`

Non dichiarata dalla traccia. Necessaria per il real-time reale delle linee di superficie ANM.

| Colonna | Tipo | Vincolo | Note |
|---|---|---|---|
| `vehicle_id` | text | not null | identificatore del mezzo |
| `route_id` | text | FK `routes`, nullable | assente quando l'abbinamento e' ambiguo |
| `trip_id` | text | FK `trips`, nullable | assente nei casi ambigui, come dichiarato dalla fonte |
| `observed_at` | timestamptz | not null | istante dell'osservazione GPS |
| `latitude` | numeric(9,6) | not null | |
| `longitude` | numeric(9,6) | not null | |
| `bearing` | numeric(5,2) | | direzione in gradi |
| `speed_mps` | numeric(5,2) | | velocita' in metri al secondo |
| `zone_id` | text | nullable, indice | zona dedotta dalla geometria della fermata piu' vicina |
| `source_id` | text | not null | `anm`, non il proxy |
| `data_reference` | text | not null | URL del proxy con timestamp dell'emissione |
| `is_simulated` | boolean | not null default false | true solo in fallback |
| `ingested_at` | timestamptz | not null default now() | |

Chiave naturale per upsert: `(vehicle_id, observed_at)`.

### 2.10 `trip_updates`

Non dichiarata dalla traccia. Necessaria per ritardi, soppressioni e fermate saltate.

| Colonna | Tipo | Vincolo | Note |
|---|---|---|---|
| `trip_id` | text | not null, FK `trips` | |
| `route_id` | text | FK `routes` | |
| `stop_id` | text | FK `stops`, nullable | null per aggiornamenti a livello di corsa |
| `stop_sequence` | integer | nullable | |
| `arrival_delay_s` | integer | | ritardo in secondi, negativo se anticipo |
| `departure_delay_s` | integer | | |
| `schedule_relationship` | text | CHECK `scheduled`, `skipped`, `canceled`, `no_data` | |
| `observed_at` | timestamptz | not null | |
| `source_id` | text | not null | `anm` |
| `data_reference` | text | not null | |
| `is_simulated` | boolean | not null default false | |
| `ingested_at` | timestamptz | not null default now() | |

Chiave naturale per upsert: `(trip_id, stop_id, observed_at)`.

Nota: `schedule_relationship = no_data` non significa "in orario". Un passaggio senza riscontro resta senza dato, e l'agente lo tratta come assenza, non come zero ritardo.

### 2.11 Rete GTFS autorevole

La rete statica importata da `gtfs-via-postgres` **non** vive in `public`.
Ogni dataset ha uno schema dedicato (es. `gtfs_eav`) con le tabelle originali
`agency`, `routes`, `trips`, `stops`, `stop_times`, `calendar`,
`calendar_dates`, `shapes`, le viste `service_days`, `arrivals_departures`,
`connections`, `shapes_aggregated` e le funzioni di metadati dell'import.
I repository leggono direttamente questo schema; non esiste una copia
alimentata dal seed demo.

Le tabelle applicative `stops`, `routes`, `trips`, `stop_times` in `public`
restano per il percorso demo e per eventuali classificazioni/estensioni
applicative. Non vengono popolate automaticamente dall'import GTFS.

Metadati di importazione (schema `public`):

| Tabella | Contenuto |
|---|---|
| `gtfs_imports` | una riga per tentativo: fonte, hash SHA-256, versione dataset, schema di staging/destinazione, operatore, stato, conteggi |
| `gtfs_datasets` | dataset pubblicato e attivo: stessa provenienza/hash/versione, schema GTFS, intervallo servizio, conteggi |

I dataset convivono in schemi dedicati (`gtfs_eav`, `gtfs_anm`) e restano
entrambi attivi in `gtfs_datasets`. Il repository multi-dataset espone gli ID
come `dataset_key:gtfs_id` (`eav:6238`, `anm:6238`) e conserva l'ID originale
in `gtfs_stop_id`/`gtfs_route_id`/`gtfs_trip_id`.

Il prefisso OTP `feedId:` non è persistito come parte degli ID GTFS: viene
letto dal grafo OTP in esecuzione. Il database conserva gli ID originali
(`route_id`, `trip_id`, `stop_id`); OTP li espone come `feedId:route_id`, ecc.

### 2.12 Territorio OSM (`osm_territory`)

Il catalogo OSM vive in uno schema dedicato, separato da `public` e
`gtfs_eav`. Non è un grafo di routing: ogni riga di `osm_ways` è una **way
OSM**, non un segmento topologico. La costruzione della rete navigabile resta
compito di OTP.

| Tabella | Contenuto |
|---|---|
| `osm_territory.osm_ways` | way con `highway`, nome/ref, tag di accesso, direzione, ponte/tunnel/livello, geometria `LineString` 4326 |
| `osm_territory.pois` | nodi, way chiuse e relation con categoria POI; geometria originale e `label_point` per la ricerca |
| `public.osm_imports` | audit delle importazioni: fonte, hash, versione, staging, stato, conteggi |
| `public.osm_datasets` | dataset pubblicato: snapshot, timestamp, attribuzione ODbL, conteggi |

`osm_key` è la chiave stabile (`node/<id>`, `way/<id>`, `relation/<id>`).
Il refresh aggiorna le tabelle pubblicate per `osm_key` e marca le righe non
più presenti con `is_current = FALSE`; non rinomina lo schema e non cancella
le righe storiche, quindi eventuali FK future restano riferite alle tabelle
pubblicate e gli identificativi restano ricostruibili.

Indici: GIST su `osm_ways.geom`, `pois.geom` e `pois.label_point`; btree e
GIN trigram su nome/ref; GIN sui tag JSONB. Le distanze usano `geography`
(metri), non buffer in gradi.

### 2.13 Perturbazioni persistenti

La fonte autorevole resta `public.service_alerts`, estesa dalla migrazione
004; non esiste un secondo archivio. Campi aggiunti: `alert_type`, `effect`
(`block`, `penalize`, `info`), `source_url`, `content_hash`, `published_at`,
`observed_at`, `timezone`, `lifecycle_status` (`draft`, `active`, `resolved`,
`cancelled`, `expired`), `verification_status` (`verified`, `unverified`,
`needs_review`, `stale`), `uncertainty` (`low`, `medium`, `high`),
`next_review_at`, `recurrence` JSONB, `revision`, `resolved_at`,
`cancelled_at`, `updated_at`.

`effect`, `lifecycle_status` e `verification_status` sono distinti: la
severità non è lo stato di risoluzione; una finestra ricorrente non è un
blocco continuo; `valid_to` nullo richiede `next_review_at` e non significa
“valido per sempre”.

| Tabella | Ruolo |
|---|---|
| `public.reference_entities` | catalogo stabile di route/trip/stop GTFS e way/POI OSM; `is_current=false` conserva gli oggetti usciti dal dataset |
| `public.service_alert_links` | collegamenti multipli a entità, con direzione, modo, porzione di corsa, `service_date`, stato di risoluzione e raw reference |
| `public.service_alert_revisions` | storico delle revisioni, con hash e payload JSONB |

Con più feed GTFS l'`entity_key` include il dataset
(`gtfs:{dataset_key}:{entity_type}:{entity_id}`), così route/trip/stop con lo
stesso ID originale in EAV e ANM restano entità distinte. La migrazione
`005_gtfs_reference_namespaces.sql` applica questa forma e converte i
collegamenti esistenti.

Per risolvere o cercare perturbazioni ANM, il repository usa
`dataset_key="anm"`; se omesso mantiene il dataset GTFS configurato nel
repository (EAV per default), senza cercare in altri feed. Anche la verifica
del calendario di una corsa legge lo schema del dataset richiesto da
`gtfs_datasets`, non uno schema EAV fisso. Un riferimento non risolto conserva
il dataset nella propria identità, così due ID mancanti uguali non si fondono.

La migrazione 005 propaga la nuova chiave alle FK e ai riferimenti operativi
dei link; lo storico JSON delle revisioni rimane immutato. Eventuali link
legacy con dataset discordante da quello del riferimento sono conservati
come `unresolved` e richiedono nuova risoluzione, senza assegnazioni arbitrarie.

`service_alert_links.entity_key` ha FK reale verso
`reference_entities.entity_key`. Un riferimento inesistente resta
`unresolved` con `raw_reference` e senza FK; un oggetto non più corrente è
`historical` e mantiene la FK. Dopo un refresh GTFS/OSM le righe non vengono
cancellate: il catalogo viene marcato `is_current=false` e i collegamenti
restano leggibili.

## 3. Tabelle interne

Non sono nella traccia. Sono necessarie e vengono dichiarate come interne, non come contratto.

### 3.1 `zones`

| Colonna | Tipo | Note |
|---|---|---|
| `zone_id` | text, chiave primaria | identificatore condiviso tra agenti, es. `Z_BAGNOLI` |
| `name` | text | nome leggibile |
| `geometry` | geography(Polygon,4326) | |

Regola: l'identificatore di zona e' lo stesso per mobility e crowding. Senza, R2 non scatta mai.

### 3.2 `ingestion_runs`

| Colonna | Tipo | Note |
|---|---|---|
| `run_id` | bigint identity | |
| `connector` | text | `rss`, `gtfs`, `gtfs-rt`, `weather`, `events`, `occupancy` |
| `started_at` | timestamptz | |
| `finished_at` | timestamptz | |
| `rows_written` | integer | |
| `is_simulated` | boolean | se la run ha usato il fallback |
| `outcome` | text | `ok`, `fallback`, `failed` |
| `detail` | text | motivo |

### 3.3 `findings`

Store di audit, append-only.

| Colonna | Tipo | Note |
|---|---|---|
| `finding_ref` | text, chiave primaria | hash del finding canonico |
| `agent` | text | |
| `type` | text | |
| `severity` | text | |
| `is_simulated` | boolean | |
| `payload` | jsonb | finding canonico completo |
| `received_at` | timestamptz | |

### 3.4 `decisions`

Store di audit, append-only.

| Colonna | Tipo | Note |
|---|---|---|
| `decision_id` | text, chiave primaria | hash della decisione canonica senza timestamp |
| `trigger_rule` | text | `trigger.rule_id` |
| `conflict_detected` | boolean | |
| `payload` | jsonb | decisione canonica completa |
| `created_at` | timestamptz | |

## 4. Regole di derivazione

Dati che non esistono nei feed e che il sistema deve produrre con regole deterministiche, non con estrazione libera.

### 4.1 `alert_id`

| Fonte | Derivazione |
|---|---|
| feed con `guid` `?p=ID` | `source_id + ":" + id numerico` |
| feed con `guid` URL | `source_id + ":" + sha1(guid)[:16]` |
| CCISS e Protezione Civile Nazionale, senza guid | `source_id + ":" + sha1(title + "|" + pubDate)[:16]` |

### 4.2 `severity` e `confidence`

Nessun feed espone la severita' come campo. La derivazione e' dichiarata e testata.

| Tipo di fonte | `severity` | `confidence` |
|---|---|---|
| Protezione Civile (avvisi, bollettini) | da categoria o da livello di allerta nel testo | 0.90 |
| MIT scioperi | da tipo di sciopero, `high` se nazionale | 0.90 |
| CCISS | da keyword nella `description`: `chius`, `incidente`, `coda` | 0.80 |
| Azienda di trasporto (A3, ANM, EAV) | da keyword nel titolo | 0.85 |
| Testata locale (ANSA, NapoliToday) | da keyword nel titolo | 0.65 |
| Museo o parco (eventi) | `low` di default | 0.60 |
| Aggregatore (Google News) | `medium` di default | 0.40 |

La mappatura vive in `backend/app/services/connectors/rss/derivation.yaml`. Una keyword non riconosciuta produce `severity=medium` e `confidence` della fonte, con nota nel `detail` della run. Una fonte aggregatrice non e' mai `severity=critical`.

### 4.3 `valid_from` e `valid_to`

| Caso | `valid_from` | `valid_to` |
|---|---|---|
| alert con finestra dichiarata nel testo o nel PDF | estratta se disponibile | estratta se disponibile |
| alert senza finestra | `pubDate` | null |
| sciopero MIT | `pubDate`, che e' l'inizio dell'evento | null |
| evento con finestra | `window_start` dell'evento | `window_end` dell'evento |

`valid_to` null significa "validita' non dichiarata", non "valido per sempre". Le regole non inventano una durata: un alert senza `valid_to` resta valido finche' non compare un alert che lo revoca sulla stessa `route_id`.

### 4.4 `heavy_rain`

| `alert_level` | `heavy_rain` |
|---|---|
| `verde` | false |
| `gialla` | false |
| `arancione` | true |
| `rossa` | true |

Mappatura in `rules.yaml`. Se `alert_level` e' nullo, R3 non scatta e il log lo registra.

### 4.5 `zone_id`

| Sorgente | Derivazione |
|---|---|
| fermata GTFS | tabella di mappatura `stop_id` verso `zone_id` |
| evento | campo `zone_id` del dataset eventi |
| alert RSS | da `route_id` mappato, oppure da keyword sul titolo, oppure nullo |
| finding mobility | `zone_id` della fermata di destinazione |

La tabella di mappatura e' curata a mano e vive in `database/seed/zones.csv`. Non si deduce da coordinate a runtime in demo: sarebbe un calcolo spaziale non spiegabile in cinque righe.

### 4.6 `zone_id` di una posizione veicolo

| Caso | Derivazione |
|---|---|
| `trip_id` presente | `zone_id` della fermata successiva della corsa |
| `trip_id` assente | `zone_id` della fermata piu' vicina entro 500 metri |

Se nessuna fermata e' entro 500 metri, `zone_id` resta nullo e la posizione non partecipa alle regole per zona. Non si inventa una zona.

### 4.7 Eta' di un dato real-time

| Caso | Trattamento |
|---|---|
| posizione con `observed_at` entro 90 secondi | valida |
| posizione piu' vecchia di 90 secondi | scartata in lettura, non cancellata |
| `trip_updates` con `schedule_relationship = no_data` | passaggio senza riscontro, non zero ritardo |
| risposta del proxy vuota | non e' un errore, e' assenza di dati: il connettore scrive zero righe e registra `outcome=ok` |

La soglia di 90 secondi replica il comportamento dichiarato dalla fonte. Non e' una scelta del progetto: e' il criterio con cui la fonte qualifica i propri dati.

## 5. Vincoli trasversali

| Vincolo | Dove |
|---|---|
| `confidence` tra 0 e 1 | `service_alerts`, e validazione Pydantic |
| `density` tra 0 e 1 | validazione Pydantic su `content` |
| `occupancy_pct` tra 0 e 100 | `occupancy_estimates` |
| `expected_attendance` maggiore di zero | `events` |
| `window_end` maggiore di `window_start` | `events` |
| `valid_to` maggiore o uguale a `valid_from` quando presente | `service_alerts` |
| `severity` nei quattro valori | `service_alerts`, `findings` |
| `arrival_delay_s` e `departure_delay_s` maggiori di -3600 | `trip_updates`, un anticipo oltre un'ora e' un dato corrotto |

## 6. Indici

| Tabella | Indice | Motivo |
|---|---|---|
| `stops` | `zone_id` | filtro per zona |
| `stops` | GIST su `geometry` | prossimita' |
| `events` | `zone_id`, `window_start` | filtro per zona e finestra |
| `events` | GIST su `geofence` | contenimento spaziale |
| `service_alerts` | `(route_id, valid_from)` | alert attivi per linea |
| `service_alerts` | `zone_id` | filtro per zona |
| `weather_snapshots` | `(source_id, zone_id, forecast_at)` | ultimo snapshot per zona |
| `occupancy_estimates` | `(line, observed_at)` | ultima stima per linea |
| `vehicle_positions` | `(route_id, observed_at)` | ultime posizio
| `vehicle_positions`, `trip_updates` | 24 ore | oltre non servono, il volume e' alto |ni per linea |
| `vehicle_positions` | `zone_id` | mezzi presenti in una zona |
| `trip_updates` | `(trip_id, stop_sequence)` | aggiornamenti di una corsa |

## 7. Viste

| Vista | Contenuto | Consumatore |
|---|---|---|
| `v_weather_latest` | ultimo snapshot per zona e per fonte | Agente Affollamento, Agente Contesto |
| `v_occupancy_latest` | ultima stima per linea e veicolo | Agente Affollamento |
| `v_service_alerts_active` | alert con `valid_to` nullo o futuro | Agente Mobilita, Agente Contesto |
| `v_vehicle_positions_latest` | ultima posizione per veicolo, con `observed_at` entro 90 secondi | frontend, Agente Mobilita |
| `v_trip_updates_latest` | ultimo aggiornamento per corsa e fermata | Agente Mobilita |

I finding leggono le viste, non le serie storiche. La serie resta per le metriche e per la demo del prima e dopo.

## 8. Retention

| Tabella | Retention | Motivo |
|---|---|---|
| serie temporali | 7 giorni | metriche e confronto prima e dopo |
| `findings`, `decisions` | intera durata dell'evento | audit e replay |
| tabelle sorgente statiche | intera durata dell'evento | ricostruibilita' |
| `ingestion_runs` | intera durata dell'evento | diagnosi |

La retention e' un parametro in configurazione, non una costante nel codice.

## 9. Profili di esecuzione

| Profilo | Database | Uso |
|---|---|---|
| `memory` | nessuno, dati in fixture JSON | default, test, demo offline |
| `sqlite` | file locale | test dei repository senza Docker |
| `postgres` | Postgres con PostGIS | profilo reale, metriche spaziali |

Il profilo si sceglie da variabile d'ambiente. Il core riceve finding gia' caricati: non sa quale profilo sia attivo.

## 10. Migrazioni

- Directory `database/migrations/`, file numerati `001_`, `002_`.
- Applicazione idempotente da uno script che tiene la tabella `schema_migrations`.
- Nessun framework di migrazioni: una funzione Python che legge i file in ordine e registra i nomi applicati.
- Ogni migrazione e' eseguibile su database vuoto e su database gia' allineato.
