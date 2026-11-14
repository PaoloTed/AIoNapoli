[PIANIFICATO]

# Schema del database

Schema del database: tabelle, colonne, tipi, chiavi, indici, vincoli e unita'. Comprende le tabelle dichiarate dalla traccia e le tabelle interne necessarie al funzionamento, dichiarate come tali.

## 1. Principi

| Principio | Regola operativa |
|---|---|
| Tracciabilita' a livello di riga | ogni tabella sorgente porta `source_id`, `data_reference`, `is_simulated`, `ingested_at` |
| Append-only sulle serie temporali | `weather_snapshots` e `occupancy_estimates` non si aggiornano, si aggiungono |
| Idempotenza | ogni ingestion scrive con upsert su chiave naturale |
| Unita' dichiarate | ogni colonna numerica dichiara l'unita' nel nome o nel commento |
| Nessun tipo proprietario | enum tramite `CHECK` testuale, non tipi Postgres, per portabilita' |
| Geometria in EPSG:4326 | punti e poligoni in coordinate geografiche standard |

## 2. Tabelle dichiarate dalla traccia

### 2.1 `stops`

| Colonna | Tipo | Vincolo | Note |
|---|---|---|---|
| `stop_id` | text | chiave primaria | identificatore GTFS |
| `stop_name` | text | not null | |
| `zone_id` | text | not null, indice | zona operativa, vedi 2.10 |
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
| `connector` | text | `rss`, `gtfs`, `weather`, `events`, `occupancy` |
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

## 7. Viste

| Vista | Contenuto | Consumatore |
|---|---|---|
| `v_weather_latest` | ultimo snapshot per zona e per fonte | Agente Affollamento, Agente Contesto |
| `v_occupancy_latest` | ultima stima per linea e veicolo | Agente Affollamento |
| `v_service_alerts_active` | alert con `valid_to` nullo o futuro | Agente Mobilita, Agente Contesto |

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
