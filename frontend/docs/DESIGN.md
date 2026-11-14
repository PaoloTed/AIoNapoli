[PIANIFICATO]

# Design

Direzione visiva, token, inventario dei componenti, accessibilita'. Il design serve a rendere leggibile una cosa sola: **da dove viene ogni dato e quanto e' affidabile**. Il resto e' contenuto.

## 1. Direzione

Due registri, un solo sistema.

| Registro | Dove | Perche' |
|---|---|---|
| sala operativa, scura | `/operator` | lettura in ambiente chiuso, molti dati, server su schermo grande |
| guida tascabile, chiara | `/tourist`, `/citizen` | lettura al sole, una informazione per volta, pollice |

Nessun gradiente decorativo, nessuna illustrazione, nessuna animazione che non comunichi un passaggio di stato. Il progetto vende rigore: l'interfaccia lo mostra con la tipografia e il bianco, non con gli effetti.

## 2. Token

### 2.1 Colori

| Token | Scuro (operator) | Chiaro (tourist, citizen) | Uso |
|---|---|---|---|
| `--bg` | `#0B1016` | `#FAFAF8` | fondo |
| `--surface` | `#131A23` | `#FFFFFF` | card e pannelli |
| `--border` | `#22303D` | `#E2E0DA` | bordi sottili, 1 px |
| `--text` | `#E8EDF2` | `#141A20` | testo primario |
| `--text-muted` | `#93A2B1` | `#5C6874` | etichette, timestamp |
| `--accent` | `#4FB3D9` | `#0B6E8F` | elemento attivo, link, focus |
| `--accent-soft` | `rgba(79,179,217,0.14)` | `rgba(11,110,143,0.10)` | fondo dell'elemento attivo |

Il colore non distingue mai due cose da sole: sempre accompagnato da testo o da una forma.

### 2.2 Severita'

| Severita' | Colore | Forma |
|---|---|---|
| `low` | `#5B8C6E` | punto pieno piccolo |
| `medium` | `#C79A3A` | punto pieno |
| `high` | `#D06A32` | triangolo |
| `critical` | `#C2382F` | triangolo pieno |

La forma cambia con la severita' perche' la demo si vede anche da lontano e su un proiettore i rossi si confondono.

### 2.3 Dati simulati

Il linguaggio visivo della provenienza e' la parte piu' importante del design.

| Stato | Bordo della card | Chip | Icona |
|---|---|---|---|
| dato reale | `1px solid var(--border)` | nessuno | punto pieno verde |
| dato simulato | `1px dashed var(--border)` | `SIMULATO` in maiuscoletto, 11 px | punto vuoto |
| dato mancante | `1px dashed` piu' opacita' 0.6 | `NON DISPONIBILE` | trattino |

`is_simulated=true` non e' un errore e non si colora di rosso. E' una dichiarazione: bordo tratteggiato e chip. Chi guarda sa cosa sta vedendo senza leggere una nota a pie' di pagina.

### 2.4 Tipografia

| Ruolo | Font | Peso | Dimensione |
|---|---|---|---|
| titoli | Inter | 600 | 20 / 24 / 32 |
| corpo | Inter | 400 | 15 |
| etichette e metadati | Inter | 500, maiuscoletto 11 px, lettere distanziate | 11 |
| dati tecnici (`decision_id`, `finding_ref`, `zone_id`) | ui-monospace | 400 | 13 |

I valori tecnici stanno in monospace: si copiano, si confrontano, si leggono ad alta voce in demo.

### 2.5 Spazio, raggio, movimento

| Token | Valore |
|---|---|
| griglia | 4 px, multipli usati: 8, 12, 16, 24, 32, 48 |
| raggio | 10 px sulle card, 6 px su chip e pulsanti |
| elevazione | una sola ombra, solo sulle card in registro chiaro |
| transizione | 120 ms per colore e opacita', 200 ms per l'ingresso di un passo della timeline |
| reduced motion | nessuna animazione di ingresso, solo il cambio di stato |

## 3. Inventario dei componenti

| Componente | Responsabilita' | Dati |
|---|---|---|
| `FindingCard` | un finding: agente, tipo, severita', confidenza, fonte, ora | `Finding`, `finding_ref` |
| `SeverityBadge` | severita' con forma e colore | `severity` |
| `ProvenanceChip` | reale / simulato / non disponibile | `is_simulated` |
| `RuleTimeline` | passi SSE in ordine, ciascuno con esito e motivo | eventi SSE |
| `RuleRow` | una regola: id, agenti, `fired`, motivo | `rule_evaluated` |
| `DecisionHeader` | trigger, conflitto, `decision_id`, azione ripeti | `decision`, `decision_id` |
| `PlanColumn` | item di un target, ordinati | `plan`, `relevance.targets[target].order` |
| `PlanCard` | azione e motivazione, testo narrativo se c'e' | `PlanItem`, `Narrative` |
| `RelevanceBar` | punteggio con contributi come segmenti | `ScoredItem` |
| `ContributionList` | feature, valore, peso, contributo | `Contribution[]` |
| `ReasoningList` | passi del log, solo operatore | `ReasoningStep[]` |
| `MapPanel` | mezzi, geo-fence, zona evidenziata | `vehicle_positions`, `zone_id` |
| `ChatPanel` | messaggio principale e alternativa | `Narrative`, `PlanItem` |
| `SystemStatusBar` | `live` / `degraded` / `offline`, versione contratto | stato client |
| `EmptyState` | stato vuoto con motivo e azione | `code` |
| `Skeleton` | forma del contenuto in caricamento | nessuno |
| `ErrorBanner` | `code`, `detail`, pulsante riprova | problem+json |

Regola: un componente riceve dati tipizzati e non fa fetch. Il fetch sta in `lib/api.ts` e negli hook.

## 4. Accessibilita'

| Requisito | Soglia |
|---|---|
| contrasto del testo | almeno 4.5:1, 3:1 per testo grande |
| focus visibile | anello `2px` colore `--accent`, offset 2 px, mai rimosso |
| tastiera | ogni azione raggiungibile, ordine coerente con il visivo |
| stream | la timeline usa `aria-live="polite"` e non ruba il focus |
| significato | severita' e simulazione non comunicate solo dal colore |
| motion | rispetta `prefers-reduced-motion` |
| zoom | layout utilizzabile a 200% senza perdita di contenuto |
| lingua | `lang="it"` di default, `lang="en"` sul blocco tradotto |

La mappa non e' l'unico modo di leggere i dati: ogni informazione presente sulla mappa compare anche come testo in un pannello.

## 5. Responsive

| Schermata | Priorita' | Sotto 768 px |
|---|---|---|
| `/operator` | desktop 1280+, ottimizzata per proiettore | colonna singola, mappa ridotta a 240 px, piano a tab |
| `/tourist` | mobile 390+ | una colonna, messaggio principale sopra la mappa |
| `/citizen` | mobile 390+ | una colonna, nessuna tabella |

Nessuna schermata usa tabelle larghe: i dati tabellari sono liste di card.
