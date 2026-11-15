# Contratto — Travel planning HTTP (`POST /api/v1/journeys/plan`)

Stato: **implementato** nel backend, contratto proposto in questo documento.
Il frontend non è stato modificato. L'endpoint non applica perturbazioni P0 e
non espone l'esclusione di route usata dai test di regressione.

## 1. Richiesta

`Content-Type: application/json`. I campi sono in `snake_case`, coerenti con
il resto delle API del progetto.

```json
{
  "origin": { "lat": 40.8943044, "lon": 14.2308735 },
  "destination": { "lat": 40.8047221, "lon": 14.1745403 },
  "depart_at": "2026-11-16T08:00:00",
  "timezone": "Europe/Rome",
  "modes": ["WALK", "BUS", "RAIL", "SUBWAY"],
  "transit_only": true,
  "first": 10
}
```

| Campo | Tipo | Obbligatorio | Regole |
|---|---|---:|---|
| `origin` | oggetto | sì | `lat` in [-90, 90], `lon` in [-180, 180], finiti |
| `destination` | oggetto | sì | come `origin` |
| `depart_at` | ISO 8601 | uno dei due | partenza richiesta |
| `arrive_by` | ISO 8601 | uno dei due | arrivo richiesto; mutuamente esclusivo con `depart_at` |
| `timezone` | stringa | no | default `Europe/Rome`; usata per datetime senza offset |
| `modes` | lista | no | default `WALK,BUS,RAIL,SUBWAY`; almeno un modo transit |
| `transit_only` | booleano | no | default `false` |
| `first` | intero | no | 1..20, default 5 |

Un datetime con offset conserva il proprio offset. Un datetime senza offset
viene interpretato nel fuso `timezone`. Non è possibile omettere entrambi i
tempi né specificarli entrambi.

## 2. Risposta 200

```json
{
  "contract_version": "1.0.0",
  "status": "ok",
  "timezone": "Europe/Rome",
  "itineraries": [
    {
      "index": 0,
      "start": "2026-11-16T08:00:00+01:00",
      "end": "2026-11-16T09:31:31+01:00",
      "duration_s": 5491,
      "walk_time_s": 900,
      "walk_distance_m": 1200.0,
      "transfers": 2,
      "generalized_cost": 2200,
      "legs": [
        {
          "mode": "SUBWAY",
          "transit_leg": true,
          "duration_s": 1200.0,
          "start_scheduled": "2026-11-16T08:10:00+01:00",
          "start_estimated": null,
          "start_delay_s": null,
          "end_scheduled": "2026-11-16T08:30:00+01:00",
          "end_estimated": null,
          "end_delay_s": null,
          "route": "L1",
          "route_id": "1:4955",
          "route_short_name": "L1",
          "route_long_name": "METRO LINEA L1",
          "route_mode": "SUBWAY",
          "agency_id": "ANM",
          "agency_gtfs_id": "1:ANM",
          "agency_name": "Azienda Napoletana Mobilità",
          "operator": "Azienda Napoletana Mobilità",
          "trip_id": "1:388_CodUdp:D600_31943746",
          "from_stop_id": "1:6312",
          "to_stop_id": "1:2167",
          "from_name": "CHIAIANO",
          "to_name": "COROGLIO - CITTÀ DELLA SCIEZA",
          "from_lat": 40.890978,
          "from_lon": 14.223564,
          "to_lat": 40.804463,
          "to_lon": 14.174222,
          "geometry": null,
          "geometry_length": null
        }
      ]
    }
  ],
  "routing_errors": [],
  "source": {
    "source_id": "otp",
    "data_reference": "http://127.0.0.1:8080/otp/gtfs/v1",
    "is_simulated": false
  }
}
```

`status` vale `ok` oppure `no_route`. `no_route` è un esito di routing, non un
errore di trasporto: la risposta resta HTTP 200, `itineraries` è vuota e
`routing_errors` riporta i codici OTP (ad esempio
`NO_TRANSIT_CONNECTION_IN_SEARCH_WINDOW`).

Gli ID `route_id`, `trip_id`, `from_stop_id`, `to_stop_id` sono feed-scoped
(`feedId:gtfsId`) e il `feedId` può cambiare a ogni build. `agency_id` è
l'identificativo GTFS originale dell'agenzia; `operator` è il nome leggibile.
Il database conserva gli ID originali senza prefisso.

## 3. Errori

Formato RFC 9457 `application/problem+json`, come le altre API.

| HTTP | `code` | Significato |
|---:|---|---|
| 422 | `invalid_journey_request` | coordinate, date, fuso, modi o `first` non validi |
| 504 | `otp_timeout` | timeout verso OTP |
| 503 | `otp_unavailable` | OTP non raggiungibile |
| 502 | `otp_http_error` | OTP ha risposto con HTTP >= 400 |
| 502 | `otp_graphql_error` | OTP ha risposto con `errors` GraphQL |
| 502 | `otp_invalid_response` | JSON o schema di risposta non valido |

Il campo `field` è valorizzato quando l'errore riguarda un campo della
richiesta. Non viene mai restituito un itinerario inventato o una fixture al
posto di un errore reale.

## 4. Esempio

```bash
curl -sS http://127.0.0.1:8000/api/v1/journeys/plan \
  -H 'Content-Type: application/json' \
  -d '{
    "origin": {"lat": 40.8943044, "lon": 14.2308735},
    "destination": {"lat": 40.8047221, "lon": 14.1745403},
    "depart_at": "2026-11-16T08:00:00",
    "timezone": "Europe/Rome",
    "modes": ["WALK", "BUS", "RAIL", "SUBWAY"],
    "transit_only": true,
    "first": 10
  }'
```

## 5. Limiti dichiarati

- L'endpoint non applica chiusure o perturbazioni persistite (P0 escluso).
- Non espone `exclude_route_ids`: l'esclusione L1 è solo un test di regressione.
- La copertura dipende dai feed caricati nel grafo OTP: ANM valida fino al
  2026-12-31, EAV fino al 2030-12-31 nel grafo corrente.
- Il routing non restituisce indicazioni stradali turn-by-turn né prezzi.
- La modalità `demo` del backend resta separata: se `ROUTING_MODE=demo`, la
  risposta è marcata `source.is_simulated=true`.

## 6. Evoluzione applicata — perturbazioni e prompt naturale

Stato: **implementato**. Gli endpoint `/api/v1/journeys/plan` e
`/api/v1/journeys` chiamano la stessa orchestrazione. Il primo usa coordinate,
il secondo interpreta un prompt e risolve i luoghi; per "da qui" servono le
coordinate del client in `client_location`.

### 6.1 Nuovi stati

`status` distingue:

| Valore | Significato |
|---|---|
| `ok` | almeno un itinerario verificato |
| `no_route` | OTP non ha restituito itinerari |
| `no_verified_route` | esistono candidati ma nessuno è verificabile senza il problema attivo |
| `insufficient_data` | dati/persistenze necessari non disponibili |
| `needs_clarification` | luogo, orario o preferenza da chiarire |
| `place_not_found` | luogo non risolto |
| `invalid_request` | contraddizione semantica nel prompt |

`no_route`, `no_verified_route` e `insufficient_data` non sono la stessa cosa
e non vengono mai convertiti in un viaggio inventato.

### 6.2 Campi aggiuntivi della risposta coordinate

`best_itinerary_index`, `unverified_itineraries`, `impacts`,
`avoided_problems`, `uncertainties`, `sources`, `agent_trace`, `coverage`.
`coverage` riporta `routing_calls` (massimo 3), budget, numero di perturbazioni
considerate, filtro `is_simulated`, controlli stradali e motivo di un esito
negativo. `sources` espone fonte, validità, revisione, stato di verifica,
incertezza e anzianità (`age_s`). `agent_trace` contiene solo contributi
sintetici, mai ragionamento interno del modello.

Le perturbazioni simulate sono escluse per default anche in lettura. Per
diagnosi backend sono disponibili:

```bash
curl -sS 'http://127.0.0.1:8000/api/v1/disruptions?include_simulated=false'
curl -sS 'http://127.0.0.1:8000/api/v1/ingestion/status'
curl -sS 'http://127.0.0.1:8000/api/v1/ingestion/sources'
```

### 6.3 Richiesta prompt

```json
{
  "prompt": "Da via Giovanni Antonio Campano a Città della Scienza domani alle 8",
  "client_location": {"lat": 40.8943044, "lon": 14.2308735},
  "timezone": "Europe/Rome",
  "context": {
    "selected_candidates": {"origin": "osm:way-group:..."},
    "accept_unsupported_constraints": false
  }
}
```

La risposta contiene `interpretation`, `clarification`, `resolved_places` e
`journey` (lo stesso contratto coordinate). Le date senza offset sono
interpretate in `timezone`; il default, se non è indicata una partenza, è
l'ora corrente Europe/Rome ed è dichiarato nella risposta. Per "senza salite",
accessibilità o altri vincoli non verificabili il server chiede conferma e non
li ignora silenziosamente.

### 6.4 Applicazione delle perturbazioni

- Le route con effetto `block` vengono escluse da OTP usando gli ID
  feed-scoped scoperti dal grafo corrente. Per i blocchi a livello di trip o
  stop OTP 2.10 non espone un filtro equivalente: la route viene esclusa
  conservativamente e la risposta lo dichiara.
- Le chiusure stradali non hanno un parametro OTP fittizio. I candidati sono
  controllati geometricamente in metri; quelli che percorrono la way chiusa
  vengono esclusi, quelli incerti non sono presentati come verificati. Se non
  resta un'alternativa verificabile la risposta è `no_verified_route`.
- Perturbazioni future, scadute, risolte o annullate non bloccano il viaggio.
  Una finestra giornaliera non è un blocco continuo. La data della notizia non
  è automaticamente l'inizio del problema.

### 6.5 Limiti dichiarati

- L'applicazione reale delle perturbazioni richiede `APP_PROFILE=postgres` e
  i cataloghi GTFS/OSM; nel profilo `memory` resta il percorso OTP semplice.
- L'interpretazione AI delle notizie richiede un provider configurato. Con
  provider assente i documenti restano `pending`/`needs_review`, non diventano
  avvisi e non vengono simulati.
- La copertura delle chiusure stradali dipende dalle geometrie OSM e dalle
  polilinee OTP disponibili. Un'intersezione 2D non viene promossa a blocco.
