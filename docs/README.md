# Documentazione

Indice dei documenti del progetto Napoli Agentic City. Ogni unita' ha la propria documentazione nella propria cartella. Questo file contiene solo riferimenti, non contenuto.

## Backend

Cartella: `backend/docs/`

| Documento | Contenuto |
|---|---|
| [REQUIREMENTS.md](../backend/docs/REQUIREMENTS.md) | requisiti funzionali e non funzionali con criterio di accettazione |
| [ARCHITECTURE.md](../backend/docs/ARCHITECTURE.md) | componenti, dipendenze, flusso, punti di innesto |
| [CONTRACTS.md](../backend/docs/CONTRACTS.md) | strutture condivise con il frontend, regole di collocazione |
| [API.md](../backend/docs/API.md) | contratto HTTP: endpoint, payload, envelope, eventi SSE, CORS |
| [STACK.md](../backend/docs/STACK.md) | tecnologie del backend, versioni, alternative scartate |
| [OPERATIONS.md](../backend/docs/OPERATIONS.md) | configurazione, errori, degradazione, comandi |
| [TRACEABILITY.md](../backend/docs/TRACEABILITY.md) | matrice requisito, componente, test |
| [DECISIONS.md](../backend/docs/DECISIONS.md) | decisioni tecniche con alternative scartate |
| [DEMO.md](../backend/docs/DEMO.md) | copione della demo |
| [METRICS.md](../backend/docs/METRICS.md) | metriche dichiarabili e metodo di misura |
| [AGENTS.md](../backend/docs/AGENTS.md) | agenti: dominio, input, output, rifiuti |
| [ORCHESTRATOR.md](../backend/docs/ORCHESTRATOR.md) | regole, priorita', reasoning log |
| [CONNECTORS.md](../backend/docs/CONNECTORS.md) | connettori: fonte, frequenza, fallback |

## Database

Cartella: `database/docs/`

| Documento | Contenuto |
|---|---|
| [SCHEMA.md](../database/docs/SCHEMA.md) | tabelle, colonne, tipi, chiavi, indici, vincoli, derivazioni |

## Frontend

Cartella: `frontend/docs/`

| Documento | Contenuto |
|---|---|
| [README.md](../frontend/docs/README.md) | indice e ordine di lettura per chi implementa |
| [STACK.md](../frontend/docs/STACK.md) | tecnologie del frontend, versioni, alternative scartate |
| [SCREENS.md](../frontend/docs/SCREENS.md) | rotte, schermate, dati usati, mappa con il copione della demo |
| [DESIGN.md](../frontend/docs/DESIGN.md) | direzione visiva, token, componenti, accessibilita' |
| [UI-REQUIREMENTS.md](../frontend/docs/UI-REQUIREMENTS.md) | requisiti di interfaccia con criterio di accettazione |
| [API-CLIENT.md](../frontend/docs/API-CLIENT.md) | tipi TypeScript, client HTTP, stream SSE, resa degli errori |

Il frontend parte dai documenti prodotti dal backend: [API.md](../backend/docs/API.md), [CONTRACTS.md](../backend/docs/CONTRACTS.md), [OPERATIONS.md](../backend/docs/OPERATIONS.md) sezione 3. Sono marcati `[PIANIFICATO]`: descrivono il contratto concordato, non codice gia' esistente.

## Documentazione generale

Non ancora redatta. Va prodotta quando esistono la documentazione di backend, quella di database e quella di frontend. Conterra' solo cio' che riguarda il sistema nel suo insieme: visione, scenario, flusso end-to-end, metriche aggregate, stato di avanzamento.

## Fonti esterne al repository

| Documento | Percorso |
|---|---|
| Traccia congelata | `ricerche/scelte implementative/01_traccia_scelte_prese.md` |
| Contratto dei feed RSS | `ricerche/scelte implementative/03_contratto_dati_definitivi.md` |
| Guida operativa a step | `guide/guida1/` |
| Checkpoint di sessione | `stati/` |
| Simulazioni dichiarate | `assumptions.md` alla radice del repository |

## Regola di collocazione

Un documento sta nella cartella dell'unita' che descrive. I contratti condivisi tra due unita' vivono nella cartella dell'unita' che li produce e sono citati dall'unita' che li consuma. I contratti del sistema sono prodotti dal backend e consumati dal frontend.

Un documento generale si scrive solo quando le unita' hanno la propria documentazione. Scriverlo prima produce una sintesi di intenzioni, non di fatti.

## Manutenzione

- Un documento si aggiorna nello stesso commit del codice che descrive.
- Un documento che descrive codice non ancora scritto si marca con `[PIANIFICATO]` nella prima riga.
- I riferimenti incrociati usano path relativi con forward slash.
- Nessun segreto, nessun token, nessun path personale assoluto.
