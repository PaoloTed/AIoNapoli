[PIANIFICATO]

# Requisiti

Requisiti del backend di Napoli Agentic City. Ogni requisito ha un identificatore stabile, un criterio di accettazione verificabile con un comando o un test, e una traccia verso il componente che lo realizza.

Un requisito senza criterio di accettazione non e' un requisito. Se il criterio non e' esprimibile, il requisito e' un obiettivo e va in [DECISIONS.md](DECISIONS.md).

## 1. Ambito

Il backend fa tre cose:

1. porta dati esterni eterogenei in strutture normalizzate e tracciabili,
2. li interpreta con agenti deterministici che producono finding o rifiuti motivati,
3. produce una decisione riproducibile con piano declinato su tre destinatari.

Il backend non esegue azioni sulla citta'. Propone.

## 2. Requisiti funzionali

### 2.1 Contratti

| ID | Requisito | Criterio di accettazione |
|---|---|---|
| REQ-CONTR-01 | Il finding ha esattamente i nove campi del contratto | test di schema: insieme dei campi uguale all'atteso |
| REQ-CONTR-02 | La decision ha esattamente i sei campi del contratto | test di schema: insieme dei campi uguale all'atteso |
| REQ-CONTR-03 | `content` del finding e' un dizionario libero | un finding con campi extra in `content` valida |
| REQ-CONTR-04 | Un finding con agente e type incoerenti e' rifiutato | `agent=mobility` con `type=density_alert` produce errore di validazione |
| REQ-CONTR-05 | `severity` accetta solo `low`, `medium`, `high`, `critical` | valore `urgent` produce errore |
| REQ-CONTR-06 | `rule_id` accetta solo i quattro identificatori dichiarati | `R5_custom` produce errore |
| REQ-CONTR-07 | `target` accetta solo `operator`, `tourist`, `citizen` | `admin` produce errore |
| REQ-CONTR-08 | Ogni finding ha un riferimento stabile e ricalcolabile | `finding_ref` identico su due esecuzioni dello stesso input |

### 2.2 Agenti

| ID | Requisito | Criterio di accettazione |
|---|---|---|
| REQ-AGT-01 | Ogni agente restituisce un finding oppure un rifiuto motivato | test: input incompleto produce `Refusal` con `reason_code` |
| REQ-AGT-02 | L'Agente Mobilita rifiuta senza GTFS per la linea richiesta | test: snapshot senza route produce rifiuto `missing_gtfs` |
| REQ-AGT-03 | L'Agente Mobilita rifiuta se origine o destinazione non sono mappate su una fermata | test: punto non mappato produce rifiuto `unmapped_point` |
| REQ-AGT-04 | L'Agente Affollamento rifiuta se occupancy e' assente e non simulata | test: snapshot vuoto produce rifiuto `missing_occupancy` |
| REQ-AGT-05 | L'Agente Affollamento rifiuta se l'evento non ha geo-fence | test: evento senza geometria produce rifiuto `missing_geofence` |
| REQ-AGT-06 | L'Agente Contesto rifiuta se il meteo non ha livello di allerta | test: snapshot senza `alert_level` produce rifiuto |
| REQ-AGT-07 | Nessun agente importa da un altro agente | test di architettura via AST |
| REQ-AGT-08 | Ogni agente legge solo dai repository, mai da HTTP diretto tranne Mobilita verso OTP | test di architettura via AST |

### 2.3 Orchestratore

| ID | Requisito | Criterio di accettazione |
|---|---|---|
| REQ-ORC-01 | R1 scatta quando `mobility.severity` e' almeno `high` e `density > 0.85` | test positivo e negativo |
| REQ-ORC-02 | R2 rileva conflitto quando la zona del percorso e' la stessa zona satura | test con due finding sulla stessa zona |
| REQ-ORC-03 | R3 riduce la capacita' stimata quando c'e' pioggia intensa e `density > 0.7` | test positivo e negativo |
| REQ-ORC-04 | R4 valuta alternative quando l'affluenza attesa supera soglia e mobility segnala saturazione | test positivo e negativo |
| REQ-ORC-05 | Nessuna regola solleva eccezioni su finding parziali | test con finding privi dei campi letti: `fired=false` e motivo |
| REQ-ORC-06 | Una regola non scattata registra il motivo nel reasoning log | log contiene la regola valutata e il campo assente |
| REQ-ORC-07 | Le soglie vivono in configurazione, non nel codice | modifica di `rules.yaml` cambia l'esito senza toccare il codice |
| REQ-ORC-08 | Il conflitto si risolve con le priorita' P1, P2, P3 | test: crowding prevale su mobility, mobility prevale su context |
| REQ-ORC-09 | Il reasoning log ha passi contigui da 1 e non supera cinque passi sullo scenario demo | test sulla lunghezza e sulla numerazione |
| REQ-ORC-10 | Il piano contiene almeno un item per ciascuno dei tre target | test di presenza dei tre target |
| REQ-ORC-11 | Nessun item del piano per turista o cittadino contiene il reasoning log | test sul contenuto |
| REQ-ORC-12 | Lo stesso input produce la stessa decisione | due chiamate producono lo stesso `decision_id` |
| REQ-ORC-13 | Il caso "nessuna regola scatta" produce una decisione valida, non un errore | test: `conflict.detected=false`, piano con item di monitoraggio |

### 2.4 Rilevanza per target

| ID | Requisito | Criterio di accettazione |
|---|---|---|
| REQ-REL-01 | Ogni item del piano ha un punteggio per ciascun target | test: tre punteggi per item |
| REQ-REL-02 | Il punteggio e' in 0..1 e deterministico | test: stessa chiamata due volte, stesso valore |
| REQ-REL-03 | I pesi sono in `relevance.yaml` | modifica di un peso cambia l'ordine senza toccare il codice |
| REQ-REL-04 | I tre target ordinano gli stessi item in ordini diversi sullo scenario demo | test di disuguaglianza degli ordinamenti |
| REQ-REL-05 | Il punteggio non entra nello schema della decisione | test di schema: nessun campo `relevance` in `Decision` |
| REQ-REL-06 | Ogni punteggio e' scomponibile nei contributi per feature | test: somma dei contributi uguale al punteggio |

### 2.5 API

| ID | Requisito | Criterio di accettazione |
|---|---|---|
| REQ-API-01 | `POST /api/v1/finding/{agent}` accetta un finding e restituisce 200 con il finding validato | test con i tre mock |
| REQ-API-02 | Un finding non conforme restituisce 422 con il campo responsabile | test: `density=1.4` produce 422 con `field=density` |
| REQ-API-03 | Un finding con agente diverso dall'endpoint restituisce 422 con motivo | test: crowding su endpoint mobility |
| REQ-API-04 | `POST /api/v1/decision` restituisce una `Decision` valida partendo dai finding disponibili | test end-to-end sui mock |
| REQ-API-05 | Un input malformato non produce mai 500 | test su payload arbitrari |
| REQ-API-06 | `GET /api/v1/scenario/{id}/stream` emette gli eventi della trace in ordine | test SSE: la sequenza degli eventi coincide con il reasoning log |
| REQ-API-07 | Nessun endpoint contiene logica di dominio | test di architettura via AST |
| REQ-API-08 | Il rifiuto di un agente e' un esito previsto, non un errore interno | test: rifiuto produce 200 con oggetto `Refusal` o 422 motivato, mai 500 |

### 2.6 Persistenza

| ID | Requisito | Criterio di accettazione |
|---|---|---|
| REQ-PER-01 | Lo schema si crea da zero su un database vuoto | script di migrazione idempotente su database vuoto |
| REQ-PER-02 | Ogni riga sorgente porta `source_id`, `data_reference`, `is_simulated`, `ingested_at` | ispezione dello schema |
| REQ-PER-03 | La pipeline funziona identica con repository in memoria e con repository Postgres | test parametrizzato sulle due implementazioni |
| REQ-PER-04 | Nessun driver di database e' importato fuori da `db/` e `repositories/` | test di architettura via AST |
| REQ-PER-05 | Le ingestion sono idempotenti | doppia esecuzione non duplica righe |
| REQ-PER-06 | Ogni finding e decisione prodotta e' conservata con il proprio hash | riga presente in `findings` e `decisions` |

### 2.7 Connettori

| ID | Requisito | Criterio di accettazione |
|---|---|---|
| REQ-CONN-01 | Ogni connettore espone `source_id`, `frequency`, `fallback()`, `run()` | test di interfaccia sui cinque connettori |
| REQ-CONN-02 | `run()` restituisce un esito con righe scritte, `is_simulated` e motivo | test di struttura dell'esito |
| REQ-CONN-03 | Nessun connettore produce finding | test di architettura: nessun import di `Finding` |
| REQ-CONN-04 | Un connettore in fallback scrive solo righe con `is_simulated=true` | test di coerenza del flag |
| REQ-CONN-05 | Il connettore RSS deriva `severity` e `confidence` con regole dichiarate, non estratte | test di derivazione su casi noti |
| REQ-CONN-06 | Il connettore RSS usa `pubDate` come data dell'articolo e `lastBuildDate` mai | test con feed di prova |
| REQ-CONN-07 | Il connettore RSS decodifica Il Mattino da ISO-8859-1 e interpreta le date italiane | test sul feed registrato |
| REQ-CONN-08 | Nessun connettore applica soglie o prioritizza | test di architettura |
| REQ-CONN-09 | Il connettore GTFS acquisisce il real-time da un proxy con header identificativi in configurazione | test: header presenti nella richiesta, nessun header nel codice |
| REQ-CONN-10 | `source_id` cita la fonte primaria, `data_reference` cita il proxy con timestamp | test: finding con `source_id=anm` e `data_reference` che contiene il proxy |
| REQ-CONN-11 | Le posizioni piu' vecchie di 90 secondi non sono lette dalle regole | test: posizione vecchia esclusa, posizione recente inclusa |
| REQ-CONN-12 | Con il proxy non raggiungibile il connettore scrive righe con `is_simulated=true` | test: fallback attivo, flag coerente |

### 2.8 Degradazione

| ID | Requisito | Criterio di accettazione |
|---|---|---|
| REQ-DEG-01 | Con la rete disattivata la demo produce una decisione valida | esecuzione della demo con socket inibiti |
| REQ-DEG-02 | Con il modello LLM spento la decisione e' identica | confronto di `decision_id` nei due modi |
| REQ-DEG-03 | Con OpenTripPlanner spento l'Agente Mobilita produce finding con `is_simulated=true` | test con servizio non raggiungibile |
| REQ-DEG-04 | Con il database non disponibile la demo usa il repository in memoria | test di selezione del profilo |
| REQ-DEG-05 | Ogni fallback dichiara la simulazione in `assumptions.md` | ispezione del file |
| REQ-DEG-06 | Con il proxy real-time non raggiungibile la demo produce finding con `is_simulated=true` | test con endpoint non raggiungibile |
| REQ-DEG-07 | Una risposta vuota del proxy real-time non produce errore | test: zero righe scritte, `outcome=ok` |

## 3. Requisiti non funzionali

| ID | Requisito | Criterio di accettazione |
|---|---|---|
| NFR-01 | Determinismo: stesso input, stesso output, byte per byte dopo canonicalizzazione | test di hash su due esecuzioni |
| NFR-02 | Il core non ha dipendenze oltre `pydantic` e standard library | ispezione degli import |
| NFR-03 | La decisione end-to-end si produce entro 2 secondi su fixture | misura nella suite |
| NFR-04 | L'avvio del backend entro 3 secondi con configurazione valida | misura del tempo di import e startup |
| NFR-05 | Configurazione invalida fallisce all'avvio, non a runtime | test con yaml malformato |
| NFR-06 | Ogni errore esposto ha un codice stabile e un campo quando applicabile | test sui codici |
| NFR-07 | Nessun segreto e nessun path personale assoluto nel repository | ricerca testuale in integrazione continua |
| NFR-08 | La suite gira senza rete per default | marker `network` disabilitato globalmente |
| NFR-09 | Ogni modulo del dominio ha un test di determinismo | ispezione della suite |
| NFR-10 | Il reasoning log e' leggibile da un umano in cinque righe | revisione manuale sullo scenario demo, registrata in `DEMO.md` |

## 4. Non obiettivi

Esplicitamente fuori dal backend:

- autenticazione, autorizzazione, gestione utenti;
- esecuzione di azioni sulla citta', invio di notifiche, prenotazioni;
- previsioni meteo proprietarie;
- copertura di tutta la rete di trasporto;
- scraping oltre le fonti elencate dalla traccia;
- addestramento di modelli;
- orchestrazione distribuita, message broker, code.

## 5. Traccia con gli step della guida

| Area | Step della guida |
|---|---|
| Contratti | 00, 01 |
| Orchestratore | 02, 03, 04 |
| Rilevanza | 05 |
| API | 06, 07 |
| Persistenza | 08 |
| Connettori | 09 |
| Mobilita' e routing | 10 |
| Linguaggio | 11 |
| Demo e metriche | 12 |

La matrice completa requisito, componente e test e' in [TRACEABILITY.md](TRACEABILITY.md).
