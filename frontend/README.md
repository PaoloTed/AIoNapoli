# Frontend

Interfaccia Next.js per operatori, turisti e cittadini. Stack: Next.js con Mapbox GL JS per la mappa e componenti chat per gli output.

## Documentazione

La documentazione e' in [docs/](docs/README.md). Ordine di lettura per chi implementa:

| Documento | Cosa fornisce |
|---|---|
| [API-CLIENT.md](docs/API-CLIENT.md) | tipi TypeScript, client HTTP, stream SSE, resa degli errori |
| [SCREENS.md](docs/SCREENS.md) | rotte, schermate, dati usati, mappa con il copione della demo |
| [DESIGN.md](docs/DESIGN.md) | direzione visiva, token, componenti, accessibilita' |
| [UI-REQUIREMENTS.md](docs/UI-REQUIREMENTS.md) | requisiti di interfaccia con criterio di accettazione |
| [STACK.md](docs/STACK.md) | tecnologie, versioni, alternative scartate |

I contratti consumati sono prodotti dal backend:

| Documento | Cosa fornisce |
|---|---|
| [CONTRACTS.md](../backend/docs/CONTRACTS.md) | Finding, Decision, PlanItem, ReasoningStep, Refusal, RelevanceScore, Narrative |
| [API.md](../backend/docs/API.md) | endpoint, payload completi, envelope, eventi SSE, CORS |
| [OPERATIONS.md](../backend/docs/OPERATIONS.md) sezione 3 | tassonomia degli errori e forma `application/problem+json` |

Il frontend non definisce i propri dati: se un campo serve e non c'e', si apre una voce in [DECISIONS.md](../backend/docs/DECISIONS.md), non si inventa un campo nel client.
