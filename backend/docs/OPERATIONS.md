[PIANIFICATO]

# Operations

Configurazione, errori, degradazione, comandi. Tutto cio' che serve per eseguire, diagnosticare e mettere in scena il sistema.

## 1. Variabili d'ambiente

| Variabile | Default | Significato |
|---|---|---|
| `APP_PROFILE` | `memory` | `memory`, `sqlite`, `postgres` |
| `APP_CONFIG_DIR` | `backend/app/services/orchestrator` | dove stanno `rules.yaml` e `relevance.yaml` |
| `DATABASE_URL` | vuoto | richiesto solo con profilo `postgres` |
| `SQLITE_PATH` | `.data/app.db` | richiesto solo con profilo `sqlite` |
| `OTP_BASE_URL` | `http://localhost:8080` | endpoint GraphQL di OpenTripPlanner |
| `OTP_TIMEOUT_S` | `5` | timeout della query, in secondi |
| `LLM_MODE` | `replay` | `replay`, `live`, `off` |
| `LLM_CACHE_DIR` | `.cache/llm` | cache delle generazioni per il replay |
| `HTTP_TIMEOUT_S` | `10` | timeout dei connettori |
| `DEMO_SCENARIO` | `bagnoli` | scenario della demo |
| `LOG_LEVEL` | `info` | livello di log |

Nessun valore e' hardcoded nel codice. Ogni variabile ha un default che permette l'avvio senza configurazione.

## 2. File di configurazione

### 2.1 `rules.yaml`

| Chiave | Tipo | Significato |
|---|---|---|
| `r1.density_threshold_0_1` | float | soglia di densita' per R1, default 0.85 |
| `r1.severity_min` | stringa | severita' minima di mobilita' per R1, default `high` |
| `r2.density_threshold_0_1` | float | soglia di densita' per il conflitto, default 0.85 |
| `r3.density_threshold_0_1` | float | soglia di densita' per R3, default 0.70 |
| `r3.requires_heavy_rain` | booleano | R3 richiede pioggia intensa, default vero |
| `r4.attendance_threshold` | intero | affluenza oltre la quale R4 valuta alternative |
| `rule_precedence` | lista | ordine di dominanza quando piu' regole scattano |
| `confidence_weights` | oggetto | pesi per il calcolo della confidence della decisione |
| `monitoring_text` | oggetto | testo dell'item di monitoraggio per target |

### 2.2 `relevance.yaml`

| Chiave | Tipo | Significato |
|---|---|---|
| `features` | lista | feature ammesse, con tipo e derivazione |
| `weights.<target>` | oggetto | peso per feature e per target |
| `filter_threshold` | float | soglia opzionale di filtro, null per non filtrare |
| `rounding` | intero | decimali del punteggio, default 4 |

Esempio di forma, non di valori:

```yaml
weights:
  operator:
    severity_score: 0.40
    confidence: 0.20
    affects_public_service: 0.20
    priority_rank: 0.20
  tourist:
    affects_route: 0.35
    time_to_event: 0.30
    severity_score: 0.20
    confidence: 0.15
  citizen:
    affects_public_service: 0.40
    affects_route: 0.25
    severity_score: 0.20
    confidence: 0.15
```

### 2.3 `derivation.yaml`

Mappature del connettore RSS: `severity` e `confidence` per fonte, keyword, livelli di allerta verso `heavy_rain`.

### 2.4 Validazione

Tutti i file sono validati da modelli Pydantic all'avvio. Un errore di configurazione produce `config_invalid` e blocca l'avvio. Non si degrada su configurazione invalida: la configurazione e' parte del codice.

## 3. Tassonomia degli errori

### 3.1 Formato della risposta

```json
{
  "type": "https://napoli-agentic-city/errors/invalid_finding",
  "title": "Finding non valido",
  "status": 422,
  "code": "invalid_finding",
  "field": "content.density",
  "detail": "density deve essere compresa tra 0 e 1",
  "instance": "/api/v1/finding/crowding"
}
```

Formato `application/problem+json`, conforme a RFC 9457.

### 3.2 Codici

| Codice | HTTP | Significato | Quando |
|---|---|---|---|
| `invalid_finding` | 422 | finding non conforme al contratto | validazione fallita |
| `agent_mismatch` | 422 | agente diverso dall'endpoint | finding crowding su endpoint mobility |
| `missing_finding` | 422 | mancano finding per produrre la decisione | richiesta di decisione con meno di un finding |
| `agent_refusal` | 422 | l'agente si rifiuta con motivo | dati insufficienti, corpo con `Refusal` |
| `scenario_not_found` | 404 | scenario inesistente | `GET` su id sconosciuto |
| `config_invalid` | 500 | configurazione invalida | all'avvio, non a richiesta |
| `upstream_timeout` | 503 | sorgente esterna non risponde | timeout di connettore o OTP |
| `upstream_unavailable` | 503 | sorgente esterna non raggiungibile | errore di rete |
| `llm_unavailable` | 200 con fallback | modello non disponibile | si usa il template deterministico, la risposta resta valida |
| `internal_error` | 500 | errore non previsto | ultimo livello, sempre loggato |

### 3.3 Regole

- Un input malformato produce 422, mai 500.
- Un rifiuto di agente e' un esito previsto e non e' un errore interno.
- Un fallback riuscito produce 200 con `is_simulated=true` e non un errore.
- Ogni errore 5xx e' loggato con il `decision_id` o il `finding_ref` se disponibili.
- Nessun `except: pass`. Nessun fallback silenzioso.

## 4. Degradazione

Matrice di cosa succede quando un componente non e' disponibile. Ogni riga e' un requisito verificabile.

| Componente spento | Comportamento | Effetto sulla demo |
|---|---|---|
| rete | si usano fixture e cache | nessuno, la demo gira |
| OpenTripPlanner | l'agente Mobilita usa la fixture registrata, `is_simulated=true` | itinerario mostrato, dichiarato simulato |
| database | profilo `memory`, fixture JSON | nessuno |
| LLM | template deterministico | testo meno vario, decisione identica |
| feed RSS | fallback con set simulato, `is_simulated=true` | alert mostrati, dichiarati simulati |
| meteo | snapshot simulato dichiarato | R3 valutata su dati simulati |
| sensori di occupazione | simulazione statistica | densita' stimata, dichiarata |

Regola: la demo non richiede mai un componente esterno per produrre una decisione valida.

## 5. Comandi

### 5.1 Sviluppo

```
python -m venv .venv
.venv/Scripts/Activate.ps1
pip install -e ".[dev]"
pytest
```

### 5.2 Avvio del backend

```
uvicorn app.main:app --reload --port 8000
```

### 5.3 Ingestion

```
python -m app.cli ingest --connector rss
python -m app.cli ingest --connector rss --fallback
python -m app.cli ingest --all --fallback
```

Lo scheduler non e' in-process. Il cron esterno e' dichiarato in `infra/` e non e' parte della demo.

### 5.4 Database

```
python -m app.cli db migrate
python -m app.cli db seed
python -m app.cli db reset
```

### 5.5 Demo

```
python -m app.cli demo --scenario bagnoli --profile memory
python -m app.cli demo --scenario bagnoli --report
```

Il secondo comando produce il file con le metriche della sezione 7.

### 5.6 OpenTripPlanner

```
docker compose -f infra/otp/docker-compose.yml run --rm otp otp --build --save /var/otp/graphs/napoli
docker compose -f infra/otp/docker-compose.yml up otp
```

Il build avviene una volta, prima dell'evento. Il serve e' veloce. I due comandi non si concatenano.

### 5.7 Verifica della configurazione

```
python -m app.cli config validate
```

Stampa i valori effettivi e fallisce se un file e' invalido.

## 6. Test

| Tipo | Comando | Rete | Database |
|---|---|---|---|
| unit | `pytest -m "not network and not db"` | no | no |
| architettura | `pytest tests/architecture` | no | no |
| contratti | `pytest tests/contracts` | no | no |
| integrazione | `pytest -m db` | no | Postgres via testcontainers |
| rete | `pytest -m network` | si | no |

Marker dichiarati in `pyproject.toml`. Per default la rete e' inibita: `pytest-socket` in modalita' disable globale.

## 7. Metriche della demo

Solo metriche calcolabili da campi esistenti. Nessuna stima non misurata.

| Metrica | Come si calcola | Fonte |
|---|---|---|
| tempo tra finding e decisione | `decision.timestamp` meno il `timestamp` del finding piu' recente | contratti |
| passi del reasoning log | lunghezza di `reasoning_log` | contratto |
| copertura dei target | numero di target distinti in `plan` su tre | contratto |
| azioni raccomandate | lunghezza di `plan` | contratto |
| quota di dati simulati | finding con `is_simulated=true` sul totale | contratto |
| decisioni identiche su input identico | confronto di `decision_id` su due esecuzioni | audit |
| punteggio di rilevanza per target | contributi per feature dal calcolo di rilevanza | oggetto separato |
| tempo di risposta di OTP | durata della query GraphQL | log di `scripts/demo_timing.py` |
| righe ingerite per connettore | `rows_written` in `ingestion_runs` | database |

## 8. Logging

- Log strutturato in JSON, un evento per riga.
- Ogni riga porta `timestamp`, `level`, `component`, `event`, e `finding_ref` o `decision_id` quando applicabili.
- Nessun dato personale, nessun segreto, nessun payload completo in log a livello `info`.
- La trace del core e' loggabile a livello `debug` con un flag esplicito.

## 9. Vincoli d'ambiente noti

| Vincolo | Conseguenza |
|---|---|
| shell PowerShell 5.1 su Windows | separatore `;`, non `&&`; percorsi con spazi quotati |
| JVM locale Java 25 | OpenTripPlanner richiede Java 21, quindi solo container |
| git non traccia cartelle vuote | `.gitkeep` nelle cartelle vuote |
| feed con encoding eterogeneo | Il Mattino e' ISO-8859-1, va decodificato prima del parsing |
| date non standard nel feed dei Vigili del Fuoco e de Il Mattino | parser dedicato, non `feedparser` puro |
