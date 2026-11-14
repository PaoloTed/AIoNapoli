[PIANIFICATO]

# API

Contratto HTTP esposto al frontend. Questo documento e' la sorgente di verita' per chi costruisce l'interfaccia: endpoint, payload completi, envelope di risposta, contratto dello stream SSE, errori.

I tipi dei campi non si riscrivono qui: vivono in [CONTRACTS.md](CONTRACTS.md). Questo documento dice come viaggiano sulla rete.

## 1. Convenzioni

| Aspetto | Regola |
|---|---|
| Base URL | `http://localhost:8000` in sviluppo, da variabile lato frontend |
| Versione | nel path: `/api/v1` |
| Formato | JSON UTF-8, `Content-Type: application/json` |
| Errori | `application/problem+json`, RFC 9457, forma in [OPERATIONS.md](OPERATIONS.md) sezione 3 |
| Versione del contratto | `contract_version` presente in ogni corpo di risposta |
| Tempo | ISO 8601 con offset, es. `2026-11-14T18:30:00+01:00` |
| Autenticazione | nessuna, fuori dagli obiettivi del backend |
| Cache | le risposte di decisione sono `Cache-Control: no-store`: la decisione e' riproducibile, non cacheabile |
| Determinismo | stessa richiesta, stessa risposta a meno di `timestamp`; `decision_id` identico |

### 1.1 Stato dei path

La traccia congela alcune rotte e non altre. La distinzione e' dichiarata, non implicita.

| Endpoint | Stato | Fonte |
|---|---|---|
| `POST /api/v1/finding/{agent}` | congelato | traccia |
| `POST /api/v1/decision` | congelato | traccia |
| `GET /api/v1/scenario/{scenario_id}` | proposta | [ARCHITECTURE.md](ARCHITECTURE.md) sezione 6 |
| `GET /api/v1/scenario/{scenario_id}/stream` | congelato | REQ-API-06 |

Un endpoint marcato proposta si puo' cambiare, ma non in silenzio: il cambiamento passa da una voce in [DECISIONS.md](DECISIONS.md) e da un aggiornamento di questo file e di `frontend/docs/API-CLIENT.md` nello stesso commit.

### 1.2 Perche' non c'e' un endpoint di elenco scenari

Gli scenari sono una lista chiusa in configurazione (`DEMO_SCENARIO`, default `bagnoli`), non una collezione interrogabile. Aggiungere `GET /api/v1/scenarios` introdurrebbe un endpoint che la traccia non chiede.

Conseguenza per il frontend: la lista degli scenari selezionabili e' una costante compilata, allineata a mano con la configurazione del backend. Se un id non esiste, la risposta e' `404 scenario_not_found` e l'interfaccia lo mostra come stato vuoto, non come errore di sistema.

## 2. `POST /api/v1/finding/{agent}`

Riceve un finding gia' interpretato da una verticale. Non calcola nulla: valida, salva se il repository esiste, restituisce.

| Parametro | In | Valori |
|---|---|---|
| `agent` | path | `mobility`, `crowding`, `context` |

### 2.1 Richiesta

Il corpo e' il Finding con i nove campi del contratto. Nessun campo in piu', nessuno in meno.

```json
{
  "agent": "crowding",
  "type": "density_alert",
  "content": {
    "density": 0.91,
    "zone_id": "Z_BAGNOLI",
    "expected_attendance": 12000,
    "note": "afflusso in crescita dalle 17:00"
  },
  "confidence": 0.82,
  "severity": "high",
  "source_id": "ir_sensors",
  "data_reference": "occupancy:2026-11-14T17:40:00+01:00",
  "is_simulated": true,
  "timestamp": "2026-11-14T17:40:00+01:00"
}
```

`content` accetta campi arbitrari: il frontend non deve mai rimuoverli ne' validarli oltre i cinque campi letti dalle regole ([CONTRACTS.md](CONTRACTS.md) sezione 1.2).

### 2.2 Risposta 200

```json
{
  "contract_version": "1.0.0",
  "finding": {
    "agent": "crowding",
    "type": "density_alert",
    "content": { "density": 0.91, "zone_id": "Z_BAGNOLI", "expected_attendance": 12000, "note": "afflusso in crescita dalle 17:00" },
    "confidence": 0.82,
    "severity": "high",
    "source_id": "ir_sensors",
    "data_reference": "occupancy:2026-11-14T17:40:00+01:00",
    "is_simulated": true,
    "timestamp": "2026-11-14T17:40:00+01:00"
  },
  "finding_ref": "7b1e9c04a2d5"
}
```

`finding_ref` e' calcolato, non memorizzato: `sha256(canonical_json(finding))[:12]`. Il finding restituito e' identico a quello ricevuto.

### 2.3 Risposta 422

Tre casi, stessa forma, `code` diverso.

| Caso | `code` | `field` |
|---|---|---|
| campo non conforme o assente | `invalid_finding` | percorso del campo, es. `content.density` |
| agente del corpo diverso da quello del path | `agent_mismatch` | `agent` |
| l'agente si rifiuta per dati insufficienti | `agent_refusal` | assente, il motivo e' in `refusal.reason_code` |

```json
{
  "type": "https://napoli-agentic-city/errors/agent_refusal",
  "title": "Agente senza dati sufficienti",
  "status": 422,
  "code": "agent_refusal",
  "detail": "occupancy assente per la zona richiesta",
  "instance": "/api/v1/finding/crowding",
  "refusal": {
    "agent": "crowding",
    "reason_code": "missing_occupancy",
    "missing_input": ["occupancy_estimates"],
    "detail": "nessuna stima di occupazione nella finestra richiesta"
  }
}
```

Il campo `refusal` e' un'estensione dichiarata del problem+json, non un secondo corpo. Il rifiuto non e' un errore interno: produce 422, mai 500 (REQ-API-08).

## 3. `POST /api/v1/decision`

Produce la decisione: trigger, conflitto, piano, reasoning log, piu' gli oggetti che il contratto non puo' contenere.

### 3.1 Richiesta

Due forme, mutuamente esclusive. Una delle due e' obbligatoria.

| Forma | Corpo | Quando |
|---|---|---|
| scenario | `{"scenario_id": "bagnoli"}` | i finding sono gia' nel repository o nelle fixture |
| finding espliciti | `{"findings": [ ... ]}` | il chiamante fornisce i finding gia' pronti, uno per agente al massimo |

```json
{ "scenario_id": "bagnoli" }
```

```json
{
  "findings": [
    { "agent": "mobility", "type": "route_disruption", "content": { "zone_id": "Z_BAGNOLI", "congestion": 0.88 }, "confidence": 0.9, "severity": "high", "source_id": "anm", "data_reference": "rss:2026-11-14T16:12:00+01:00", "is_simulated": false, "timestamp": "2026-11-14T16:12:00+01:00" },
    { "agent": "crowding", "type": "density_alert", "content": { "density": 0.91, "zone_id": "Z_BAGNOLI" }, "confidence": 0.82, "severity": "high", "source_id": "ir_sensors", "data_reference": "occupancy:2026-11-14T17:40:00+01:00", "is_simulated": true, "timestamp": "2026-11-14T17:40:00+01:00" },
    { "agent": "context", "type": "impact_assessment", "content": { "heavy_rain": true, "expected_attendance": 12000, "zone_id": "Z_BAGNOLI" }, "confidence": 0.75, "severity": "medium", "source_id": "open_meteo", "data_reference": "weather:2026-11-14T17:00:00+01:00", "is_simulated": true, "timestamp": "2026-11-14T17:00:00+01:00" }
  ]
}
```

Regole di validazione:

- `scenario_id` e `findings` insieme, o nessuno dei due: `422 invalid_finding`, `field=request`.
- `findings` vuoto o assente senza `scenario_id`: `422 missing_finding`.
- Due finding dello stesso agente: `422 invalid_finding`, `field=findings.agent`, perche' la pipeline legge un finding per agente.
- Un finding non conforme: `422 invalid_finding` con `field=findings[i].<campo>`.

### 3.2 Risposta 200

Envelope. La `decision` dentro e' esattamente la struttura a sei campi di [CONTRACTS.md](CONTRACTS.md) sezione 2.

```json
{
  "contract_version": "1.0.0",
  "decision_id": "3f9a51c7e2b84d06",
  "decision": {
    "trigger": {
      "rule_id": "R1_line2_crowding",
      "agents_involved": ["mobility", "crowding"]
    },
    "conflict": {
      "detected": true,
      "description": "Il percorso verso Z_BAGNOLI attraversa la zona satura rilevata da crowding"
    },
    "plan": [
      {
        "priority": 1,
        "action": "Percorso via bus di superficie con priorita' 1 per sicurezza",
        "target": "operator",
        "rationale": "P1 sicurezza delle persone; densita' 0.91 oltre soglia 0.85 (R1_line2_crowding)"
      },
      {
        "priority": 1,
        "action": "Alternativa: linea R2 da Fuorigrotta, tempo stimato 20 min",
        "target": "tourist",
        "rationale": "P2 tempo di percorrenza; percorso alternativo citato in R2_conflict_route_vs_density"
      },
      {
        "priority": 1,
        "action": "Raggiungi il servizio pubblico in 15 min via percorso A",
        "target": "citizen",
        "rationale": "P3 esperienza; servizio pubblico nella stessa zona"
      }
    ],
    "reasoning_log": [
      { "step": 1, "agent": "crowding", "finding_ref": "7b1e9c04a2d5", "rule_applied": "R1_line2_crowding", "outcome": "densita' 0.91 oltre la soglia 0.85, regola scattata" },
      { "step": 2, "agent": "mobility", "finding_ref": "c4d8a0f31b6e", "rule_applied": "R2_conflict_route_vs_density", "outcome": "percorso e zona satura coincidono su Z_BAGNOLI" },
      { "step": 3, "agent": "orchestrator", "finding_ref": "7b1e9c04a2d5", "rule_applied": "P1", "outcome": "priorita' sicurezza applicata, percorso diretto scartato" }
    ],
    "confidence": 0.86,
    "timestamp": "2026-11-14T17:41:12+01:00"
  },
  "relevance": {
    "rounding": 4,
    "targets": {
      "operator": {
        "order": [0],
        "items": [
          {
            "plan_index": 0,
            "score": 0.9312,
            "contributions": [
              { "feature": "severity_score", "value": 1.0, "weight": 0.40, "contribution": 0.4000 },
              { "feature": "confidence", "value": 0.86, "weight": 0.20, "contribution": 0.1720 },
              { "feature": "affects_public_service", "value": 1, "weight": 0.20, "contribution": 0.2000 },
              { "feature": "priority_rank", "value": 1.0, "weight": 0.20, "contribution": 0.2000 }
            ]
          }
        ]
      },
      "tourist": { "order": [1], "items": [] },
      "citizen": { "order": [2], "items": [] }
    }
  },
  "narrative": {
    "mode": "replay",
    "items": [
      { "plan_index": 1, "texts": { "it": "Linea R2 da Fuorigrotta, circa 20 minuti.", "en": "Line R2 from Fuorigrotta, about 20 minutes." } }
    ]
  }
}
```

Note per chi consuma:

- `relevance.targets.<target>.order` elenca indici di `decision.plan`. Prende il posto dell'ordinamento quando serve la classifica per rilevanza.
- `decision.plan` non va mai riordinato in place dal client: `priority` e' un rango univoco per target definito dal backend ([CONTRACTS.md](CONTRACTS.md) sezione 2.1).
- `narrative.mode` vale `replay`, `live` o `off`. Serve a dichiarare all'utente se il testo e' generato o da template: la decisione e' identica nei tre casi (REQ-DEG-02).
- `narrative.items` puo' essere vuoto. L'interfaccia allora mostra `PlanItem.action` e `PlanItem.rationale`.
- `decision_id` non e' un campo della decisione: sta accanto, calcolato su JSON canonico senza `timestamp`.

### 3.3 Caso "nessuna regola scatta"

Non e' un errore: 200 con `conflict.detected=false`, `trigger.rule_id` valorizzato con la prima regola valutata nell'ordine di precedenza, `plan` con un item di monitoraggio per target e `reasoning_log` che dice per quali regole e per quale campo assente non sono scattate (REQ-ORC-13).

### 3.4 Risposta 422 e 503

| `code` | HTTP | Quando |
|---|---|---|
| `missing_finding` | 422 | nessun finding disponibile e nessuno scenario |
| `invalid_finding` | 422 | corpo malformato o finding non conforme |
| `scenario_not_found` | 404 | `scenario_id` sconosciuto |
| `upstream_timeout` | 503 | OTP o connettore non rispondono entro il timeout |
| `config_invalid` | 500 | configurazione invalida, errore di avvio |

`upstream_timeout` non deve fermare l'interfaccia: il backend ha gia' sostituito la sorgente con una fixture e la risposta contiene `is_simulated=true` sul finding corrispondente. Il 503 arriva solo quando il fallback non e' disponibile.

## 4. `GET /api/v1/scenario/{scenario_id}`

Fotografia dello scenario per il primo render, prima di aprire lo stream. Evita al frontend di dover comporre tre finding a mano.

```json
{
  "contract_version": "1.0.0",
  "scenario_id": "bagnoli",
  "title": "Regata America's Cup, Linea 2 ferma, pioggia in arrivo",
  "findings": [
    { "agent": "mobility", "type": "route_disruption", "content": { "zone_id": "Z_BAGNOLI", "congestion": 0.88 }, "confidence": 0.9, "severity": "high", "source_id": "anm", "data_reference": "rss:2026-11-14T16:12:00+01:00", "is_simulated": false, "timestamp": "2026-11-14T16:12:00+01:00" },
    { "agent": "crowding", "type": "density_alert", "content": { "density": 0.91, "zone_id": "Z_BAGNOLI" }, "confidence": 0.82, "severity": "high", "source_id": "ir_sensors", "data_reference": "occupancy:2026-11-14T17:40:00+01:00", "is_simulated": true, "timestamp": "2026-11-14T17:40:00+01:00" },
    { "agent": "context", "type": "impact_assessment", "content": { "heavy_rain": true, "expected_attendance": 12000, "zone_id": "Z_BAGNOLI" }, "confidence": 0.75, "severity": "medium", "source_id": "open_meteo", "data_reference": "weather:2026-11-14T17:00:00+01:00", "is_simulated": true, "timestamp": "2026-11-14T17:00:00+01:00" }
  ],
  "vehicle_positions": [
    { "vehicle_id": "ANM-2231", "route_id": "R2", "latitude": 40.8206, "longitude": 14.1785, "bearing": 214.5, "observed_at": "2026-11-14T17:39:48+01:00", "source_id": "anm", "is_simulated": false }
  ]
}
```

- `findings` contiene solo i finding disponibili: puo' averne uno, due o tre. L'interfaccia mostra lo stato mancante, non un errore.
- `vehicle_positions` e' opzionale e vuota se il real-time non e' disponibile. Ogni posizione porta il proprio `is_simulated`.
- `scenario_id` sconosciuto: `404 scenario_not_found`.
- Questo endpoint non produce la decisione. La decisione si chiede con `POST /api/v1/decision`.

## 5. `GET /api/v1/scenario/{scenario_id}/stream`

Stream SSE degli eventi della trace. La stessa trace che alimenta `decision.reasoning_log`: quello che si vede scorrere e' esattamente quello che la decisione conterra' (REQ-API-06).

### 5.1 Semantica HTTP

| Aspetto | Valore |
|---|---|
| Metodo | `GET`, nessun header custom: si usa `EventSource` |
| `Content-Type` | `text/event-stream; charset=utf-8` |
| `Cache-Control` | `no-cache` |
| Header proxy | `X-Accel-Buffering: no` per evitare i buffer intermedi |
| Chiusura | il server chiude dopo l'evento `decision`, oppure dopo `error` |
| `retry` | 3000 ms, dichiarato all'apertura |

Lo stream e' one-shot: descrive l'esecuzione di una decisione, non e' un feed permanente. Per una nuova decisione si apre un nuovo stream.

### 5.2 Eventi

I primi quattro nomi sono congelati da [ARCHITECTURE.md](ARCHITECTURE.md) sezione 4.2. Gli altri sono aggiunte dichiarate, necessarie al ciclo di vita della connessione.

| `event` | `data` | Quando | Stato |
|---|---|---|---|
| `start` | `{"scenario_id": "bagnoli", "contract_version": "1.0.0"}` | apertura | aggiunta |
| `phase` | `{"phase": "validazione", "index": 1}` | inizio di ogni fase | aggiunta |
| `rule_evaluated` | `{"rule_id": "R1_line2_crowding", "agents": ["mobility", "crowding"], "fired": true, "reason": "densita' 0.91 oltre soglia 0.85"}` | ogni regola R1-R4 | congelato |
| `conflict_detected` | `{"description": "...", "zone_id": "Z_BAGNOLI"}` | conflitto rilevato | congelato |
| `priority_applied` | `{"priority": "P1", "winner": "crowding"}` | priorita' applicata | congelato |
| `plan_item_created` | `{"target": "operator", "action_ref": "plan:0"}` | ogni item creato | congelato |
| `decision` | `{"decision_id": "3f9a51c7e2b84d06", "contract_version": "1.0.0"}` | fine, poi il server chiude | aggiunta |
| `error` | problem+json come in sezione 1 | errore fatale | aggiunta |

Valori di `phase`, nell'ordine in cui arrivano: `validazione`, `trace`, `regole`, `conflitto`, `priorita`, `piano`, `rilevanza`, `hash`.

`rule_evaluated` arriva per tutte e quattro le regole, anche quelle non scattate: `fired=false` con `reason` che nomina il campo o l'agente assente (REQ-ORC-06). Il frontend mostra la valutazione negativa invece di nasconderla.

### 5.3 Formato del frame

```
event: rule_evaluated
id: 3
data: {"rule_id":"R1_line2_crowding","agents":["mobility","crowding"],"fired":true,"reason":"densita' 0.91 oltre soglia 0.85"}

```

Regole: un solo `data:` per frame, JSON su una riga, `id` = numero di passo contiguo da 1, riga vuota di terminazione. Nessun commento keep-alive all'interno della decisione: lo stream dura meno di due secondi.

### 5.4 Ripresa e disconnessione

`EventSource` riconnette da solo. Poiche' lo stream e' one-shot, la riconnessione riparte da capo: il frontend azzera la timeline prima di riaprire, per non duplicare i passi. Se il server e' irraggiungibile, lo stato dell'interfaccia e' `degraded`: si mostra la decisione gia' ottenuta da `POST /decision`, senza timeline animata.

## 6. CORS

Il frontend gira su un origin diverso dal backend in sviluppo.

| Aspetto | Regola |
|---|---|
| Origin ammessi | lista bianca da variabile `CORS_ORIGINS`, default `http://localhost:3000` |
| Metodi | `GET`, `POST`, `OPTIONS` |
| Header permessi | `Content-Type` |
| Credenziali | no, nessun cookie, nessuna autenticazione |
| Preflight | solo per `POST` con `Content-Type: application/json`; lo stream `GET` non ne ha bisogno |

## 7. Come si verifica che il contratto non sia cambiato

| Verifica | Come |
|---|---|
| versione | `contract_version` nella risposta confrontata con quella attesa dal client; disallineamento produce un avviso visibile, non un crash |
| campi del finding | test di schema: insieme dei campi uguale all'atteso (REQ-CONTR-01) |
| campi della decisione | test di schema: insieme dei campi uguale all'atteso (REQ-CONTR-02) |
| ordine degli eventi SSE | test: la sequenza coincide con `reasoning_log` (REQ-API-06) |
| determinismo | due `POST /decision` identiche producono lo stesso `decision_id` (REQ-ORC-12) |

## 8. Cosa il frontend non deve fare

- Calcolare regole, priorita', punteggi o testi: sono del backend, e il frontend li mostra.
- Mostrare il `reasoning_log` a turista e cittadino: REQ-ORC-11 lo vieta sui contenuti del piano, e per coerenza vale anche sull'interfaccia.
- Trattare `is_simulated=true` come errore: e' un dato dichiarato.
- Dedurre campi assenti di `content` con un default silenzioso. Se il campo manca, il dato manca.
- Chiamare il database o le fonti esterne: l'unico canale e' questa API.
