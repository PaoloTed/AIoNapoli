[PIANIFICATO]

# Requisiti di interfaccia

Requisiti del frontend con identificatore stabile e criterio di accettazione verificabile. Un requisito senza criterio non e' un requisito.

Ogni requisito che nasce da un requisito del backend lo cita. La colonna "Traccia" usa gli identificatori di [REQUIREMENTS.md](../../backend/docs/REQUIREMENTS.md).

## 1. Contratti

| ID | Requisito | Criterio di accettazione | Traccia |
|---|---|---|---|
| FE-REQ-01 | I tipi del client sono una traduzione dei contratti, non una loro variante | `lib/contracts.ts` contiene esattamente 9 campi in `Finding` e 6 in `Decision`; un test confronta le chiavi con una costante attesa | REQ-CONTR-01, REQ-CONTR-02 |
| FE-REQ-02 | Il client non aggiunge campi alle strutture ricevute | nessun `...spread` che introduca chiavi non presenti nel contratto; la validazione zod fallisce su chiavi sconosciute | REQ-CONTR-01 |
| FE-REQ-03 | `content` si legge tramite accessor, con `undefined` quando il campo manca | test: finding senza `content.density` produce `undefined`, non `0` | CONTRACTS.md sezione 5 |
| FE-REQ-04 | `contract_version` e' confrontata a ogni risposta | versione diversa produce il banner `contract_mismatch` e un test che lo verifica | CONTRACTS.md voce C10 |
| FE-REQ-05 | Il client non ricalcola punteggi, priorita' o testi | nessuna funzione nel frontend che sommi contributi o riordini item per conto proprio | REQ-REL-01 |

## 2. Dati e stato

| ID | Requisito | Criterio di accettazione | Traccia |
|---|---|---|---|
| FE-REQ-06 | Ogni schermata mostra lo scenario in tre tempi: dati, decisione, stream | Playwright: mappa e card visibili prima che la decisione arrivi | API.md sezione 4 |
| FE-REQ-07 | Un finding mancante produce uno stato `partial`, non un errore | test con `findings` lungo 2: due card piene e una "dato non disponibile" | REQ-AGT-01 |
| FE-REQ-08 | `conflict.detected=false` produce il banner `no_rules` con il piano di monitoraggio | test con lo scenario senza regole: nessun elemento di errore a schermo | REQ-ORC-13 |
| FE-REQ-09 | `is_simulated=true` e' sempre visibile come chip e bordo tratteggiato | ispezione visiva su ogni card; test sul componente `ProvenanceChip` | REQ-DEG-05 |
| FE-REQ-10 | Nessuna informazione e' dedotta quando il campo manca | test: finding senza `zone_id` non produce un poligono evidenziato | CONTRACTS.md sezione 1.2 |
| FE-REQ-11 | Ogni richiesta ha uno stato di caricamento con la forma del contenuto finale | scheletri presenti su tutte e tre le rotte; nessuno spinner a schermo intero | API.md |
| FE-REQ-12 | La mappa e' opzionale: senza token l'interfaccia resta usabile | build senza `NEXT_PUBLIC_MAPBOX_TOKEN`: stato vuoto dichiarato, resto funzionante | SCREENS.md sezione 2 |

## 3. Stream

| ID | Requisito | Criterio di accettazione | Traccia |
|---|---|---|---|
| FE-REQ-13 | Lo stream si consuma con `EventSource` sulla rotta dichiarata | test: apertura su `/api/v1/scenario/{id}/stream`, nessun header custom | REQ-API-06 |
| FE-REQ-14 | I passi mostrati coincidono, in ordine, con `decision.reasoning_log` | test: sequenza degli eventi uguale alla sequenza dei passi per `rule_applied` e `outcome` | REQ-API-06 |
| FE-REQ-15 | Le regole non scattate sono mostrate con il motivo | `fired=false` produce una riga visibile con `reason` | REQ-ORC-06 |
| FE-REQ-16 | La riconnessione azzera la timeline prima di riaprire | test: una disconnessione non duplica i passi | API.md sezione 5.4 |
| FE-REQ-17 | Stream non disponibile produce `degraded`, non un errore | la decisione gia' ottenuta resta a schermo e la timeline mostra la nota | API.md sezione 5.4 |

## 4. Errori

| ID | Requisito | Criterio di accettazione | Traccia |
|---|---|---|---|
| FE-REQ-18 | Ogni `code` di problem+json ha una resa dichiarata | tabella in [API-CLIENT.md](API-CLIENT.md) sezione 5 completa per tutti i codici di OPERATIONS.md sezione 3.2 | NFR-06 |
| FE-REQ-19 | Nessun errore mostra uno stack trace o un messaggio grezzo del server | test: risposta 500 fittizia mostra solo `code` e `detail` | OPERATIONS.md sezione 3.3 |
| FE-REQ-20 | Un rifiuto di agente e' mostrato come esito, non come guasto | `agent_refusal` produce la card "dato non disponibile" con `reason_code` | REQ-API-08 |

## 5. Contenuti per destinatario

| ID | Requisito | Criterio di accettazione | Traccia |
|---|---|---|---|
| FE-REQ-21 | `reasoning_log` e `rationale` non compaiono su `/tourist` e `/citizen` | test: nessun nodo con testo del log nelle due rotte | REQ-ORC-11 |
| FE-REQ-22 | L'ordine degli item segue `relevance.targets[target].order` | test: cambiando i pesi in `relevance.yaml` cambia l'ordine a schermo senza modifiche al frontend | REQ-REL-04 |
| FE-REQ-23 | Se `narrative.items` e' vuota si mostra `PlanItem.action` | test con `mode=off`: l'azione e' visibile, il testo narrativo no | REQ-DEG-02 |
| FE-REQ-24 | Il turista vede il testo in italiano e in inglese | selettore lingua funzionante, `lang` corretto sul blocco | CONTRACTS.md sezione 7.1 |
| FE-REQ-25 | Il turista vede al massimo tre azioni | test: piano con cinque item per il turista produce tre card e una riga "altre N" | SCREENS.md sezione 4 |

## 6. Determinismo e demo

| ID | Requisito | Criterio di accettazione | Traccia |
|---|---|---|---|
| FE-REQ-26 | Il pulsante "ripeti" confronta i due `decision_id` e mostra l'esito | test: due chiamate identiche mostrano `same` con il valore | REQ-ORC-12 |
| FE-REQ-27 | Ogni passo del copione ha il suo componente visibile entro il tempo dichiarato | prova cronometrata dei 90 secondi, esito registrato in DEMO.md | NFR-10 |
| FE-REQ-28 | Le metriche mostrate sono solo quelle calcolate da un campo esistente | nessun numero a schermo senza un campo che lo produca | METRICS.md sezione 3 |

## 7. Accessibilita' e qualita'

| ID | Requisito | Criterio di accettazione | Traccia |
|---|---|---|---|
| FE-REQ-29 | Contrasto, focus e navigazione da tastiera rispettano DESIGN.md sezione 4 | audit con axe su tre rotte, zero violazioni gravi | — |
| FE-REQ-30 | La timeline e' annunciata senza rubare il focus | `aria-live="polite"` presente, test con screen reader o ispezione dell'albero | — |
| FE-REQ-31 | Nessun segreto nel repository | ricerca di `pk.` e `sk.` nel codice versionato: zero risultati | NFR-07 |
| FE-REQ-32 | Il frontend non chiama il database ne' le fonti esterne | ispezione degli import e delle fetch: solo `NEXT_PUBLIC_API_BASE_URL` | ARCHITECTURE.md sezione 9 |

## 8. Cosa non e' un requisito

- Fedelta' pixel-perfect a un mockup che non esiste.
- Supporto a browser senza `EventSource`.
- Tema scuro sul turista, o tema chiaro sull'operatore: il registro e' fissato in DESIGN.md.
- Internazionalizzazione oltre italiano e inglese.
- Modifica delle soglie dall'interfaccia.
