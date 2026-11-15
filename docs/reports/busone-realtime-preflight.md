# BusOne realtime — preflight e stop motivato (P2.1)

Data della verifica: 2026-11-15 (Europe/Rome). Stato: **non implementato**.
Sono stati eseguiti solo probe di disponibilità, lettura dei termini e un
confronto tecnico non persistente. Non è stato creato alcuno schema
`gtfs_anm_busone`, nessun import è stato eseguito e nessuna modifica è stata
fatta al routing o al dataset `gtfs_anm`.

## 1. Disponibilità verificata

| Risorsa | Esito |
|---|---|
| `GET https://proxy.busone.app/anm/gtfs.zip` | HTTP 200, `application/zip`, 6.194.038 byte, `Last-Modified 2026-11-15 08:29:48 GMT` |
| `GET /anm/gtfs-rt/vehicle-positions.json` | HTTP 200, `application/json`, 87 veicoli nel campione |
| `GET /anm/gtfs-rt/trip-updates.json` | HTTP 200, `application/json`, 135 trip update nel campione |
| `GET /anm/status` | disponibile (non usato per l'integrazione) |

Header di risposta rilevanti:

```text
warning: 299 proxy.busone.app "Requests without X-BusOne-Client and a valid
X-BusOne-Use will not be supported in the future; see
https://proxy.busone.app/#data-terms"
x-busone-terms: noncommercial-free; permitted-users=individuals-nonprofits;
other-organizations=prior-written-permission; attribution-required;
derivatives=yes; redistribution=yes; transitous-authorized;
transitland-authorized; commercial=contact-info@busone.app
```

## 2. Termini d'uso letti

La pagina `https://proxy.busone.app/#data-terms` dichiara:

- uso gratuito per persone e organizzazioni non profit;
- altre organizzazioni richiedono **permesso scritto preventivo**;
- attribuzione obbligatoria;
- per uso commerciale: `contact-info@busone.app`;
- identificazione del client tramite:
  - `X-BusOne-Client: organizzazione/app e contatto`
  - `X-BusOne-Use: personal|nonprofit|commercial`
- le richieste senza identificazione sono ancora servite, ma ricevono un
  warning e non saranno supportate in futuro.

Il progetto ha già in configurazione `RT_USE_HEADER=nonprofit`, ma
`RT_CLIENT_HEADER` è **vuoto**. Non è stato inventato un identificativo, non
è stata usata una API key e non è stato assunto che l'hackathon rientri
automaticamente nella categoria non profit.

## 3. Confronto statico/realtime (non persistente)

Il file BusOne è stato scaricato solo in una directory temporanea fuori dal
repository e non è stato importato in PostgreSQL.

| Controllo | Esito |
|---|---|
| SHA-256 archivio BusOne | `9d8a4bba82eb72e5f38b1b5359121ce57c3d065200c3746715501da0137e8177` |
| SHA-256 `gtfs_anm` corrente | `ac0dfd987b734022efde05e98b312b59ddde68a8e49c77564e8bfbdb641f15b4` |
| Agenzie nello statico BusOne | `ANM` (Azienda Napoletana Mobilità), `FS` (Trenitalia) |
| Entità | 112 route, 32.177 trip, 2.392 stop |
| Route ID realtime presenti nello statico BusOne | 45/45 (vehicle positions), 46/46 (trip updates) |
| Trip ID realtime presenti nello statico BusOne | 81/81 (vehicle positions), 135/135 (trip updates) |
| Stop ID realtime presenti nello statico BusOne | 1.529/1.529 (trip updates) |
| Stessi ID presenti anche in `gtfs_anm` corrente | sì per tutti i campioni |

Gli ID campionati sono quindi compatibili con lo statico BusOne, ma gli archivi
**non sono identici**: `trips.txt`, `stops.txt`, `stop_times.txt`,
`calendar_dates.txt` e `shapes.txt` hanno contenuti/hash diversi. Non si può
sostituire `gtfs_anm` con BusOne e non si può mescolare i due dataset.

## 4. Perché l'integrazione è ferma

Prerequisiti mancanti:

1. **`X-BusOne-Client` reale** (organizzazione/app + contatto). La
   configurazione attuale ha `RT_CLIENT_HEADER=""`.
2. **Conferma dei termini per l'organizzazione**: la pagina richiede permesso
   scritto preventivo per soggetti diversi da persone/non profit. Serve una
   decisione esplicita del progetto, non una deduzione tecnica.
3. **Decisione di prodotto** sul dataset separato:
   - `dataset_key=anm_busone`, `schema=gtfs_anm_busone`;
   - feed OTP separato accanto a `gtfs_anm` e `gtfs_eav`;
   - gestione dell'ambiguità di due feed ANM con route ID uguali nel routing.
4. **Feature flag** per l'ingestion realtime, spento per default, e criterio di
   freshness/attribuzione.

Finché questi punti non sono confermati, non è stata aggiunta alcuna
integrazione. Il codice esistente continua a leggere il proxy BusOne tramite
`GtfsRtClient`, con header presi dalla configurazione e fallback simulato
dichiarato; nessun header è hardcoded.

## 5. Passi proposti dopo l'approvazione

```bash
# 1. configurare identificativi reali (mai nel codice)
export RT_CLIENT_HEADER='organizzazione/app - contatto@example.org'
export RT_USE_HEADER='nonprofit'   # solo se il progetto ne ha diritto

# 2. importare lo statico BusOne in uno schema separato
docker exec napoli-postgres-mobility /usr/local/bin/import-gtfs.sh \
  --zip /data/gtfs/busone-anm.gtfs.zip \
  --dataset-key anm_busone \
  --schema gtfs_anm_busone \
  --operator-id ANM \
  --operator-name 'Azienda Napoletana Mobilità' \
  --source-url https://proxy.busone.app/anm/gtfs.zip \
  --publish

# 3. aggiungere anm_busone a GTFS_DATASETS solo dopo la decisione di prodotto
#    e ricostruire il grafo in una directory separata, validando su 8081.

# 4. attivare l'ingestion realtime dietro feature flag, con i due endpoint:
#    /anm/gtfs-rt/vehicle-positions.json
#    /anm/gtfs-rt/trip-updates.json
```

Nessuna di queste operazioni è stata eseguita.
