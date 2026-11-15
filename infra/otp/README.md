# OTP 2.10.0 — runbook prova EAV (CHECKPOINT 1A/1B)

Questa directory contiene solo il runbook e gli script della prova. JAR, PBF,
GTFS copiato e grafo restano fuori da Git, sotto `/home/r0x4n/otp-1a/`.

**Perimetro dichiarato:** prova tecnica sul GTFS **EAV** disponibile localmente.
Non è una prova di copertura ANM, non acquisisce il feed ANM e non integra
BusOne. Il CHECKPOINT 1A non modificava l'applicazione; il 1B modifica soltanto
client OTP, wiring dell'agente Mobility, configurazione e test. Schema GTFS,
migrazioni e database restano invariati.

## 1. Runtime

- Java usato esplicitamente: `/usr/lib/jvm/java-25-openjdk-amd64/bin/java`
  (OpenJDK 25.0.5). Il `java` predefinito del sistema resta Java 17.
- Docker è presente ma non è stato usato: il socket risponde `permission
  denied` e l'utente non è nel gruppo `docker`. Nessun container o database
  è stato creato/ricostruito in 1A.
- OTP: `otp-shaded-2.10.0.jar` da Maven Central, 191.382.029 byte,
  SHA-256 `5a5d1efd30b19295418ac49ad048c5f5cac341af63dd41d5e2ae5ad9e7b37885`.
  URL: `https://repo1.maven.org/maven2/org/opentripplanner/otp-shaded/2.10.0/otp-shaded-2.10.0.jar`.
- Verifica: `sha256sum -c` contro il `.sha256` pubblicato da Maven Central.

## 2. GTFS EAV

Sorgente locale: `/home/r0x4n/Scaricati/google-transit.zip`

- 4.105.995 byte; SHA-256
  `9a3eeba9a84ce7de11e3daf1e1727e60705ab89a0a9f8ea369105ff436716df9`.
- Copia neutra: `eav-technical.gtfs.zip` (nessuna data dedotta dal nome).
- Contenuto: agency EAV (`NA0004` ferrovia, `EAVO` autolinea), 124 route,
  7.415 corse, 4.208 fermate, 280.889 stop_times, 166.625 punti shape,
  8.495 `calendar_dates`; assenti `calendar.txt` e `feed_info.txt`.
- **Attenzione alla validità:** le 6.698 corse di autolinea hanno servizi nel
  periodo `2025-09-15`..`2025-10-31`; le 717 corse ferroviarie EAV hanno
  servizi dal `2026-11-12`. Sul giorno di prova `2026-11-16` sono attive solo
  11 route ferroviarie (`1, 1., 2, 4, 5, 5., 6, 7, 8, 9, 9.`) per 682 corse.
  La prova esercita quindi solo il trasporto ferroviario EAV, non le autolinee
  e non ANM.

## 3. OSM/PBF

Download Geofabrik:

- URL: `https://download.geofabrik.de/europe/italy/sud-latest.osm.pbf`
- redirect verificato: `https://download.geofabrik.de/europe/italy/sud-261113.osm.pbf`
- 423.322.789 byte, `Last-Modified 2026-11-14 01:23:15 GMT`,
  MD5 `35c90562a87af1ba669b990a1f3896e7` (verificato).
- Attribuzione: OpenStreetMap contributors, ODbL 1.0.

Estratto con osmium 1.19.0 / libosmium 2.23.0:

```bash
osmium extract -b 13.80,40.55,14.85,41.40 \
  --strategy=complete_ways --set-bounds \
  -o napoli-eav-261113.osm.pbf sud-261113.osm.pbf
```

Risultato: 58.877.279 byte, SHA-256
`ca4164b471edd76fb2f5f94aab34aed4e0319104f7ad043e36c4c36ff7a71192`,
7.672.022 nodi, 966.954 way, 14.603 relazioni. Il bbox è quello configurato
(fermate EAV + margine), non l'intera area metropolitana.

Senza root, osmium è stato usato da pacchetti Ubuntu estratti localmente:

```bash
mkdir -p tools/osmium-deb && cd tools/osmium-deb
apt-get download osmium-tool=1.19.0-1build1 \
  libboost-program-options1.90.0=1.90.0-6ubuntu1
for f in *.deb; do dpkg-deb -x "$f" root; done
export LD_LIBRARY_PATH="$PWD/root/usr/lib/x86_64-linux-gnu"
root/usr/bin/osmium --version
```

SHA-256 dei `.deb`: `e6a8b74dd2596092d464b90c524ebf0f9ff39912277e18f148dba05b84508e9f`
(osmium-tool), `552699d9211d5e9bc6c2ff97c412a901b431ba61eb7d93c8c139c3d20f45104e`
(libboost-program-options).

## 4. Configurazione e build

`infra/otp/build-config.json` (copiato nella base directory della prova):

```json
{
  "transitServiceStart": "2025-09-15",
  "transitServiceEnd": "2030-12-31",
  "transitModelTimeZone": "Europe/Rome",
  "osmDefaults": { "timeZone": "Europe/Rome" }
}
```

Senza questa configurazione OTP usa la finestra predefinita e aveva scartato
6.698 corse; con il periodo esplicito ha caricato tutte le 7.415 corse.

Comando (memoria disponibile verificata prima: 7,7 GiB; heap 4 GiB):

```bash
/usr/bin/time -v /usr/lib/jvm/java-25-openjdk-amd64/bin/java \
  -Xms1g -Xmx4g -jar otp-shaded-2.10.0.jar --build --save otp-data
```

Risultato: build completata in 48,04 s wall (OTP: 42,827 s), max RSS
2.258.000 KiB (~2,15 GiB), 0 swap. Grafo 62 MB, SHA-256
`ba5d4a9cdc8b8b24de69dba3a8d21f58cf7bc79c46f838c985a4404171f8d29c`;
342.767 vertici, 842.022 archi; 4.208 fermate, 541 pattern, 5.665 transfer
vincolati.

## 5. Avvio e arresto

```bash
systemd-run --user --unit=otp-1a --collect \
  --working-directory=/home/r0x4n/otp-1a \
  /bin/bash -lc 'exec /usr/lib/jvm/java-25-openjdk-amd64/bin/java \
    -Xms512m -Xmx2g -jar otp-shaded-2.10.0.jar \
    --load --serve otp-data >> artifacts/otp-server.log 2>&1'
# endpoint GTFS GraphQL:
# http://127.0.0.1:8080/otp/gtfs/v1
```

Processo lasciato attivo: unità utente `otp-1a`, MainPID `224830`, heap 2 GiB,
RSS ~1 GB, porta 8080. Arresto:

```bash
systemctl --user stop otp-1a
ss -ltnp | grep ':8080' || true
```

## 6. Probe GraphQL

```bash
python3 infra/otp/probe.py \
  --artifacts /home/r0x4n/otp-1a/probe-artifacts
```

Lo script interroga `feeds`, ricava gli ID reali da `routes` (feed `1`; route
`1:2`, `1:1`, `1:1.`, `1:4`), esegue i due casi e scrive request/response e
`summary.json`. Non usa assunzioni sul fatto che l'ID completo sia `2`.
La manutenzione 1B salva anche la richiesta (`*-request.json`), usa le stesse
impostazioni di modi per baseline ed esclusione e rifiuta shortName duplicati
invece di sceglierne uno arbitrariamente.

Caso A — Piscinola Scampia (40.892929,14.239837) → Aversa
(40.974147,14.213685), `2026-11-16T08:00:00+01:00`:

- baseline: 4 itinerari, tutti RAIL con `1:2`, durata 750 s;
- esclusione `1:2` con `preferences.transit.filters.exclude.routes`,
  `transitOnly: true`: 0 itinerari, `NO_TRANSIT_CONNECTION`. L'esclusione è
  dimostrata; non c'è alternativa di trasporto pubblico su questo collegamento.

Caso B — Napoli P. Garibaldi (40.851017,14.272976) → Torre Annunziata -
Oplonti (40.759526,14.451518), stessa data/ora:

- baseline: 6 itinerari, route `1:1`, `1:4`, `1:1.`;
- esclusione `1:1`: 4 itinerari, route `1:4` e `1:1.`, nessuna occorrenza di
  `1:1`. È dimostrata sia l'esclusione sia la presenza di un'alternativa
  reale con trasporto pubblico (durata 2.100 s / 2.130 s).

Sono conservati anche gli errori GraphQL del primo tentativo con variabili
`Float!`: il 2.10.0 richiede `CoordinateValue!`. Il probe 1A usa letterali
numerici; il client 1B usa variabili `PlanLabeledLocationInput!` e non
concatena input utente. Introspezione `TransitFilterInput` verificata sulla
release avviata: campi `include` ed `exclude`.

## 7. Client OTP2 (CHECKPOINT 1B)

`backend/app/services/agents/mobility/otp_client.py` usa:

- `POST {OTP_BASE_URL}/otp/gtfs/v1`;
- `planConnection` con variabili GraphQL `PlanLabeledLocationInput`,
  `PlanDateTimeInput`, `PlanModesInput`, `PlanPreferencesInput`;
- `first` e lista completa `ItineraryPlan.itineraries`;
- `preferences.transit.filters[].exclude[].routes` con ID `feedId:routeId`;
- `Leg.start/end`, `trip.gtfsId`, `route.gtfsId`, `from/to.stop.gtfsId` e
  `legGeometry.points`.

Il parser reale richiede mode, tempi scheduled interpretabili, coerenza
start/end, coordinate from/to finite e, per i leg transit, route/trip/stop ID;
la durata dichiarata deve essere valida e coerente con i tempi, altrimenti è
calcolata dai tempi. Campi accessori (nomi, estimated, geometria, walkTime,
transfer, generalizedCost) sono opzionali. Risposte incomplete o incoerenti
producono `OtpInvalidResponseError`, senza clamp o durate inventate.

Modalità: `ROUTING_MODE=real` (default) non usa mai fixture; `ROUTING_MODE=demo`
legge `shared/mocks/otp_fixture.json` senza rete e restituisce sempre
`is_simulated=True`. `APP_PROFILE` resta solo la persistenza. Errori distinti:
`OtpTimeoutError`, `OtpUnavailableError`, `OtpHttpError`, `OtpGraphQLError`,
`OtpInvalidResponseError`, `OtpNoRouteError`. Gli `routingErrors` con itinerari
utilizzabili restano in `ItineraryPlan.routing_errors` e diventano
`routing_warnings` nel finding.

## 8. Test e controllo live

Ambiente isolato riproducibile (fuori dal repository), installato dal
`pyproject.toml`:

```bash
python3 -m venv --without-pip /home/r0x4n/otp-1b-venv-pyproject
# get-pip.py nel venv (il venv di sistema non include ensurepip)
/home/r0x4n/otp-1b-venv-pyproject/bin/pip install -e ".[dev]"
/home/r0x4n/otp-1b-venv-pyproject/bin/python -m pytest -q
```

Payload registrati da OTP 2.10.0 in `tests/fixtures/otp2/`; i test offline usano
`httpx.MockTransport`. Il controllo live è separato:

```bash
/home/r0x4n/otp-1b-venv-pyproject/bin/python infra/otp/live_client_check.py \
  --output /home/r0x4n/otp-1a/live-client-check.json
```

Il live check usa gli stessi parametri per baseline ed esclusione, salvo
`exclude_route_ids=("1:1",)`, e scrive un summary nel file indicato. Non è un
test pytest e richiede OTP attivo.

## 9. Warning e limiti

- OTP 2.10.0 avvia con `CostlyAssertions` attivo (warning: feature da non
  usare in produzione).
- Warning JDK su `sun.misc.Unsafe` (Kryo), non bloccante.
- Island pruning: `GraphConnectivity 3`, isole WALK/BICYCLE/CAR; non ha
  impedito i due collegamenti provati. Non è una certificazione di continuità
  dell'intera rete.
- Il PBF è un estratto con `complete_ways`: la bbox dei dati si estende oltre
  il rettangolo richiesto; non è un confine amministrativo.
- La copertura è EAV ferroviaria sul giorno di prova. Non è ANM, non è BusOne,
  non è una prova di autolinee o di real-time.
- Esclusione applicata a route/agency; l'API GTFS GraphQL non offre
  l'esclusione di un segmento stradale arbitrario.

## 10. Grafo OSM + EAV + ANM (CHECKPOINT ANM)

Nuova build separata, senza modificare `otp-1a/otp-data/graph.obj`:

```bash
mkdir -p /home/r0x4n/otp-1b-anm/otp-data
cp /home/r0x4n/otp-1a/otp-data/napoli-eav-261113.osm.pbf /home/r0x4n/otp-1b-anm/otp-data/
cp data/gtfs/eav-technical.gtfs.zip data/gtfs/anm-google-transit-20261103.gtfs.zip \
  /home/r0x4n/otp-1b-anm/otp-data/
cp infra/otp/build-config.json /home/r0x4n/otp-1b-anm/otp-data/
/usr/lib/jvm/java-25-openjdk-amd64/bin/java -Xms1g -Xmx4g \
  -jar /home/r0x4n/otp-1a/otp-shaded-2.10.0.jar \
  --build --save /home/r0x4n/otp-1b-anm/otp-data
```

Build: 48 s, max RSS 1,8 GiB, grafo 94,7 MB (SHA-256
`3e22452fafe53656c13cf10639310262b4e287f80f5e06c816938ed2ec92941f`).
OTP assegna `feedId=1` a EAV e `feedId=2` ad ANM; il mapping va sempre
riletto da `feeds` e da `routes.agency.gtfsId`, non copiato.

Avvio del nuovo grafo sulla porta 8080 (dopo la validazione sulla 8081):

```bash
systemctl --user stop otp-1a
systemd-run --user --unit=otp-1b-anm --collect \
  --working-directory=/home/r0x4n/otp-1b-anm \
  /bin/bash -lc 'exec /usr/lib/jvm/java-25-openjdk-amd64/bin/java \
    -Xms512m -Xmx2g -jar /home/r0x4n/otp-1a/otp-shaded-2.10.0.jar \
    --load --serve otp-data >> artifacts/otp-server.log 2>&1'
```

Rollback EAV-only (il vecchio grafo non è stato cancellato):

```bash
systemctl --user stop otp-1b-anm
systemd-run --user --unit=otp-1a --collect \
  --working-directory=/home/r0x4n/otp-1a \
  /bin/bash -lc 'exec /usr/lib/jvm/java-25-openjdk-amd64/bin/java \
    -Xms512m -Xmx2g -jar otp-shaded-2.10.0.jar \
    --load --serve otp-data >> artifacts/otp-server.log 2>&1'
```

Sonde: `infra/otp/probe_anm.py` e verifica multi-dataset
`infra/otp/verify_multi_dataset_itinerary.py`.

### Sincronizzazione automatica DB → OTP

Il container scrive `/data/otp-rebuild/request.json` dopo un import GTFS
pubblicato e verificato per hash. Sull'host:

```bash
install -m 0644 infra/otp/systemd/otp-mobility.service \
  infra/otp/systemd/otp-graph-sync.service \
  infra/otp/systemd/otp-graph-sync.path \
  infra/otp/systemd/otp-graph-sync.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now otp-mobility.service
systemctl --user enable --now otp-graph-sync.path otp-graph-sync.timer
```

`sync_graph_from_request.sh`:
1. verifica che gli hash dei file `/data/gtfs` coincidano con
   `public.gtfs_datasets` (EAV e ANM);
2. costruisce in `/home/r0x4n/otp-graphs/graph-*` senza toccare il grafo live;
3. valida il nuovo grafo su `8081` (feed, route con corse, L1/C1/R7);
4. sposta atomicamente `/home/r0x4n/otp-live` e riavvia `otp-mobility`;
5. in caso di errore ripristina il puntamento precedente.

Il timer `otp-graph-sync.timer` esegue la stessa riconciliazione ogni 15
minuti; se gli hash coincidono non ricostruisce nulla. Log e stato:
`data/otp-rebuild/sync.log`, `last-result.json`, `current.json`.

Forzare un rebuild manuale (anche con hash invariati):

```bash
systemctl --user start otp-graph-sync.service   # attende la fine
infra/otp/sync_graph_from_request.sh --force    # equivalente da shell
```

Per disabilitare il rebuild automatico mantenendo il download:
`OTP_REBUILD_ENABLED=false` nel container.

## 11. Corrispondenza con il GTFS persistito (CHECKPOINT 2A)

Il grafo OTP e lo schema PostgreSQL `gtfs_eav` usano lo stesso archivio EAV
(SHA-256 `9a3eeba9a84ce7de11e3daf1e1727e60705ab89a0a9f8ea369105ff436716df9`).
Il database conserva gli ID originali GTFS; OTP li espone come
`feedId:gtfsId`. Il `feedId` è assegnato dal grafo e **non** è una costante:
nel grafo di questa prova vale `1`, ma va letto da `feeds`/`routes.gtfsId` a
ogni nuova build.

Verifica di un itinerario OTP contro il repository backend:

```bash
python infra/otp/verify_persisted_itinerary.py \
  --artifact /home/r0x4n/otp-1a/probe-artifacts-1b-final/baseline-a.json \
  --database-url 'postgresql://.../mobility' --schema gtfs_eav
```

Esempio verificato: `1:2` → route persistita `2`;
`1:2080_opttp2026-2030-12` → trip `2080_opttp2026-2030-12`;
`1:6711`/`1:6112` → stop `6711`/`6112`; partenza 08:00:00, arrivo 08:12:30.

## 12. Controllo di coerenza DB ↔ build OTP ↔ grafo live

`check_pipeline_consistency.py` è un controllo **solo lettura**. Confronta:

- `public.gtfs_datasets.source_sha256` con `data/otp-rebuild/current.json` e
  `data/otp-rebuild/last-result.json`;
- gli ZIP `anm.gtfs.zip`/`eav.gtfs.zip` nella build attiva;
- `graph.obj` con il `graph_sha256` registrato;
- il symlink `/home/r0x4n/otp-live` con la build attiva;
- feed e numero di route esposte da OTP con il database.

```bash
/home/r0x4n/otp-1b-venv-pyproject/bin/python \
  infra/otp/check_pipeline_consistency.py
```

Exit 0 e messaggio `PIPELINE COERENTE` se tutto coincide; exit 1 e lista dei
problemi se DB, ZIP, build o grafo live divergono. Lo script usa `sg docker`
per leggere il container, quindi va eseguito dall'host come utente del
progetto. Il controllo è eseguito come `ExecStartPost` di
`otp-graph-sync.service`: un fallimento rende l'unità fallita, senza
modificare il grafo live. Dopo una modifica all'unità:

```bash
install -m 0644 infra/otp/systemd/otp-graph-sync.service \
  ~/.config/systemd/user/
systemctl --user daemon-reload
```

Test negativo verificato:

```bash
jq '.datasets.anm.source_sha256="deadbeef"' data/otp-rebuild/current.json \
  > /tmp/current-bad.json
python3 infra/otp/check_pipeline_consistency.py \
  --state-file /tmp/current-bad.json --skip-otp
# exit 1: current.json: hash diverso per 'anm'
```

## 13. Test di regressione OTP (offline e live opt-in)

Suite ordinaria, senza rete:

```bash
/home/r0x4n/otp-1b-venv-pyproject/bin/python -m pytest -q
/home/r0x4n/otp-1b-venv-pyproject/bin/ruff check backend shared tests infra
```

I test rilevanti:

- `tests/unit/agents/test_mobility_default_modes.py`: `SUBWAY` in
  `DEFAULT_MODES` e passaggio della stessa tupla dall'agente;
- `tests/unit/agents/test_l1_closed.py`: discovery L1 per shortName+agenzia,
  esclusione del route ID feed-scoped, alternativa presente,
  `routing_errors=[]`;
- `tests/unit/agents/test_otp_graph.py`: mapping feed → dataset via agencies,
  feed arbitrari e rifiuto degli stati ambigui;
- `tests/integration/test_journeys_api.py`: endpoint HTTP con MockTransport;
- `tests/unit/test_pipeline_consistency.py`: controllo di coerenza.

Test live, richiedono OTP e PostgreSQL già attivi:

```bash
OTP_LIVE_BASE_URL=http://127.0.0.1:8080 \
OTP_LIVE_DATABASE_URL='postgresql://postgres:postgres@127.0.0.1:5432/mobility' \
/home/r0x4n/otp-1b-venv-pyproject/bin/python -m pytest -q -m live_otp \
  --force-enable-socket tests/integration/test_otp_live.py
```

`tests/integration/test_otp_live.py` verifica L1 chiusa contro il database
(route/trip/stop/orari), mapping multi-dataset, agente Mobility e endpoint
HTTP. Non viene eseguito dalla suite ordinaria (`-m 'not network'`).

## 14. Matrice date e limiti del grafo

Origine Via Domenico Biondi (40.8943044, 14.2308735), destinazione Città della
Scienza (40.8047221, 14.1745403), 08:00 Europe/Rome, `first=10`,
`transit_only=true`:

| Data | Esito | Itinerari | L1 |
|---|---|---:|---|
| 2026-11-16 | ok | 10 | presente |
| 2026-11-21 (sabato) | ok | 10 | presente |
| 2026-11-22 (domenica) | ok | 10 | presente |
| 2026-12-31 | ok | 10 | presente |
| 2027-01-01 | `NO_TRANSIT_CONNECTION_IN_SEARCH_WINDOW` | 0 | assente |

ANM nel grafo corrente: `2026-11-09..2026-12-31`; EAV:
`2025-09-15..2030-12-31`. Fuori validità ANM l'endpoint restituisce
`status=no_route`, non una fixture.

Altri casi limite:

- **feed mancante**: `import-gtfs.sh` rifiuta l'archivio se mancano
  `agency.txt`, `routes.txt`, `trips.txt`, `stops.txt` o `stop_times.txt`;
- **ZIP invalido**: `unzip -tq` fallisce, nessun import;
- **calendario vuoto**: `service_days` senza date → import fallito (controllo
  aggiunto in `import-gtfs.sh`);
- **hash diverso**: `sync_graph_from_request.sh` esce senza toccare il grafo
  live;
- **feed ID cambiati**: ogni build va riscoperta via `agencies`; non usare
  `1`/`2` come costanti.

## 15. Journey API e BusOne

- Contratto HTTP: `docs/CONTRACT_JOURNEY_PLAN.md`
  (`POST /api/v1/journeys/plan`).
- Preflight BusOne: `docs/reports/busone-realtime-preflight.md`. Integrazione
  **non implementata**: manca `X-BusOne-Client` reale e la conferma dei
  termini per l'organizzazione.
- Retention manuale: `docs/reports/retention-policy.md`. Nessun cleanup
  automatico; non cancellare volumi, schemi attivi/precedenti o grafi
  live/previous.
- Report completo: `docs/reports/checkpoint-p1-p2.md`.
