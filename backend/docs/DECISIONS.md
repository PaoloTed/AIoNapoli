[PIANIFICATO]

# Decisioni

Registro delle scelte tecniche con il motivo e le alternative scartate. Una voce per decisione. Le voci non si cancellano: si superano con una voce nuova che le cita.

Formato: `D-NN`, data, stato, contesto, decisione, conseguenze, alternative scartate, riferimenti.

## D-01 Spina dorsale pura e corsie indipendenti

**Data**: 2026-11-14
**Stato**: accettata
**Contesto**: il progetto vuole implementare tutte le componenti, incluse quelle con costo operativo alto: OpenTripPlanner, database con PostGIS, cinque connettori, modello linguistico. Con molte componenti esterne, un guasto in una porta giu' la demo se le dipendenze sono obbligatorie.
**Decisione**: il core e' una funzione pura `decide(findings, config, clock) -> Decision`. Ogni componente esterna e' un adattatore con sostituto dichiarato: repository in memoria, fixture OTP registrata, cache LLM, fallback dei connettori. Le quattro corsie (persistenza, connettori, routing, linguaggio) si attaccano in punti di innesto e possono essere spente.
**Conseguenze**: si implementa tutto, ma nulla e' obbligatorio in demo. Il test end-to-end gira su fixture e nessuna corsia puo' romperlo. Aumenta il lavoro di interfaccia, diminuisce la superficie di fallimento.
**Alternative scartate**: ridurre lo scope per prudenza, scartata perché la velocita' di scrittura con assistenza non e' il collo di bottiglia, lo e' la superficie di fallimento. Dipendenze obbligatorie, scartata perché rende la demo fragile.
**Riferimenti**: [ARCHITECTURE.md](ARCHITECTURE.md) sezioni 1 e 5, [REQUIREMENTS.md](REQUIREMENTS.md) REQ-DEG-01

## D-02 `content` aperto con accessor invece di validatori condizionali

**Data**: 2026-11-14
**Stato**: accettata, supera l'analogo punto della guida1
**Contesto**: la guida1 prevede validatori condizionali su `content` per crowding, mobility e context. Effetto collaterale: se il proprietario di un agente omette un campo, il suo finding e' invalido e la sua verticale non produce nulla.
**Decisione**: `content` resta `dict` libero. L'accesso avviene tramite funzioni che restituiscono `None` quando il dato manca: `density()`, `zone_id()`, `heavy_rain()`, `congestion()`, `expected_attendance()`. Se il valore e' `None`, la regola non scatta e il motivo entra nel reasoning log.
**Conseguenze**: il contratto resta stabile, l'attrito tra team sparisce, la robustezza dell'orchestratore resta. Il prezzo: un errore nel formato del dato si scopre alla regola, non alla validazione.
**Alternative scartate**: validatori condizionali, scartati per l'attrito organizzativo. `content` con modello chiuso per dominio, scartato perché la struttura non e' nota e verrebbe inventata.
**Riferimenti**: [CONTRACTS.md](CONTRACTS.md) sezioni 1.2 e 5

## D-03 `finding_ref` come hash del finding canonico

**Data**: 2026-11-14
**Stato**: accettata
**Contesto**: `ReasoningStep.finding_ref` deve citare un finding, ma il contratto non ha un campo identificatore. Una stringa arbitraria non e' verificabile.
**Decisione**: `finding_ref = sha256(canonical_json(finding))[:12]`, calcolato da una funzione pura. Stabile tra esecuzioni, ricalcolabile da chiunque abbia il finding.
**Conseguenze**: nessun campo aggiunto al contratto. Il log cita un riferimento verificabile. Due finding identici hanno lo stesso riferimento, ed e' corretto.
**Alternative scartate**: aggiungere `finding_id` al contratto, scartata per violazione del contratto congelato. Contatore incrementale, scartato perché non stabile tra esecuzioni.
**Riferimenti**: [CONTRACTS.md](CONTRACTS.md) sezione 4 voce C1

## D-04 Regola dominante con precedenza dichiarata

**Data**: 2026-11-14
**Stato**: accettata
**Contesto**: `trigger` contiene un solo `rule_id`, ma piu' regole possono scattare nello stesso scenario. Serve una regola per sceglierne una senza perdere informazione.
**Decisione**: `trigger.rule_id` e' la regola dominante secondo `rule_precedence` in `rules.yaml`. Le altre regole scattate restano nel `reasoning_log` come passi.
**Conseguenze**: contratto rispettato, informazione conservata. La precedenza e' configurabile e testabile.
**Alternative scartate**: `rule_id` composito, scartato perche' viola il tipo dichiarato. Regola con severita' massima, scartata perché la severita' non e' definita per regola.
**Riferimenti**: [CONTRACTS.md](CONTRACTS.md) sezione 4 voce C2

## D-05 `priority` come rango univoco per target

**Data**: 2026-11-14
**Stato**: accettata
**Contesto**: `PlanItem.priority` puo' essere il livello P1-P3 oppure il rango d'ordine. Le due semantiche non convivono.
**Decisione**: `priority` e' il rango d'ordine, univoco per target. Il livello P1-P3 vive nel `rationale` come testo.
**Conseguenze**: il frontend ordina senza ambiguita'. Il livello di dominio resta visibile e spiegabile.
**Alternative scartate**: P-level come valore, scartato perché due item dello stesso livello renderebbero l'ordine indefinito.
**Riferimenti**: [CONTRACTS.md](CONTRACTS.md) sezione 2.1

## D-06 Zone operative curate invece delle Municipalita'

**Data**: 2026-11-14
**Stato**: accettata
**Contesto**: R2 dipende da un identificatore di zona condiviso. Le dieci Municipalita' di Napoli sono ufficiali ma troppo ampie: Bagnoli e Fuorigrotta sono nella stessa municipalita', quindi il conflitto scatta banalmente e la deviazione proposta resta nella stessa zona.
**Decisione**: circa venti zone operative curate a mano, mappate su fermate e eventi. Identificatore `Z_<NOME>`. La mappatura vive in `database/seed/zones.csv`.
**Conseguenze**: R2 distingue quartieri vicini. La mappatura e' un dato curato, non un calcolo spaziale: spiegabile in una riga.
**Alternative scartate**: Municipalita', scartate perché rendono R2 banale e la demo non mostra il conflitto. Zone derivate a runtime da coordinate, scartate perché il calcolo non e' spiegabile in cinque righe e rende la demo dipendente da un algoritmo.
**Riferimenti**: [Schema del database](../../database/docs/SCHEMA.md) sezioni 2.1 e 3.1

## D-07 Repository in memoria come default, Postgres come profilo

**Data**: 2026-11-14
**Stato**: accettata
**Contesto**: la traccia ammette database anche leggero. Un database obbligatorio aggiunge avvio, migrazioni e dipendenze al percorso della demo.
**Decisione**: interfaccia `SourceRepository` con tre implementazioni: `memory` da fixture (default), `sqlite` per test senza Docker, `postgres` per il profilo reale e le metriche spaziali. Il profilo si sceglie da variabile d'ambiente.
**Conseguenze**: la demo non richiede setup. Postgres resta dimostrabile e usato per le query spaziali che aggiungono valore al racconto.
**Alternative scartate**: Postgres obbligatorio, scartato per fragilita' in demo. Solo in memoria, scartato perché perderebbe il valore delle query spaziali nel racconto.
**Riferimenti**: [Schema del database](../../database/docs/SCHEMA.md) sezione 9, [OPERATIONS.md](OPERATIONS.md) sezione 1

## D-08 OpenTripPlanner con fixture di riserva

**Data**: 2026-11-14
**Stato**: accettata
**Contesto**: OTP richiede un build del grafo di Napoli con costo di decine di minuti e diversi GB di RAM. La JVM locale e' Java 25, OTP richiede Java 21.
**Decisione**: OTP resta nel progetto, confinato all'Agente Mobilita' e solo in container. Il client ha timeout in configurazione. Se OTP non risponde, l'agente usa una fixture di risposta registrata e produce il finding con `is_simulated=true`. Il build si avvia prima dell'evento, non durante. Il grafo compilato e i feed sono esclusi da git.
**Conseguenze**: il valore scenico dell'itinerario reale resta, la dipendenza no.
**Alternative scartate**: togliere OTP, scartato perche' il percorso reale e' un elemento del racconto. Alternativa GTFS-lite scritta a mano, scartata come primo approccio ma tenuta come piano di riserva se il build fallisce.
**Riferimenti**: [ARCHITECTURE.md](ARCHITECTURE.md) sezione 5, [OPERATIONS.md](OPERATIONS.md) sezione 5.6

## D-09 Modello linguistico in replay per default

**Data**: 2026-11-14
**Stato**: accettata
**Contesto**: in demo la rete puo' mancare. Un modello obbligatorio rende la demo fragile e il determinismo non verificabile.
**Decisione**: l'uso del modello e' confinato a due punti: estrazione da testo non strutturato e formulazione del testo del piano. Modalita' `replay` per default, con cache delle generazioni; `live` opzionale; `off` sempre possibile. In ogni modalita' la `Decision` e' identica.
**Conseguenze**: la demo regge senza rete, il determinismo resta verificabile, il modello migliora la forma e non la sostanza.
**Alternative scartate**: modello obbligatorio per la formulazione, scartato per fragilita'. Nessun modello, scartato perché il testo del turista in due lingue beneficia della variazione.
**Riferimenti**: [OPERATIONS.md](OPERATIONS.md) sezione 4, [REQUIREMENTS.md](REQUIREMENTS.md) REQ-DEG-02

## D-10 Hash canonico come identificatore della decisione

**Data**: 2026-11-14
**Stato**: accettata
**Contesto**: il determinismo e' un principio anti-slop, ma senza una verifica esterna resta un'affermazione.
**Decisione**: `decision_id = sha256(canonical_json(decision_senza_timestamp))[:16]`. JSON con chiavi ordinate, float arrotondati, timestamp escluso dal calcolo e conservato accanto.
**Conseguenze**: il determinismo diventa verificabile dall'esterno con due chiamate. Il test piu' semplice della suite diventa anche il piu' persuasivo in demo.
**Alternative scartate**: UUID casuale, scartato perché non dimostra nulla.
**Riferimenti**: [ARCHITECTURE.md](ARCHITECTURE.md) sezione 4.3, [REQUIREMENTS.md](REQUIREMENTS.md) NFR-01

## D-11 Trace come sorgente unica del log e dello stream

**Data**: 2026-11-14
**Stato**: accettata
**Contesto**: il reasoning log deve essere coerente con cio' che e' successo, e lo stream SSE deve mostrare i passi. Costruirli separatamente significa poterli far divergere.
**Decisione**: la pipeline emette eventi in una `Trace`. `Decision.reasoning_log` e lo stream SSE sono due proiezioni della stessa trace.
**Conseguenze**: coerenza per costruzione. Un solo punto da testare. Lo stream diventa quasi gratuito.
**Alternative scartate**: costruire il log alla fine dai risultati, scartata perché il log potrebbe divergere dall'ordine reale dei passaggi.
**Riferimenti**: [ARCHITECTURE.md](ARCHITECTURE.md) sezione 4.2, [REQUIREMENTS.md](REQUIREMENTS.md) REQ-API-06

## D-12 Nessun framework di orchestrazione come contenitore della logica

**Data**: 2026-11-14
**Stato**: accettata
**Contesto**: la traccia suggerisce un framework di orchestrazione. Se le regole vivono dentro i nodi del grafo, non sono testabili senza avviare il grafo.
**Decisione**: il core e' composto da funzioni pure. Se serve la narrativa del grafo per il racconto, il grafo si costruisce come shell sottile attorno alle funzioni e il diagramma si genera dalla configurazione delle regole.
**Conseguenze**: testabilita' piena, determinismo verificabile, nessuna dipendenza obbligatoria. La narrativa resta disponibile se serve.
**Alternative scartate**: logica dentro i nodi del framework, scartata per testabilita'. Nessuna rappresentazione a grafo, scartata perché il racconto la usa.
**Riferimenti**: [ARCHITECTURE.md](ARCHITECTURE.md) sezione 1

## D-13 Database testato su Postgres reale, mai su SQLite

**Data**: 2026-11-14
**Stato**: accettata
**Contesto**: testare il repository Postgres su SQLite nasconde differenze di SQL, di tipi e di funzioni.
**Decisione**: i test dei repository girano su Postgres reale via testcontainers, con marker `db` e skip se Docker non e' disponibile. I test dei connettori e del core non toccano il database.
**Conseguenze**: bug di SQL scoperti in test, non in demo. La suite completa richiede Docker, la suite di default no.
**Alternative scartate**: test su SQLite, scartati perché nascondono difetti. Mock del driver, scartati perché non verificano il SQL.
**Riferimenti**: [OPERATIONS.md](OPERATIONS.md) sezione 6

## D-14 Regole di derivazione dichiarate per `severity` e `confidence`

**Data**: 2026-11-14
**Stato**: accettata
**Contesto**: il contratto dei feed RSS dimostra che nessun feed espone `severity` o `confidence` come campo strutturato, mentre la traccia le richiede su `service_alerts`.
**Decisione**: la derivazione e' dichiarata in `derivation.yaml` con una tabella per tipo di fonte e keyword riconosciute. Una keyword non riconosciuta produce `severity=medium` con la confidence della fonte. Un aggregatore non produce mai `severity=critical`.
**Conseguenze**: il campo e' popolato in modo deterministico e spiegabile. Il limite e' dichiarato: la severita' e' una stima del connettore, non un dato della fonte.
**Alternative scartate**: estrazione della severita' con il modello, scartata perché non riproducibile. Severita' sempre `medium`, scartata perché R1 e R4 diventano inutili.
**Riferimenti**: [Schema del database](../../database/docs/SCHEMA.md) sezione 4.2

## D-15 Un'incoerenza di unita' risolta con una funzione unica

**Data**: 2026-11-14
**Stato**: accettata
**Contesto**: la traccia dichiara `occupancy_pct` in 0..100, le regole leggono `density` in 0..1. Senza conversione esplicita le soglie confrontano grandezze diverse.
**Decisione**: una sola funzione `occupancy_to_density()`, soglie in configurazione con l'unita' nel nome, test dedicato.
**Conseguenze**: nessuna ambiguita' nelle soglie. Il nome della chiave impedisce l'errore piu' banale.
**Alternative scartate**: convertire nel connettore, scartata perché sposta la semantica nel layer sbagliato. Accettare `occupancy_pct` nelle regole, scartata perché contraddice il contratto del finding.
**Riferimenti**: [CONTRACTS.md](CONTRACTS.md) sezione 6

## D-16 Test di architettura come requisito

**Data**: 2026-11-14
**Stato**: accettata
**Contesto**: la regola "dipendenze solo verso il basso" e' una convenzione. Una convenzione decade il primo giorno di fretta.
**Decisione**: un test analizza gli import via AST e fallisce se `domain/` importa verso l'alto, se `api/` contiene logica, se un agente importa un altro agente, se un driver di database e' importato fuori da `db/` e `repositories/`.
**Conseguenze**: l'architettura e' verificata automaticamente. Il costo e' una mezza giornata di messa a punto del test.
**Alternative scartate**: revisione manuale, scartata perché non scala e non e' verificabile. Linter semantico esterno, scartato per dipendenza non necessaria.
**Riferimenti**: [ARCHITECTURE.md](ARCHITECTURE.md) sezione 3, [TRACEABILITY.md](TRACEABILITY.md) REQ-AGT-07, REQ-AGT-08, REQ-API-07, REQ-PER-04, REQ-CONN-03, REQ-CONN-08

## D-17 Documentazione per unita', sintesi generale solo alla fine

**Data**: 2026-11-14
**Stato**: accettata, sostituisce la collocazione iniziale di tutti i documenti in `docs/`
**Contesto**: la traccia 2.13 distingue documentazione generale e documentazione per unita'. Inizialmente tutti i documenti erano stati scritti in `docs/` alla radice, con l'effetto che un documento di 72 requisiti di backend risultava la fotografia del sistema, mentre e' la fotografia di una sua parte.
**Decisione**: i documenti stanno nella cartella dell'unita' che descrivono. Il backend in `backend/docs/`, il database in `database/docs/SCHEMA.md`, il frontend in `frontend/docs/`. `docs/README.md` alla radice contiene solo i riferimenti. La documentazione generale si scrive quando esistono le tre documentazioni di unita'.
**Conseguenze**: nessun documento mente sul proprio perimetro. Il frontend parte dai contratti prodotti dal backend. La sintesi generale descrive fatti e non intenzioni.
**Alternative scartate**: tutti i documenti in `docs/`, scartata perché confonde il perimetro e contraddice la traccia. Documentazione generale scritta subito, scartata perché sarebbe una previsione.
**Riferimenti**: [docs/README.md](../../docs/README.md), [SCHEMA.md](../../database/docs/SCHEMA.md), traccia punto 2.13

## D-18 Real-time ANM acquisito da un proxy di terze parti

**Data**: 2026-11-14
**Stato**: accettata
**Contesto**: ANM non pubblica i propri dati real-time come feed GTFS standard. Il proxy BusOne espone per il namespace `/anm/` GTFS statico, VehiclePositions e TripUpdates in formato GTFS-RT, senza API key, con osservazioni GPS reali. La demo dichiara la Linea 2 ferma, e i bus di superficie ANM sono l'alternativa concreta da mostrare.
**Decisione**: il connettore GTFS acquisisce una variante real-time verso il proxy. Il `source_id` dei dati resta `anm`, il `data_reference` cita l'URL del proxy con il timestamp dell'emissione. Header identificativi e endpoint in configurazione, mai nel codice. Polling con `ETag` ogni circa 10 secondi, nessun WebSocket. Le posizioni piu' vecchie di 90 secondi sono scritte ma escluse in lettura. Se il proxy non risponde o la risposta e' vuota, il connettore usa il fallback dichiarato e la demo prosegue.
**Conseguenze**: la simulazione del real-time del trasporto di superficie cade e il finding di mobilita puo' avere `is_simulated=false` citando una fonte reale. Servono due tabelle nuove, `vehicle_positions` e `trip_updates`. Il progetto dipende da un servizio di terze parti, e la dipendenza e' mitigata dal fallback obbligatorio.
**Alternative scartate**: usare il proxy come fonte primaria, scartata perche' viola la regola 3 anti-slop e perche' i dati originali restano di ANM. WebSocket per lo streaming, scartato perche' aggiunge una connessione persistente senza valore per la demo. Nessun real-time, scartata perche' lascia la demo su un dato simulato quando esiste un dato reale.
**Riferimenti**: [CONNECTORS.md](CONNECTORS.md) sezione connettore GTFS real-time, [SCHEMA.md](../../database/docs/SCHEMA.md) sezioni 2.9 e 2.10, [assumptions.md](../../assumptions.md) voci A3, A7, S6, S7

## Come si aggiunge una decisione

1. Assegnare il numero successivo.
2. Compilare tutti i campi. Se manca una conseguenza, la decisione non e' matura.
3. Se una decisione supera una precedente, citarla nel campo riferimenti con lo stato `superata` nella voce vecchia. Non riscrivere la voce vecchia.
4. Aggiornare il documento interessato nello stesso commit.
