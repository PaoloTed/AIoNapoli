[PIANIFICATO]

# Stack

Tecnologie usate dal backend, con ruolo, motivo della scelta e alternative scartate. Le voci marcate `[PROPOSTA]` non sono ancora pinnate in `pyproject.toml`: la versione si fissa alla prima installazione e da quel momento si aggiorna solo con una voce in [DECISIONS.md](DECISIONS.md).

Regola: una dipendenza che non sta in questa tabella non entra nel progetto.

## 1. Runtime e linguaggio

| Tecnologia | Versione | Ruolo | Stato |
|---|---|---|---|
| Python | 3.12 | linguaggio del backend e del core | `[PROPOSTA]` |
| venv + pip | — | ambiente e installazione, nessun gestore alternativo | deciso |

Motivo del 3.12: supporto pieno di `datetime.UTC`, `type` statement e delle versioni correnti di Pydantic. Alternative scartate: 3.11 per prudenza, scartata perche' non aggiunge nulla; 3.13, scartata perche' le wheel delle dipendenze scientifiche e di testcontainers arrivano in ritardo.

## 2. Web

| Tecnologia | Versione | Ruolo | Stato |
|---|---|---|---|
| FastAPI | 0.115 | applicazione HTTP, validazione automatica, OpenAPI generato | `[PROPOSTA]` |
| uvicorn | 0.32 | server ASGI, `--reload` in sviluppo | `[PROPOSTA]` |
| Pydantic | 2.x | schemi di contratto, validazione di configurazione | vincolato da NFR-02 |
| sse-starlette | 2.x | `EventSourceResponse` per lo stream della trace | `[PROPOSTA]` |
| PyYAML | 6.x | lettura di `rules.yaml`, `relevance.yaml`, `derivation.yaml` | `[PROPOSTA]` |

Motivo di FastAPI: la validazione dei nove campi e dei sei campi e' la stessa cosa dei modelli Pydantic richiesti da NFR-02, e l'OpenAPI generato in `/openapi.json` e' la verifica automatica che [API.md](API.md) non mente. Alternative scartate: Flask, scartato perche' la validazione andrebbe scritta a mano due volte; Litestar, scartato per minore familiarita' del team.

Motivo di sse-starlette: gestisce `ping`, disconnessione del client e header anti-buffer. Alternativa scartata: `StreamingResponse` nativo con `yield`, tenuto come piano di riserva se si vuole una dipendenza in meno.

## 3. Dati

| Tecnologia | Versione | Ruolo | Stato |
|---|---|---|---|
| psycopg | 3.x | driver Postgres, con pool | `[PROPOSTA]` |
| Postgres | 16 | profilo `postgres`, estensioni PostGIS | deciso in D-07 |
| PostGIS | 3.x | `geography(Polygon,4326)`, query spaziali | deciso in D-07 |
| SQLite | — | profilo `sqlite` per test senza Docker | deciso in D-07 |

Regola di isolamento: i driver si importano solo da `db/` e `repositories/` (REQ-PER-04, verificato via AST).

## 4. Rete in uscita

| Tecnologia | Versione | Ruolo | Dove |
|---|---|---|---|
| httpx | 0.27 | client HTTP sincrono con timeout esplicito | solo `services/connectors/` e `services/agents/mobility/` |
| feedparser | 6.x | parsing RSS con encoding dichiarato dal feed | `services/connectors/rss/` |
| xml.etree | stdlib | piano di riserva del parser RSS | `services/connectors/rss/` |

Motivo di httpx: timeout, `ETag` e `If-None-Match` in una sola API. Alternative scartate: `requests`, scartata perche' la variante asincrona manca e il pooling e' meno controllabile; `aiohttp`, scartata perche' il backend non ha bisogno di concorrenza nel percorso della demo.

Motivo di feedparser: il feed del Mattino e' in ISO-8859-1 e le date sono italiane; feedparser legge l'encoding dal feed, il resto lo fa il nostro parser. Alternativa scartata: parsing a mano con `xml.etree`, tenuto come riserva.

## 5. Test e qualita'

| Tecnologia | Versione | Ruolo |
|---|---|---|
| pytest | 8.x | suite unit, integration, e2e |
| pytest-asyncio | 0.24 | test dello stream SSE |
| pytest-cov | 5.x | copertura per area di [TRACEABILITY.md](TRACEABILITY.md) |
| testcontainers | 4.x | Postgres reale nei test dei repository (D-13) |
| ruff | 0.7 | lint e import order, unico strumento |

Marker della suite: `network` disabilitato per default (NFR-08), `db` attivo solo con Docker.

## 6. Fuori dallo stack, per scelta

| Tecnologia | Perche' non c'e' |
|---|---|
| framework di orchestrazione di agenti | le regole sono funzioni pure; il grafo, se serve al racconto, e' una shell sottile (D-12) |
| ORM | lo schema e' SQL esplicito in `database/migrations/`, nessuna mappatura implicita |
| Redis, Celery, code | fuori dagli obiettivi; lo scheduler e' un cron esterno dichiarato in `infra/` |
| autenticazione e sessioni | fuori dagli obiettivi del backend |
| WebSocket | non serve: il real-time e' polling con `ETag`, lo stream e' SSE (D-18) |
| Docker Compose per la demo | il profilo `memory` non richiede servizi |

## 7. Versioni e riproducibilita'

- Le versioni si pinnano in `pyproject.toml` con l'operatore `==` per gli strumenti di sviluppo e `~=` per le librerie.
- `pip freeze` non e' la sorgente: `pyproject.toml` lo e'.
- Ogni aggiornamento di major passa da una voce in [DECISIONS.md](DECISIONS.md).
- `contract_version` in [CONTRACTS.md](CONTRACTS.md) non segue la versione delle dipendenze: cambia solo quando cambia un contratto.
