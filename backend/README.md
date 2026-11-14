# Backend

Backend del sistema Napoli Agentic City: connettori, agenti specializzati, orchestratore.

## Avvio

```
pip install [DA COMPLETARE]
uvicorn [DA COMPLETARE]
```

## Test

- Unit: [DA COMPLETARE]
- Integration: [DA COMPLETARE]
- Scenarios: [DA COMPLETARE]

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

- [AGENTS.md](docs/AGENTS.md)
- [ORCHESTRATOR.md](docs/ORCHESTRATOR.md)
- [CONNECTORS.md](docs/CONNECTORS.md)
- [Schemi condivisi](../../shared/schemas/)