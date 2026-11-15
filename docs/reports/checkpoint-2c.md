# CHECKPOINT 2C — Perturbazioni persistenti e collegamenti GTFS/OSM

Data: 2026-11-15 (Europe/Rome). Perimetro: modello e persistenza delle
perturbazioni, riferimenti stabili a GTFS/OSM, refresh e repository. Non sono
stati implementati scraping, LLM, matching automatico, ricalcolo di viaggi,
nuovi endpoint o agenti.

## 1. Ambiente e stato iniziale

Docker usato con `sg docker`; nessun permesso del socket modificato.

- progetto Compose: `hackaton2026cds`;
- container: `napoli-postgres-mobility`, `healthy`;
- volume: `hackaton2026cds_postgres_data`;
- database Docker: `mobility`, porta `5432` (distinto da `mobility_2a` sulla
  porta `55432`);
- PostgreSQL 18.7 + PostGIS 3.6.2;
- GTFS `gtfs_eav`: 7.415 trip, 4.208 stop, 280.889 stop_times;
- OSM `osm_territory`: 204.803 way, 97.937 POI;
- sentinella 2A `checkpoint-2a-docker-sentinel`: presente;
- `service_alerts` preesistenti: 0 righe (nessun dato cancellato).

## 2. Una sola fonte autorevole

La fonte resta **`public.service_alerts`**, estesa dalla migrazione
`004_disruptions.sql`. Non è stato creato un secondo archivio delle
perturbazioni.

Aggiunte alla tabella esistente:

`alert_type`, `effect` (`block`, `penalize`, `info`), `source_url`,
`content_hash`, `published_at`, `observed_at`, `timezone`,
`lifecycle_status` (`draft`, `active`, `resolved`, `cancelled`, `expired`),
`verification_status` (`verified`, `unverified`, `needs_review`, `stale`),
`uncertainty` (`low`, `medium`, `high`), `next_review_at`, `recurrence`
JSONB, `revision`, `resolved_at`, `cancelled_at`, `updated_at`.

Nuove tabelle:

| Tabella | Ruolo |
|---|---|
| `public.reference_entities` | catalogo stabile di route/trip/stop GTFS e way/POI OSM |
| `public.service_alert_links` | collegamenti multipli con direzione, modo, porzione, service date e stato di risoluzione |
| `public.service_alert_revisions` | storico delle revisioni, hash e payload JSONB |

`severity` e `lifecycle_status` restano distinti. `uncertainty` e
`verification_status` non sono sinonimi di severità. Un `valid_to` nullo non
significa “valido per sempre”: per una perturbazione attiva il modello
richiede `next_review_at` e non ammette `verification_status=verified` senza
scadenza. `effect=block` e `effect=penalize` richiedono almeno un
collegamento; `effect=info` può anche non averne.

`recurrence` supporta finestre giornaliere (`daily`, `start`, `end`, `days`),
valutate nel fuso `timezone` della perturbazione; una finestra 08:00–10:00 non
è un blocco continuo. `published_at` futuro non è attivo. Una scadenza
sconosciuta resta visibile con stato di verifica/revisione.

Il connettore RSS legacy continua a scrivere la stessa tabella tramite
`upsert_service_alerts`; i campi nuovi hanno default compatibili e
`published_at` viene ricondotto a `valid_from` quando assente. Non esiste un
adattatore che crei una seconda tabella.

## 3. Collegamenti e integrità referenziale

`service_alert_links` contiene:

- `source_id`, `alert_id`, `link_ref` (identità idempotente del link);
- `entity_type`: `route`, `trip`, `stop`, `osm_way`, `osm_poi`;
- `entity_key` con **FK reale** verso `reference_entities.entity_key`;
- `raw_reference` sempre conservata;
- `resolution_status`: `resolved`, `historical`, `unresolved`;
- `direction` (`both`, `forward`, `backward`), `mode`;
- `from_stop_id`/`to_stop_id`, sequenze, `service_date`, `service_active`;
- `details` JSONB e flag `is_current`.

Chiavi stabili:

| Entità | `entity_key` |
|---|---|
| route GTFS | `gtfs:route:<route_id>` |
| trip GTFS | `gtfs:trip:<trip_id>` |
| stop GTFS | `gtfs:stop:<stop_id>` |
| way OSM | `osm:way:<osm_key>` |
| POI OSM | `osm:poi:<osm_key>` |

Il catalogo `reference_entities` viene sincronizzato dagli import
(`sync-gtfs-refs.sql`, `sync-osm-refs.sql`). Le righe non presenti in un
nuovo dataset restano con `is_current=false`, non vengono cancellate. Il
repository classifica un link come `historical` se l’entità non è più
corrente; `find_applicable` considera solo link `resolved` e correnti.

Un riferimento inesistente non viene associato alla prima entità simile:
resta `unresolved`, con `raw_reference` e senza `entity_key`. Un oggetto OSM
`is_current=false` non è trattato come corrente; la FK resta valida per
storico/audit, ma il link è `historical`.

La way OSM resta una **way**, non un segmento topologico: il link identifica
la way o il POI, non costruisce archi o percorsi. OTP resta l’unico motore di
routing.

## 4. Refresh GTFS/OSM

Il refresh GTFS rinomina `gtfs_eav`; non esiste una FK diretta verso le sue
tabelle. I link usano `reference_entities`, aggiornato dopo la pubblicazione
GTFS. Il refresh OSM aggiorna le tabelle stabili `osm_territory` e poi
`reference_entities`; l’eventuale oggetto scomparso diventa
`is_current=false`.

Politica:

1. import in staging;
2. validazione e pubblicazione del dataset;
3. sincronizzazione di `reference_entities` in transazione;
4. nessuna cancellazione di `service_alerts`, link o revisioni;
5. link a entità non più correnti conservati e classificati `historical`.

Sono stati eseguiti refresh reali: GTFS run 3 e OSM run 4 dopo la creazione
dei fixture. I collegamenti della perturbazione `fixture_2c_refresh` sono
rimasti presenti e `resolved` verso route 2, trip
`2080_opttp2026-2030-12`, stop `6711` e way `way/269910733`.

## 5. Repository

`backend/app/repositories/disruptions.py`:

- `upsert(DisruptionInput)`: idempotente su `(source_id, alert_id)`;
  aggiorna `revision` e `service_alert_revisions` solo se cambia il contenuto;
- `get(source_id, alert_id)`: legge una perturbazione con i link correnti;
- `resolve` / `cancel` / `set_lifecycle`: transizione esplicita, con revisione;
- `find_applicable(entity_type, entity_id, at, service_date, direction, mode)`:
  applicabilità temporale, direzionale, modale e per giornata di servizio.

La ricerca considera `published_at <= at`, `valid_from/valid_to`, stato
`active`, ricorrenza locale e link correnti risolti. Un trip con
`service_date` viene verificato contro `gtfs_eav.service_days`; una data non
attiva non rende applicabile il link. `next_review_at` e `verification_status`
restano esposti per la revisione umana.

## 6. Verifiche PostgreSQL reali

Fixture tutte simulate (`is_simulated=true`, prefisso `fixture_2c` /
`fixture_2c_test`), non incidenti reali.

**Multi-entità**

`fixture_2c/multi-entity-001` ha 6 link:

| Tipo | Entità | Stato |
|---|---|---|
| route | `gtfs:route:2` | resolved |
| trip | `gtfs:trip:2080_opttp2026-2030-12` | resolved |
| stop | `gtfs:stop:6711` | resolved |
| stop | `gtfs:stop:6112` | resolved |
| osm_way | `osm:way:way/269910733` | resolved |
| osm_poi | `osm:poi:way/338168783` | resolved |

Il link trip ha `service_date=2026-11-16` e `service_active=true`; con
`service_date=2026-11-17` la perturbazione non è applicabile.

**Idempotenza e revisione**

- primo upsert: `revision=1`, una riga logica, 6 link;
- stesso contenuto: nessuna nuova riga logica, `revision` invariata;
- titolo modificato: `revision=2`, due righe in `service_alert_revisions`.

**Stati e tempo**

Test reali su: attiva, futura (pubblicazione futura), scaduta, risolta,
annullata, ricorrente giornaliera 08:00–10:00 e direzione `forward` /
`backward`. Una pubblicazione futura non è attiva; una ricorrenza non è un
blocco continuo; risolta/annullata non compaiono in `find_applicable`.

**Riferimenti**

- route inesistente → link `unresolved`, `raw_reference` conservata, nessuna
  FK;
- route presente nel catalogo ma `is_current=false` → link `historical` con
  FK valida;
- link OSM non corrente → `historical`, non applicabile.

**Refresh e integrità**

Dopo i refresh GTFS/OSM:

```text
service_alerts                 2 (fixture simulate)
service_alert_links           10
service_alert_revisions        2
reference_entities GTFS    11.747 (124 route, 4.208 stop, 7.415 trip)
reference_entities OSM    302.740 (204.803 way, 97.937 POI)
gtfs_eav.trips              7.415
osm_territory.osm_ways     204.803
osm_territory.pois          97.937
checkpoint-2a sentinel          1
```

Nessuna perdita di dati GTFS, OSM o sentinelle. Il container è stato
ricreato/riavviato più volte; conteggi e link sono rimasti nel volume.

**Timestamp PBF**

`osm_datasets.osm_timestamp = 2026-11-14T01:23:15Z` è il `Last-Modified` HTTP
della sorgente; `osm_datasets.data_timestamp = 2026-11-13T21:03:47Z` è il
timestamp effettivo dell’ultimo oggetto OSM nel PBF (`osmium fileinfo`). I due
valori sono distinti e documentati anche nel report 2B.

## 7. Test e comandi

Test:

- suite ordinaria: **121 passed, 9 skipped**;
- PostgreSQL live: **9 passed** (5 disruption, 2 GTFS, 2 OSM);
- `ruff check`: nessun errore;
- `bash -n` su `import-gtfs.sh` e `import-osm.sh`: nessun errore.

Comandi principali (senza credenziali):

```bash
APP_PROFILE=postgres DATABASE_URL='postgresql://postgres@127.0.0.1:5432/mobility' \
  python -m app.cli db migrate

DISRUPTION_TEST_DATABASE_URL='postgresql://postgres@127.0.0.1:5432/mobility' \
  pytest -q tests/db/test_disruptions_postgres.py -m db

# Il refresh reale usa i percorsi 2A/2B già documentati:
# import-gtfs.sh --publish ...  e  import-osm.sh --publish ...
```

## 8. Limiti

- Le fixture sono simulate e non rappresentano interruzioni reali.
- Non è stato implementato scraping, estrazione LLM, matching automatico,
  ricalcolo o endpoint di viaggio.
- Il catalogo `reference_entities` è un indice derivato stabile, non una
  seconda rete GTFS/OSM né un archivio alternativo delle perturbazioni.
- `find_applicable` lavora su entità esatte; non deduce automaticamente che
  un link a una route valga per tutte le sue corse.
- La ricorrenza supportata è giornaliera; non sono modellate ricorrenze
  settimanali/festive complesse oltre ai giorni della settimana.
- `service_active` è validato al momento dell’inserimento/refresh del link;
  una successiva variazione del calendario richiede una nuova verifica.
- La classificazione `historical` dipende dalla sincronizzazione di
  `reference_entities`; se la sincronizzazione fallisce, il link resta
  `resolved` finché il catalogo non viene aggiornato.
- Le prove distruttive con riferimenti rimossi usano fixture isolate; nessun
  oggetto GTFS/OSM reale è stato cancellato.
- Fuori perimetro: fase 3, matching imprevisti, agenti, frontend, OTP.
