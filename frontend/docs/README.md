[PIANIFICATO]

# Documentazione frontend

Indice dei documenti del frontend. Ogni documento dice cosa costruire, non come e' gia' costruito: il codice del frontend non esiste ancora.

Il frontend consuma i contratti prodotti dal backend. Questo implica una regola di lettura: **il frontend non definisce i propri dati**. Se un campo serve e non c'e', si apre una voce in [DECISIONS.md](../../backend/docs/DECISIONS.md), non si inventa un campo nel client.

## Documenti

| Documento | Contenuto |
|---|---|
| [STACK.md](STACK.md) | tecnologie, versioni, alternative scartate |
| [SCREENS.md](SCREENS.md) | rotte, schermate, dati usati da ogni schermata, mappa con il copione della demo |
| [DESIGN.md](DESIGN.md) | direzione visiva, token, inventario dei componenti, accessibilita' |
| [UI-REQUIREMENTS.md](UI-REQUIREMENTS.md) | requisiti con identificatore e criterio di accettazione |
| [API-CLIENT.md](API-CLIENT.md) | tipi TypeScript, client HTTP, stream SSE, macchina a stati, mappatura degli errori |

## Sorgenti prodotte dal backend

| Documento | Cosa fornisce |
|---|---|
| [CONTRACTS.md](../../backend/docs/CONTRACTS.md) | Finding, Decision, PlanItem, ReasoningStep, Refusal, RelevanceScore, Narrative |
| [API.md](../../backend/docs/API.md) | endpoint, payload completi, envelope, eventi SSE, CORS |
| [OPERATIONS.md](../../backend/docs/OPERATIONS.md) sezione 3 | tassonomia degli errori e forma `application/problem+json` |
| [REQUIREMENTS.md](../../backend/docs/REQUIREMENTS.md) sezione 2.5 | requisiti degli endpoint |
| [DEMO.md](../../backend/docs/DEMO.md) | copione dei 90 secondi |
| [METRICS.md](../../backend/docs/METRICS.md) | metriche da mostrare e come si misurano |

## Regole di scrittura

- Un documento che descrive codice non ancora scritto si marca con `[PIANIFICATO]` nella prima riga.
- Ogni requisito ha un identificatore `FE-REQ-NN` e un criterio verificabile a occhio o con un test.
- Un requisito dell'interfaccia che nasce da un requisito del backend lo cita: `REQ-API-06`, `REQ-ORC-11`.
- Nessun segreto, nessun token Mapbox nel repository: la chiave sta in `NEXT_PUBLIC_MAPBOX_TOKEN`, valorizzata in locale.
- I riferimenti incrociati usano path relativi con forward slash.

## Ordine di lettura per chi implementa

1. [API-CLIENT.md](API-CLIENT.md) per i tipi e i dati disponibili.
2. [SCREENS.md](SCREENS.md) per cosa mostrare e dove.
3. [DESIGN.md](DESIGN.md) per come si vede.
4. [UI-REQUIREMENTS.md](UI-REQUIREMENTS.md) per sapere quando una schermata e' finita.

## Struttura dei file

```
frontend/
  app/
    layout.tsx              shell comune: intestazione, stato sistema, navigazione
    page.tsx                scelta del punto di vista, tre card
    operator/page.tsx       sala operativa
    tourist/page.tsx        vista turista, bilingue
    citizen/page.tsx        vista cittadino
  components/
    FindingCard.tsx         finding con provenienza e severita'
    ProvenanceChip.tsx      reale / simulato / non disponibile
    RuleTimeline.tsx        passi SSE
    DecisionHeader.tsx      trigger, conflitto, decision_id, ripeti
    PlanColumn.tsx          item di un target, ordinati
    RelevanceBar.tsx        punteggio e contributi
    MapPanel.tsx            mezzi, geo-fence, zona
    ChatPanel.tsx           messaggio principale e alternativa
    SystemStatusBar.tsx     live / degraded / offline, versione contratto
    states/                 skeleton, empty, error, degraded
  lib/
    contracts.ts            tipi dei contratti, unica sorgente lato client
    api.ts                  fetch, errori, controllo della versione
    i18n.ts                 dizionario it/en tipizzato
    format.ts               date in Europe/Rome, percentuali, testi di severita'
  hooks/
    useScenario.ts          GET scenario con retry e backoff
    useDecision.ts          POST decision
    useDecisionStream.ts    EventSource e passi accumulati
  docs/                     questi documenti
```

Un componente non fa fetch: riceve dati tipizzati. Le chiamate stanno nei tre hook.
