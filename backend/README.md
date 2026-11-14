# Backend

Backend del sistema Napoli Agentic City: connettori, agenti specializzati, orchestratore.

## Avvio

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python -m app.cli config validate
python -m app.cli demo --scenario bagnoli --report
uvicorn app.main:app --app-dir backend --reload --port 8000
```

## Test

- Suite completa (offline di default con `--disable-socket`): `.venv/bin/pytest -v`
- Unit & Contracts: `.venv/bin/pytest tests/contracts tests/unit tests/architecture -v`
- Integration & DB: `.venv/bin/pytest tests/integration tests/db -v`
- E2E & Scenarios: `.venv/bin/pytest tests/e2e -v`
- Lint & Formatting: `.venv/bin/ruff check backend shared tests`

## Struttura

- app/api/v1/: endpoint HTTP versionati.
- app/api/middleware/: middleware trasversali.
- app/services/orchestrator/: regole di trigger, conflitti, piano.
- app/services/agents/: agenti mobilita, crowding, context.
- app/services/connectors/: ingestion GTFS, RSS, meteo, eventi, occupazione.
- app/services/validation/: validazione schemi e contratti.
- app/domain/models/: modelli di dominio.
- app/repositories/: accesso al DB.
- app/db/migrations/: migrazioni backend.
- app/utils/: utilita condivise.
- docs/: documentazione backend.

## Documenti

- [REQUIREMENTS.md](docs/REQUIREMENTS.md) — requisiti con criterio di accettazione
- [ARCHITECTURE.md](docs/ARCHITECTURE.md) — componenti, dipendenze, punti di innesto
- [CONTRACTS.md](docs/CONTRACTS.md) — contratti condivisi con il frontend
- [API.md](docs/API.md) — contratto HTTP, payload, eventi SSE, CORS
- [STACK.md](docs/STACK.md) — tecnologie, versioni, alternative scartate
- [OPERATIONS.md](docs/OPERATIONS.md) — configurazione, errori, degradazione
- [TRACEABILITY.md](docs/TRACEABILITY.md) — matrice requisito, componente, test
- [DECISIONS.md](docs/DECISIONS.md) — decisioni tecniche
- [DEMO.md](docs/DEMO.md) — copione della demo
- [METRICS.md](docs/METRICS.md) — metriche e metodo di misura
- [AGENTS.md](docs/AGENTS.md) — agenti
- [ORCHESTRATOR.md](docs/ORCHESTRATOR.md) — regole e priorita'
- [CONNECTORS.md](docs/CONNECTORS.md) — connettori
- [Schemi condivisi](../shared/schemas/)
- [Documentazione frontend](../frontend/docs/README.md) — cosa consuma da questa API