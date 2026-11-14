[PIANIFICATO]

# Contratti

Strutture condivise tra backend, agenti e frontend. Le due strutture principali sono congelate dalla traccia. Questo documento le riporta, dichiara le regole di collocazione per i dati che non possono contenerle, e fissa le funzioni di accesso che rendono il contratto robusto senza modificarlo.

## 1. Finding

Nove campi, tutti obbligatori.

| Campo | Tipo | Vincolo | Note |
|---|---|---|---|
| `agent` | enum | `mobility`, `crowding`, `context` | nessun altro valore |
| `type` | stringa | coerente con l'agente | vedi tabella 1.1 |
| `content` | oggetto | libero | struttura per dominio, non validata oltre i campi letti dalle regole |
| `confidence` | float | 0..1 | |
| `severity` | enum | `low`, `medium`, `high`, `critical` | |
| `source_id` | stringa | lunghezza minima 1 | identificatore della fonte |
| `data_reference` | stringa | lunghezza minima 1 | riferimento al dato grezzo |
| `is_simulated` | booleano | | vero per ogni dato sintetico |
| `timestamp` | data ISO 8601 | coercizione a UTC | data del finding |

### 1.1 Type ammessi per agente

| Agente | Type ammessi |
|---|---|
| `mobility` | `route_disruption`, `route_alternative` |
| `crowding` | `density_alert` |
| `context` | `impact_assessment` |

Una coppia agente e type non presente in questa tabella e' invalida.

### 1.2 Campi di `content` letti dalle regole

`content` resta libero. Questi sono gli unici campi che qualcuno legge.

| Campo | Letto da | Tipo | Obbligatorio |
|---|---|---|---|
| `density` | R1, R2, R3 | float 0..1 | per `agent=crowding` |
| `zone_id` | R2 | stringa | consigliato per `mobility` e `crowding` |
| `heavy_rain` | R3 | booleano | per `agent=context` |
| `congestion` | R4 | float 0..1 | per `agent=mobility` |
| `expected_attendance` | R4 | intero | per `agent=context` |

Nessun altro campo e' contrattuale. La loro assenza non invalida il finding: rende una regola non scattante con motivo.

## 2. Decision

Sei campi, tutti obbligatori.

| Campo | Tipo | Vincolo |
|---|---|---|
| `trigger` | oggetto | `rule_id` tra i quattro dichiarati, `agents_involved` non vuoto |
| `conflict` | oggetto | `detected` booleano, `description` stringa non vuota |
| `plan` | lista | almeno un item |
| `reasoning_log` | lista | almeno un passo |
| `confidence` | float | 0..1 |
| `timestamp` | data ISO 8601 | data della decisione |

### 2.1 PlanItem

| Campo | Tipo | Significato |
|---|---|---|
| `priority` | intero >= 1 | rango d'ordine univoco per target, non il livello P1-P3 |
| `action` | stringa | azione raccomandata in italiano |
| `target` | enum | `operator`, `tourist`, `citizen` |
| `rationale` | stringa | regola o priorita' applicata, citata esplicitamente |

Il livello di priorita' P1, P2, P3 vive nel `rationale` come testo. Motivo: il frontend ordina per `priority`, e un rango univoco rende l'ordine definito.

### 2.2 ReasoningStep

| Campo | Tipo | Vincolo |
|---|---|---|
| `step` | intero >= 1 | contiguo, parte da 1 |
| `agent` | stringa | agente o componente che ha prodotto il passo |
| `finding_ref` | stringa | riferimento a un finding, non testo libero |
| `rule_applied` | stringa | uno dei quattro ID o una costante dichiarata |
| `outcome` | stringa | cosa e' cambiato dopo il passo |

## 3. Refusal

Un agente senza dati sufficienti non produce un finding. Produce un rifiuto. Il rifiuto non e' un errore: e' un esito previsto.

| Campo | Tipo | Significato |
|---|---|---|
| `agent` | enum | agente che rifiuta |
| `reason_code` | stringa | codice stabile, vedi tabella 3.1 |
| `missing_input` | lista di stringhe | campi o tabelle assenti |
| `detail` | stringa | spiegazione leggibile |

### 3.1 Codici di rifiuto

| Codice | Agente | Significato |
|---|---|---|
| `missing_gtfs` | mobility | nessun GTFS per la linea richiesta |
| `unmapped_point` | mobility | origine o destinazione non mappate su una fermata |
| `out_of_horizon` | mobility | finestra oltre l'orizzonte del GTFS statico senza simulazione |
| `missing_occupancy` | crowding | occupancy assente e nessuna simulazione dichiarata |
| `missing_geofence` | crowding | evento senza geo-fence |
| `invalid_density` | crowding | densita' fuori dal range 0..1 |
| `missing_alert_level` | context | meteo senza livello di allerta |
| `missing_time_window` | context | evento senza finestra temporale |
| `unsourced_alert` | context | alert senza fonte citata |

## 4. Regole di collocazione

I contratti sono congelati. Questi dati non possono entrarci, e questa e' la decisione su dove vivono.

| # | Dato che manca | Dove vive | Motivo |
|---|---|---|---|
| C1 | identificatore del finding | calcolato: `sha256(canonical_json(finding))[:12]`, chiamato `finding_ref` | nessun campo aggiunto, riferimento verificabile e ricalcolabile |
| C2 | piu' regole scattate insieme | `trigger.rule_id` e' la regola dominante secondo `rule_precedence` in configurazione; le altre restano nel `reasoning_log` | nessuna informazione persa, contratto rispettato |
| C3 | testo multilingua | `action` in italiano; la traduzione vive in `narrative`, fuori dalla decisione | il contratto non si tocca |
| C4 | azione scartata | `conflict.description` e `reasoning_log[].outcome`; il `rationale` dell'azione scelta la cita | il momento "l'orchestratore rifiuta la deviazione" resta visibile |
| C5 | livello P1-P3 dell'item | `rationale` come testo; `priority` e' il rango | ordinamento definito, semantica conservata |
| C6 | secondo conflitto | non rappresentato: una decisione, un conflitto, il piu' prioritario; gli altri nel log | limite dichiarato, non silenzioso |
| C7 | confidence della decisione | media pesata delle confidence dei finding citati, pesi in `rules.yaml`, arrotondata a 2 decimali | formula unica, riproducibile |
| C8 | piano quando nessuna regola scatta | un item per target con testo di monitoraggio, dichiarato in configurazione | `plan` resta non vuoto senza inventare azioni |
| C9 | punteggio di rilevanza | oggetto separato `RelevanceScore`, restituito accanto alla decisione, mai dentro | contratto intatto |
| C10 | versione del contratto | costante `CONTRACT_VERSION` in `shared/schemas`, esposta in ogni risposta | permette di rilevare disallineamenti tra backend e frontend |

## 5. Funzioni di accesso a `content`

`content` e' libero. L'accesso avviene tramite funzioni con semantica esplicita, che restituiscono `None` quando il dato non c'e'.

```python
def density(f: Finding) -> float | None
def zone_id(f: Finding) -> str | None
def heavy_rain(f: Finding) -> bool | None
def congestion(f: Finding) -> float | None
def expected_attendance(f: Finding) -> int | None
```

Motivo: un validatore condizionale su `content` impedisce a una verticale di produrre il proprio finding quando un campo manca. Con `None` il finding e' valido, la regola non scatta, e il motivo entra nel log. Il contratto resta stabile e l'attrito tra team sparisce.

## 6. Unita' e conversioni

Un'incoerenza reale tra traccia e regole: la traccia dichiara `occupancy_pct` in 0..100, le regole leggono `density` in 0..1.

| Grandezza | Unita' | Dove | Conversione |
|---|---|---|---|
| `occupancy_pct` | 0..100 | tabella `occupancy_estimates` | |
| `density` | 0..1 | `content` del finding crowding | `density = occupancy_pct / 100` |
| soglia R1 | 0.85 | `rules.yaml`, nome `density_threshold_0_1` | |
| soglia R3 | 0.70 | `rules.yaml`, nome `density_threshold_0_1` | |

La conversione ha una sola implementazione, `occupancy_to_density()`, in `domain/logic/units.py`, con test dedicato. Le soglie portano l'unita' nel nome.

## 7. RelevanceScore

Struttura separata dalla decisione (voce C9). Vive accanto, non dentro: i sei campi non si toccano.

| Campo | Tipo | Vincolo |
|---|---|---|
| `rounding` | intero | decimali del punteggio, default 4 |
| `targets` | oggetto | una chiave per `operator`, `tourist`, `citizen` |
| `targets.<target>.order` | lista di interi | indici di `Decision.plan`, tutti presenti, nessun duplicato |
| `targets.<target>.items` | lista di `ScoredItem` | un elemento per indice citato in `order` |
| `ScoredItem.plan_index` | intero >= 0 | indice dell'item in `Decision.plan` |
| `ScoredItem.score` | float | 0..1, arrotondato a `rounding` |
| `ScoredItem.contributions` | lista di `Contribution` | somma di `contribution` uguale a `score` |
| `Contribution.feature` | stringa | una delle feature ammesse in `relevance.yaml` |
| `Contribution.value` | numero | valore della feature prima del peso |
| `Contribution.weight` | float | peso della feature per quel target |
| `Contribution.contribution` | float | `value * weight`, arrotondato |

`plan_index` e' l'unico modo di collegare un punteggio a un item: `PlanItem` non ha identificatore, e aggiungerne uno violerebbe il contratto.

`order` e `priority` possono divergere: `priority` e' il rango deciso dall'orchestratore nella risoluzione delle priorita', `order` e' la classifica per rilevanza. Quando un client ordina, sceglie una delle due e lo dichiara; l'interfaccia usa `order` e mostra `priority` come etichetta.

### 7.1 Narrative

Testo del piano riformulato, fuori dalla decisione (voce C3). Struttura restituita accanto alla decisione.

| Campo | Tipo | Vincolo |
|---|---|---|
| `mode` | enum | `replay`, `live`, `off` |
| `items` | lista | puo' essere vuota se il modello e' spento e non c'e' template |
| `items[].plan_index` | intero >= 0 | indice dell'item in `Decision.plan` |
| `items[].texts` | oggetto | chiave `it` obbligatoria, `en` solo per il target `tourist` |

`mode` dichiara la provenienza del testo. La decisione e' identica nei tre modi: cambia la forma, non la sostanza (REQ-DEG-02).

## 8. Compatibilita'

- I contratti sono versionati con `CONTRACT_VERSION`.
- Un cambiamento ai nove o ai sei campi richiede decisione di team e aggiornamento coordinato di backend e frontend nello stesso commit.
- Un cambiamento ai campi di `content` letti dalle regole e' ammesso, ma passa da una voce in [DECISIONS.md](DECISIONS.md).
- `RelevanceScore` e `Narrative` non sono congelati dalla traccia: cambiano insieme a [API.md](API.md) e a `frontend/docs/API-CLIENT.md`, nello stesso commit.
- Un test di schema confronta l'insieme dei campi con una costante attesa: se qualcuno aggiunge un campo, la suite fallisce.
