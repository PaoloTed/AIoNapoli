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

- [REQUIREMENTS.md](docs/REQUIREMENTS.md) — requisiti con criterio di accettazione
- [ARCHITECTURE.md](docs/ARCHITECTURE.md) — componenti, dipendenze, punti di innesto
- [CONTRACTS.md](docs/CONTRACTS.md) — contratti condivisi con il frontend
- [OPERATIONS.md](docs/OPERATIONS.md) — configurazione, errori, degradazione
- [TRACEABILITY.md](docs/TRACEABILITY.md) — matrice requisito, componente, test
- [DECISIONS.md](docs/DECISIONS.md) — decisioni tecniche
- [DEMO.md](docs/DEMO.md) — copione della demo
- [METRICS.md](docs/METRICS.md) — metriche e metodo di misura
- [AGENTS.md](docs/AGENTS.md) — agenti
- [ORCHESTRATOR.md](docs/ORCHESTRATOR.md) — regole e priorita'
- [CONNECTORS.md](docs/CONNECTORS.md) — connettori
- [Schemi condivisi](../shared/schemas/)