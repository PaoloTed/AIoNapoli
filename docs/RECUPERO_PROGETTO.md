# Analisi del progetto e proposta di recupero

Analisi del codice a HEAD `1231722`, confrontato con il commit `c84c5f45c5368be64c73ef48b2460b09f04fa68b`, e della traccia Challenge 05 fornita dal team. Le proposte qui sotto sono pianificate, non funzionalità già implementate.

## Decisione consigliata

Recuperare il progetto con una revisione del flusso dati e dell'integrazione. Conservare stack, interfaccia, contratti, repository e parti dei connettori. Sostituire gradualmente i percorsi dimostrativi con un percorso reale completo, mantenendo una modalità demo esplicita.

La traccia permette simulazioni dichiarate e pochi servizi: l'obiettivo prioritario è dimostrare una collaborazione utile tra agenti su un caso concreto, con fonti e tempi verificabili.

## Cosa fa oggi, verificato nel codice

| Parte | Stato osservato | Conseguenza |
|---|---|---|
| Frontend | `frontend/hooks/useDecision.ts` invia `scenario_id` | L'interfaccia richiede decisioni su scenari preparati |
| Facade | `backend/app/services/facade.py` carica `shared/mocks/scenarios.json` e passa i finding alla pipeline | Il percorso HTTP di decisione non esegue i tre agenti sul database |
| Agenti | `services/agents/` contiene mobility, crowding e context con metodi `evaluate()` | Componenti riutilizzabili, attualmente deterministici, senza modelli AI |
| Orchestratore | `services/orchestrator/pipeline.py` applica regole, conflitti e priorità | Buona base per validazione e vincoli; non coordina ancora chiamate agli specialisti |
| Testi | `services/orchestrator/narrative.py` usa cache o template anche con modalità `live` | Non esiste una chiamata LLM attiva in questo percorso |
| Piano | `services/orchestrator/plan.py` contiene alternative e minuti fissi | La raccomandazione non dimostra ancora un itinerario ricalcolato |
| Database | La migrazione include rete, avvisi, posizioni, aggiornamenti, finding e decisioni | Esiste già parte della separazione statico/dinamico desiderata |
| GTFS Docker | Il commit indicato configura importazione GTFS e download OSM mensili | Recuperabile, ma deve convergere con lo schema del backend |
| GTFS backend | `GtfsConnector.run_static()` carica un seed; il lettore ZIP importa solo stops e routes | Il percorso CLI non carica ancora un GTFS completo reale |
| Realtime | Il connettore carica il seed prima di scrivere posizioni e aggiornamenti | Il seed non garantisce le FK per gli ID restituiti dal feed reale |
| RSS | La CLI crea `RssConnector` senza `feed_url`, quindi usa fallback | Lanciare l'ingestione RSS non equivale a leggere una fonte reale |
| Scraper ANM | Script e JSON in `anm_info/`, senza collegamento rilevato nel backend | Serve un adattatore verso il flusso di acquisizione |
| Polling | Il cron esistente riguarda download mensili; nessun worker applicativo continuativo individuato | Mancano acquisizione dinamica, elaborazione e rivalutazione automatiche |
| Profilo predefinito | `APP_PROFILE=memory` | Le scritture di una CLI non diventano archivio persistente condiviso con l'API |

Due aspetti richiedono verifica specifica su PostgreSQL: compatibilità tra le tabelle prodotte da `gtfs-to-sql` e quelle attese dalle migrazioni applicative; comportamento dell'importazione successiva con riferimenti dinamici già presenti. Non considerarli integrati solo perché condividono un container.

## Architettura proposta [PIANIFICATO]

Un'istanza PostgreSQL/PostGIS, un database, con separazione logica:

- `transit`: operatori, linee, fermate, corse, passaggi, calendari, eccezioni e geometrie; identificativi con namespace della fonte e versione del dataset.
- `live`: avvisi, collegamenti avviso-linea/fermata/corsa, osservazioni veicoli, ritardi, cancellazioni e stato di acquisizione.
- `ingestion`: documenti originali, hash, URL, date di pubblicazione/acquisizione, esiti, cursori e lavori da elaborare.
- `agent`: evidenze elaborate, decisioni e versioni dei modelli/prompt.

Sono schemi proposti: non occorre migrare subito ogni tabella per iniziare. Occorre invece scegliere un solo schema GTFS autorevole prima di collegare le fonti reali.

PostgreSQL non supporta normali FK tra database separati. Due schemi nello stesso database consentono di conservare la separazione desiderata con vincoli relazionali.

Un avviso può riguardare più linee e più fermate: servono tabelle ponte. `route_id` indica una linea; `trip_id` una corsa programmata; un tratto interrotto può richiedere direzione e intervallo di fermate. Un solo campo route nell'avviso non rappresenta tutti questi casi.

Gli ID estratti dal testo devono essere risolti su operatori e cataloghi reali: il nome pubblico “151” non è necessariamente il `route_id`. Per entità mancanti conservare l'avviso e lo stato di mancata risoluzione, senza inventare una FK. Linea 2 e rete ANM non vanno trattate come un solo operatore.

Gli aggiornamenti statici vanno preparati e validati in staging, quindi pubblicati atomicamente. Conservare mapping/versioni necessari agli eventi ancora validi, evitando cancellazioni a cascata dello storico.

### Flusso automatico

1. Worker di acquisizione indipendente dal server HTTP: scarica RSS, notizie ANM e feed strutturati.
2. Salvataggio del documento originale e confronto hash/ID/ETag dove disponibile.
3. Regole economiche individuano possibili notizie rilevanti e passano gli ambigui all'estrattore.
4. Un agente specializzato interpreta solo documenti nuovi o modificati e produce JSON validato.
5. Codice applicativo verifica date, fonti e identificativi, quindi salva avviso e collegamenti in transazione.
6. Un evento di modifica significativa richiede la rivalutazione degli specialisti coinvolti.
7. Mobilità calcola alternative usando rete e perturbazioni; contesto valuta meteo/eventi; crowding interviene se esistono osservazioni o simulazioni dichiarate.
8. Orchestratore confronta le proposte, applica vincoli e produce una risposta motivata con fonti.
9. API e frontend leggono lo stato persistito e mostrano disponibilità e anzianità dei dati.

Per il primo prototipo bastano un worker e una coda su PostgreSQL con claim/lease e retry. Evitare processi di polling duplicati in ogni worker HTTP. Non serve aggiungere subito un broker.

Frequenze iniziali da verificare rispetto alle fonti: RSS 2–5 minuti, scraper ANM 5–10 minuti, meteo 15–30 minuti, realtime 15–30 secondi; controllo GTFS giornaliero o secondo metadati e validità del servizio. Sono impostazioni proposte, non garanzie dei fornitori.

### Validità e costi

Distinguere `published_at`, `observed_at`, `ingested_at`, `valid_from`, `valid_to` e stato della perturbazione. La data di pubblicazione non è l'inizio dello sciopero. Una finestra giornaliera ripetuta non è un'interruzione continua.

Prevedere rettifiche, riaperture, annullamenti e risoluzioni esplicite. In caso di durata sconosciuta, mantenere lo stato da verificare e una politica di rivalutazione: non lasciare ogni avviso valido per sempre. L'assenza da un elenco di news non dimostra da sola la risoluzione.

Feed numerici e strutturati: parsing senza LLM. Notizie: cache per hash del contenuto, versione del modello e prompt/schema. Decisioni: invalidazione su modifiche rilevanti e scadenze. Una nuova osservazione GPS non deve produrre una nuova chiamata LLM per ogni veicolo. Una domanda utente non deve riscaricare tutte le fonti.

Fuori dalla demo, un errore di rete deve conservare l'ultimo dato valido e dichiararlo vecchio/indisponibile, senza inserire automaticamente incidenti simulati nello stato reale.

## Agenti e strumenti [PIANIFICATO]

| Ruolo | Compito | Strumenti consentiti |
|---|---|---|
| Avvisi/viabilità | Filtrare e strutturare notizie, validità temporale, impatto e riferimenti | Leggere documenti acquisiti, cercare alias, proporre avvisi strutturati |
| Mobilità | Individuare servizi coinvolti e proporre itinerari compatibili | Catalogo GTFS, stato dinamico e motore di routing |
| Contesto | Valutare meteo/eventi per zona e intervallo | Snapshot meteo, eventi e ricerca geospaziale |
| Orchestratore | Richiedere contributi, risolvere conflitti, spiegare la scelta | Finding validati, alternative e fonti |

Crowding resta utilizzabile in demo, ma una posizione GPS non misura quante persone sono sul mezzo. Dichiarare ogni stima simulata e la sua origine.

Le “skill” applicative devono diventare strumenti effettivamente invocabili, istruzioni di dominio e contratti input/output. Un file Markdown da solo non collega un agente alle fonti. Il modello propone dati; il servizio applicativo autorizzato esegue le scritture dopo la validazione, senza SQL arbitrario generato dal modello.

Scegliere un modello piccolo per estrazione/classificazione confrontandolo su un campione annotato delle notizie reali del team. Misurare precisione sulle linee, intervalli temporali, eventi irrilevanti, JSON valido, latenza e costo per documento nuovo. Prevedere escalation per casi ambigui; non scegliere il modello soltanto per numero di parametri. Il modello più capace, se necessario, si concentra sulla sintesi e sui conflitti.

Conservare una parte deterministica nell'orchestratore è utile. Per mostrare collaborazione agentica, rendere visibili contributi indipendenti e revisione di una proposta alla luce del contributo di un altro specialista.

## Ruolo di BusOne

Documentazione consultata: https://proxy.busone.app/anm/ . La documentazione dichiara identificativi condivisi tra il proprio GTFS e realtime, posizioni GPS e aggiornamenti delle corse, copertura ANM di superficie e dati osservati distinti dalle stime. Non presumere copertura completa della rete ferroviaria o di tutte le interruzioni.

Risorse documentate: `/anm/gtfs.zip`, `/anm/gtfs-rt/vehicle-positions.json`, `/anm/gtfs-rt/trip-updates.json`, `/anm/status`, notifiche `/anm/ws`.

È una buona sorgente per collegare programmazione e osservazioni; lo scraper ANM completa il quadro con comunicati espliciti. Assenza di un veicolo nel feed non significa cancellazione della linea.

Prima dell'uso automatico configurare `X-BusOne-Client` con applicazione e contatto reali e `X-BusOne-Use` coerente. La pagina pubblica specifica condizioni di accesso, attribuzione e uso: verificarle rispetto all'organizzazione e al progetto. Non presumere che qualsiasi uso in hackathon sia automaticamente coperto.

È stata verificata la documentazione pubblica, non l'effettiva disponibilità attuale dei feed né la compatibilità del parser locale con payload live.

## Ordine di recupero e risultati verificabili [PIANIFICATO]

1. **Contratto dati unico.** Scegliere importatore GTFS e schema autorevole; caricare un dataset completo con calendari; unire un payload realtime compatibile senza violare le FK.
2. **Acquisizione persistente.** Collegare scraper ANM e una fonte RSS configurata; due polling identici producono un documento logico e nessuna nuova interpretazione AI.
3. **Primo specialista AI.** Estrarre da un avviso reale linee, effetto e finestre temporali; validare su esempi annotati e conservare fonte, testo e incertezze.
4. **Percorso applicativo completo.** Un job aggiorna il database, esegue specialisti e orchestratore, salva una decisione leggibile dall'API senza `scenario_id`.
5. **Alternativa verificata.** Integrare un motore di routing configurato e alimentato dalla stessa rete, assicurando che gli impatti siano applicati al calcolo. Non basta eliminare un itinerario se manca qualsiasi alternativa calcolabile. Mostrare durata proveniente dal motore, senza minuti fissi.
6. **Demo collaborativa.** Una perturbazione cambia il viaggio; meteo/evento rende meno adatta una prima alternativa; l'orchestratore sceglie una seconda soluzione mostrando i contributi. Usare simulazione esplicita dove mancano dati.

Metriche: ritardo fonte→stato aggiornato, tempo di risposta, chiamate AI per documento nuovo, percentuale di duplicati evitati, accuratezza di estrazione e rispetto delle interruzioni. Gli effetti su attese e tempi di viaggio sono stime dello scenario finché non misurati sul campo.

Non introdurre contemporaneamente nuove schermate, nuovi framework agentici e nuove fonti prima del primo flusso completo.

## Limiti della verifica eseguita

Analisi statica del repository e consultazione della documentazione BusOne. Il tentativo `python3 -m pytest -q` termina prima della raccolta dei test: il pytest disponibile nell'ambiente Python 3.14 fallisce con `AttributeError: __spec__`. Non è una prova di errore applicativo e non certifica che i test passino. Non sono stati avviati Docker, importazioni reali, frontend o modelli AI. Nessun codice applicativo modificato.
