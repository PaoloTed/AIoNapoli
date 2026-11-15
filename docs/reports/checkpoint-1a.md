# CHECKPOINT 1A — OTP 2.10.0 reale, input EAV validati e prova API

Data: 2026-11-15 (Europe/Rome). Perimetro approvato: sola prova tecnica OTP;
nessuna modifica a `otp_client.py`, schema GTFS, migrazioni o database. Non è
stata installata/ricostruita infrastruttura Docker. JAR, PBF, grafo e artefatti
pesanti sono fuori dal repository, in `/home/r0x4n/otp-1a/`.

## 1. Base e modifiche

- HEAD iniziale: `12317220bdb208ef9988588cbca72b9143cdc84d` (`main` =
  `origin/main`).
- Modifiche applicative: nessuna.
- Nuovi file di supporto: `infra/otp/README.md`, `infra/otp/build-config.json`,
  `infra/otp/probe.py`; questo report.
- Non sono stati modificati `docker-compose.yml`, `infra/postgres/*`,
  `backend/app/**`, `database/migrations/**` o dati del progetto.

## 2. Runtime e memoria

- Java usato esplicitamente: `/usr/lib/jvm/java-25-openjdk-amd64/bin/java`,
  OpenJDK `25.0.5.0.3`. Il `java` predefinito del sistema è rimasto Java 17.
- Docker non usato in 1A. Durante la sessione è comparso installato
  (`Docker 29.9.3`, `Compose v5.7.1`, servizio attivo), ma `docker ps`
  risponde `permission denied` sul socket e l'utente non è nel gruppo
  `docker`. Non è stato installato/ricostruito alcun container o database in
  1A; la prova OTP usa il JAR e Java 25.
- Memoria host prima del build: 14 GiB totali, 7,7 GiB disponibili, 0 swap
  usato. Disco libero: 379 GiB.
- OTP: `2.10.0`, ser.ver.id `277`, commit
  `521cd5d8acaae628878f43bf5946f4942c118548`, branch `master`, build
  `2026-09-09T11:15:00+02:00`.

## 3. Download e checksum

### OTP

- URL ufficiale:
  `https://repo1.maven.org/maven2/org/opentripplanner/otp-shaded/2.10.0/otp-shaded-2.10.0.jar`
- Dimensione: `191.382.029` byte.
- SHA-256 calcolato e confrontato con il `.sha256` pubblicato:
  `5a5d1efd30b19295418ac49ad048c5f5cac341af63dd41d5e2ae5ad9e7b37885`.
- `java -jar … --version` ha restituito `OpenTripPlanner Version: 2.10.0`.

### PBF

- URL: `https://download.geofabrik.de/europe/italy/sud-latest.osm.pbf`
- Redirect effettivo:
  `https://download.geofabrik.de/europe/italy/sud-261113.osm.pbf`
- Dimensione: `423.322.789` byte; `Last-Modified 2026-11-14 01:23:15 GMT`.
- MD5 pubblicato e verificato:
  `35c90562a87af1ba669b990a1f3896e7`.
- Metadati salvati in
  `/home/r0x4n/otp-1a/osm/sud-261113.metadata.txt`; attribuzione OSM/ODbL.

### GTFS EAV

- Sorgente riusata: `/home/r0x4n/Scaricati/google-transit.zip`, 4.105.995
  byte, SHA-256
  `9a3eeba9a84ce7de11e3daf1e1727e60705ab89a0a9f8ea369105ff436716df9`.
- Copia con nome neutro: `otp-data/eav-technical.gtfs.zip`, stesso SHA-256.
  Non è stata dedotta una data del dataset dal nome.
- `unzip -tq`: archivio valido.
- L'archivio contiene agency EAV, 124 route, 7.415 corse, 4.208 fermate,
  280.889 stop_times, 166.625 punti shape, 8.495 calendar_dates; assenti
  `calendar.txt` e `feed_info.txt`.
- **Non è ANM e non è BusOne.** La prova non acquisisce la copertura ANM né
  l'integrazione real-time.

## 4. Estrazione OSM

`osmium-tool` non era installato e `sudo` non era disponibile. È stato usato
senza root un binario ufficiale Ubuntu estratto localmente:

- `osmium-tool 1.19.0-1build1` (SHA-256 `.deb`
  `e6a8b74dd2596092d464b90c524ebf0f9ff39912277e18f148dba05b84508e9f`);
- `libboost-program-options1.90.0 1.90.0-6ubuntu1` (SHA-256 `.deb`
  `552699d9211d5e9bc6c2ff97c412a901b431ba61eb7d93c8c139c3d20f45104e`);
- `dpkg-deb -x` + `LD_LIBRARY_PATH`; versione:
  `osmium version 1.19.0`, `libosmium version 2.23.0`.

Comando:

```bash
osmium extract -b 13.80,40.55,14.85,41.40 \
  --strategy=complete_ways --set-bounds \
  -o napoli-eav-261113.osm.pbf sud-261113.osm.pbf
```

- Output: `58.877.279` byte; SHA-256
  `ca4164b471edd76fb2f5f94aab34aed4e0319104f7ad043e36c4c36ff7a71192`.
- `osmium fileinfo`: 7.672.022 nodi, 966.954 way, 14.603 relazioni;
  header bbox `(13.8,40.55,14.85,41.4)`.
- Il bbox è configurato come “fermate EAV + margine”, non come confine
  amministrativo e non come “intera area metropolitana”.

## 5. Build

Configurazione usata (anche in `infra/otp/build-config.json`):

```json
{
  "transitServiceStart": "2025-09-15",
  "transitServiceEnd": "2030-12-31",
  "transitModelTimeZone": "Europe/Rome",
  "osmDefaults": { "timeZone": "Europe/Rome" }
}
```

Senza questa configurazione OTP applicava la finestra predefinita e scartava
6.698 corse. La build finale ha caricato tutte le 7.415 corse.

Comando:

```bash
/usr/bin/time -v /usr/lib/jvm/java-25-openjdk-amd64/bin/java \
  -Xms1g -Xmx4g -jar otp-shaded-2.10.0.jar --build --save otp-data
```

Risultati:

- build OTP: `42,827 s`; wall time `48,04 s`; CPU media ~356%;
- max RSS: `2.258.000 KiB` (~2,15 GiB), 0 swap;
- grafo: `62 MB`, SHA-256
  `ba5d4a9cdc8b8b24de69dba3a8d21f58cf7bc79c46f838c985a4404171f8d29c`;
- grafo: `|V|=342.767`, `|E|=842.022`; `4.208` fermate, `541` pattern,
  `5.665` transfer vincolati.

Sono state scartate due build intermedie: la prima non aveva il PBF nella base
directory (`|E|=0`); la seconda, con PBF ma senza `build-config.json`, aveva
perso 6.698 corse per la finestra di servizio predefinita. Non sono usate come
risultato.

Warning finali:

- `CostlyAssertions` attivo (OTP segnala di non usarlo in produzione);
- `sun.misc.Unsafe` deprecato (Kryo), non bloccante;
- island pruning: `GraphConnectivity 3`, isole WALK/BICYCLE/CAR; non ha
  impedito i collegamenti provati;
- nessun warning di timezone OSM dopo l'introduzione della configurazione.

## 6. Avvio e stato attivo

```bash
systemd-run --user --unit=otp-1a --collect \
  --working-directory=/home/r0x4n/otp-1a \
  /bin/bash -lc 'exec /usr/lib/jvm/java-25-openjdk-amd64/bin/java \
    -Xms512m -Xmx2g -jar otp-shaded-2.10.0.jar \
    --load --serve otp-data >> artifacts/otp-server.log 2>&1'
```

- Unità attiva: `otp-1a`; MainPID `224830`; porta `8080`; heap `-Xmx2g`;
  RSS al momento della verifica ~`897 MB`.
- Endpoint GTFS GraphQL: `http://127.0.0.1:8080/otp/gtfs/v1`.
- Arresto:

```bash
systemctl --user stop otp-1a
ss -ltnp | grep ':8080' || true
```

Nota: il primo avvio con `nohup` è terminato durante la sessione; la prova
finale è stata rieseguita con l'unità systemd utente qui sopra.

## 7. Contratto API verificato sulla release avviata

- `POST /otp/gtfs/v1` → `{"data":{"feeds":[{"feedId":"1"}]}}`.
- `routes` ha restituito 119 route (5 route del feed non hanno corse). ID reali:
  - route shortName `2` → `1:2`;
  - route shortName `1` → `1:1`;
  - route shortName `1.` → `1:1.`;
  - route shortName `4` → `1:4`.
- Il primo tentativo con variabili GraphQL `Float!` ha prodotto:
  `VariableTypeMismatch … expected type 'CoordinateValue!'`. La query corretta
  usa letterali numerici; errore e risposta conservati in
  `/home/r0x4n/otp-1a/artifacts/baseline-float-error-{request,response}.json`.
- Introspezione `TransitFilterInput` sulla release: campi `include` ed
  `exclude`; il filtro usato è
  `preferences: { transit: { filters: [ { exclude: [ { routes: ["<id>"] } ] } ] } }`.
  Nessuna assunzione che l'ID completo sia semplicemente `2`.
- L'esclusione è a livello route/agency; l'API GTFS GraphQL non supporta
  l'esclusione di un segmento stradale arbitrario.

## 8. Prova A — Piscinola Scampia → Aversa

Coordinate: `40.892929,14.239837` → `40.974147,14.213685`; data
`2026-11-16T08:00:00+01:00`; `first: 5`; modi BUS/RAIL.

Baseline: 4 itinerari, tutti `RAIL`, route `1:2`, durata `750 s`:

```text
08:00:00 → 08:12:30  RAIL 1:2 2  Piscinola Scampia → Aversa
08:15:00 → 08:27:30  RAIL 1:2 2
08:30:00 → 08:42:30  RAIL 1:2 2
08:45:00 → 08:57:30  RAIL 1:2 2
```

Esclusione `1:2` con `transitOnly: true`: 0 itinerari,
`routingErrors=[{code: "NO_TRANSIT_CONNECTION", ...}]`. La route esclusa non
compare. Un controllo senza `transitOnly` ha restituito solo un walk di
`8.735 s` con lo stesso `routingError`: non è un'alternativa di trasporto
pubblico. **Esito: esclusione dimostrata; alternativa assente su questo
collegamento.**

## 9. Prova B — Napoli P. Garibaldi → Torre Annunziata

Coordinate: `40.851017,14.272976` → `40.759526,14.451518`; stessa data/ora;
`first: 8`; modi RAIL/BUS.

Baseline: 6 itinerari, route `1:1`, `1:4`, `1:1.`:

```text
08:03:00 → 08:32:30  RAIL 1:1  1   durata 1770 s
08:12:30 → 08:47:30  RAIL 1:4  4   durata 2100 s
08:22:30 → 08:58:00  RAIL 1:1. 1.  durata 2130 s
... ripetuti
```

Esclusione `1:1`: 4 itinerari, route `1:4` e `1:1.`, nessuna occorrenza di
`1:1`; `routingErrors=[]`:

```text
08:12:30 → 08:47:30  RAIL 1:4  4   durata 2100 s
08:22:30 → 08:58:00  RAIL 1:1. 1.  durata 2130 s
08:42:30 → 09:17:30  RAIL 1:4  4
08:52:30 → 09:28:00  RAIL 1:1. 1.
```

**Esito: esclusione dimostrata e alternativa reale con trasporto pubblico
dimostrata.**

## 10. Artefatti e riproducibilità

- Richieste/risposte principali:
  `/home/r0x4n/otp-1a/artifacts/{baseline,exclude,alt-baseline,alt-exclude}-{request,response}.json`.
- Probe completa:
  `/home/r0x4n/otp-1a/probe-artifacts/` (`feeds.json`, `routes.json`,
  `baseline-a.json`, `exclude-a.json`, `baseline-b.json`, `exclude-b.json`,
  `summary.json`).
- Script riproducibile: `python3 infra/otp/probe.py --artifacts <dir>`.
- Build log: `/home/r0x4n/otp-1a/artifacts/otp-build-final.log`.
- Server log: `/home/r0x4n/otp-1a/artifacts/otp-server.log`.

## 11. Copertura e limiti

- Giorno di prova `2026-11-16`: nel feed EAV sono attive 11 route ferroviarie
  (`1, 1., 2, 4, 5, 5., 6, 7, 8, 9, 9.`) per 682 corse. Il feed contiene 717
  corse ferroviarie totali e 6.698 corse di autolinea; queste ultime hanno
  calendario `2025-09-15`..`2025-10-31` e non sono attive alla data di prova.
  La prova non copre autobus, ANM, BusOne, real-time o database.
- Il grafo include l'intero feed EAV caricato, ma le due prove usano solo
  ferrovia. Non si dichiara copertura completa della rete EAV.
- Il bbox OSM è un'area funzionale con margine, non un confine amministrativo.
- Non è stata fatta una prova di ricalcolo dopo una perturbazione persistita;
  questa è materia dei checkpoint successivi.
- 1B non è stato avviato: `otp_client.py` resta invariato.
