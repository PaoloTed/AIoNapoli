# Piano di allineamento backend [PIANIFICATO]

Data: 2026-11-15. Base verificata: HEAD `1231722`. Questo documento definisce interventi e prove di accettazione; non attesta la loro implementazione. Integra `RECUPERO_PROGETTO.md` e assume come obiettivo una richiesta di viaggio reale con verifica delle perturbazioni e alternativa calcolata.

## Decisioni iniziali proposte

- Conservare FastAPI, Pydantic, PostgreSQL/PostGIS e frontend esistente. Recuperare il client OTP e i connettori dopo verifica dei relativi contratti.
- Un database PostgreSQL con separazione logica di rete, territorio, acquisizione e perturbazioni; un servizio OTP separato; un worker separato dall'API.
- Primo perimetro: cammino e trasporto pubblico nell'area napoletana coperta dai feed realmente validati. Partire da un operatore/feed, estendere dopo. ANM, EAV e Trenitalia sono fonti candidate, non coperture già acquisite.
- Default viaggio: partenza adesso, timezone Europe/Rome; ordinamento per arrivo più vicino, poi meno cambi e cammino; preferenze esplicite possono modificare l'ordine. Le durate vengono dal routing.
- Massimo tre calcoli per richiesta, budget temporale configurabile, riconoscimento di itinerari già scartati. Terminare anche con nessuna alternativa o dati insufficienti.
- Modalità reale e demo separate. Nessuna conversione automatica di errori, assenza di servizi o query non valide in itinerari fittizi.

## Cosa significa database città

OSM PBF è il file sorgente. OTP costruisce il proprio grafo da OSM e GTFS: non interroga automaticamente le tabelle PostgreSQL per pianificare. Il geocoder è un ulteriore componente: scaricare un PBF non crea una ricerca indirizzi funzionante.

In PostGIS importare inizialmente soltanto strade e POI necessari alla ricerca e al collegamento spaziale degli imprevisti, mantenendo ID OSM, geometrie, nomi e versione del dataset. Per provare routing tra coordinate questo import non è prerequisito: basta il grafo OTP. Diventa necessario, o va sostituito da un servizio equivalente, per associare notizie a segmenti della città.

Geocodifica tramite adattatore sostituibile verso un fornitore scelto e configurato. Catalogo locale di fermate/alias e luoghi della demo per disambiguazione e funzionamento controllato. Un catalogo limitato non equivale alla geocodifica di tutta Napoli. Nessuna coordinata inventata dal modello.

## Contratti da fissare prima delle implementazioni indipendenti

| Oggetto | Campi e regole minimi |
|---|---|
| TravelRequest | Origine/destinazione testuali o coordinate, partenza/arrivo richiesto, timezone, preferenze, contesto di chiarimento |
| ResolvedPlace | Coordinate WGS84, nome, fonte, identificativo, candidati e stato resolved/ambiguous/not_found |
| Itinerary | ID stabile, partenza/arrivo, durata, cammino, cambi, legs con tempi, modalità, namespace operatore/feed, route/trip/stop, geometrie disponibili |
| Disruption | ID e versione, fonte/documento, effetto, published/observed/ingested, validità temporale, ricorrenze se presenti, modi/direzione interessati, incertezza e stato |
| Impact | Disruption e leg coinvolti, blocked/penalized/uncertain, motivazione e evidenze |
| RoutingConstraint | Entità risolta, effetto, intervallo e modo interessato, fonte; distinguere vincolo richiesto, applicato e non supportato |
| JourneyResult | ok/needs_clarification/no_route/insufficient_data/upstream_unavailable, itinerari, impatti, fonti, freshness, trace sintetica e simulazione esplicita |

Separare l'identità della corsa dalla sua istanza nella giornata di servizio. Gestire orari GTFS oltre 24:00, calendario ed eccezioni. Non confondere nome pubblico di linea e route_id.

## Fase 1 — Prova reale di routing e vincoli

File principali: `docker-compose.yml`, `infra/`, `backend/app/services/agents/mobility/otp_client.py`, configurazione backend.

1. Fissare release OTP e immagine/versione Java corrispondente; verificare endpoint, schema GraphQL e parametri supportati. Il client esistente non è prova di compatibilità OTP2.
2. Preparare un estratto OSM adeguato con margine ai confini; validare un GTFS con servizi nella data di prova.
3. Costruire e avviare OTP, registrando hash/versioni degli input.
4. Adeguare il client a più itinerari, tempi, geometrie, ID e errori GraphQL, separando nessun percorso, query non valida e indisponibilità.
5. Provare esclusione di una linea/corsa realmente supportata e nuovo calcolo. Verificare a parte la fattibilità di esclusioni di segmenti stradali: non assumere che un poligono arbitrario sia accettato dall'API.

Accettazione: viaggio tra coordinate restituito da OTP senza fixture; con un servizio escluso, alternativa realmente diversa e compatibile oppure no_route esplicito. Nessun vincolo dichiarato applicato se è stato soltanto controllato a posteriori.

Questa è la prima verifica tecnica: farla prima di costruire tutti gli agenti.

## Fase 2 — Persistenza coerente e territorio

File principali: `database/migrations/`, `backend/app/db/`, `backend/app/repositories/`, `infra/postgres/`.

Scegliere un solo schema GTFS autorevole conciliando `gtfs-to-sql` e repository applicativo. Importare calendari, eccezioni, shapes e riferimenti necessari. Stesso dataset/versione nel database e nel grafo OTP, con mapping esplicito dei namespace.

Aggiungere documenti sorgente, stato di polling, perturbazioni e tabelle ponte verso linee/corse/fermate/segmenti. Conservare entità non risolte senza inventare riferimenti. Definire import statico in staging e pubblicazione controllata senza rompere FK o storico.

Import territoriale minimo: strade/segmenti e POI utili, indici spaziali e alias. Per misurare distanze utilizzare geography o CRS metrico adatto, non buffer in gradi.

Accettazione: import ripetibile; join tra un itinerario OTP e rete persistita; aggiornamento statico che conserva riferimenti validi; ricerca e risoluzione di un segmento noto.

## Fase 3 — Mobility e Imprevisti senza dipendenza dall'LLM

File principali: `services/agents/mobility/`, nuovo `services/agents/incidents/`, repository e nuovi modelli.

Implementare il nucleo deterministico degli impatti usando perturbazioni strutturate di prova. Controllare linee, corse, fermate, direzione e passaggio del singolo leg nell'intervallo dell'evento. Un evento a mezzogiorno non blocca automaticamente il viaggio della sera.

Intersezione geometrica = candidato da verificare. Distinguere strada sovrapposta, ponte/tunnel, treno, senso di marcia e modalità interessata. Un buffer attorno a un punto non dimostra la chiusura di ogni percorso che lo attraversa. Shapes GTFS mancanti o approssimate limitano la precisione del collegamento.

Accettazione: perturbazione attiva blocca il servizio pertinente; perturbazione futura/scaduta non lo blocca; eventi su altro modo o servizio non producono blocchi indiscriminati; ambiguità produce uncertain.

Se il motore non applica chiusure stradali arbitrarie, filtrare solo alternative effettivamente ottenute e comunicare il limite: non dichiarare risolto il ricalcolo generale delle strade. Un itinerario di cui non si riesce a verificare un tratto non diventa automaticamente sicuro.

## Fase 4 — Richiesta strutturata e orchestrazione

File principali: `services/facade.py`, nuovo servizio journey, `api/v1/`, `shared/schemas/`.

Aggiungere un endpoint proposto `POST /api/v1/journeys/plan` per coordinate e tempo. Conservare il vecchio endpoint scenario come demo, evitando di forzare viaggi reali nei finding per Bagnoli.

Orchestrazione: caricare perturbazioni pertinenti già note; chiamare Mobility; valutare candidati con Imprevisti; accumulare vincoli applicabili; ricalcolare entro tre tentativi e budget; produrre risultato esplicito. Salvare una traccia dei contributi e dei vincoli, senza esporre ragionamento interno del modello.

Accettazione: richiesta HTTP con coordinate produce viaggio reale; una perturbazione registrata cambia il risultato; nessun loop; timeout e dati insufficienti sono distinti da no_route.

## Fase 5 — Acquisizione automatica e agente Scraping

File principali: `anm_info/anm_scraper.py`, `services/connectors/rss/`, `services/connectors/gtfs/`, nuovo worker di ingestione.

Collegare lo scraper ANM tramite adattatore e configurare almeno un RSS verificato. Worker unico o lavori con lease per evitare duplicati; hash, cursori, retry/backoff, ETag dove supportato e audit persistente. Ultimo dato valido conservato con indicazione di anzianità.

LLM solo per documenti nuovi/modificati: estrazione JSON, validazione dello schema, risoluzione su catalogo e scrittura applicativa in transazione. Registrare versione del prompt/modello. Distinguere data di pubblicazione e periodo di applicazione; gestire rettifiche, riaperture e notizie bilingui duplicate.

Configurare il feed BusOne compatibile con lo statico scelto. Verificare parser, namespace, timestamps e relazioni GTFS-RT a livello di corsa e fermata. Le posizioni non sono una misura di affollamento o una prova di cancellazione.

Accettazione: un documento nuovo produce una perturbazione tracciabile; due polling identici non aggiungono interpretazioni AI; modifica rilevante viene rielaborata; errore esterno non inserisce una perturbazione simulata nel profilo reale.

## Fase 6 — Agente Input e prompt

Nuovo adattatore LLM e geocodifica; endpoint proposto `POST /api/v1/journeys` con prompt e contesto.

Estrarre richiesta strutturata e risolvere luoghi. Selezionare un modello con esempi italiani annotati, misurando output valido, date, precisione e latenza. Chiedere chiarimenti per ambiguità. Collegare GPS solo quando fornito dal client con consenso.

Preferenze non supportate vanno comunicate: “senza salite” richiede altimetria e supporto del routing; accessibilità richiede dati verificati, non solo inferenza del modello.

Accettazione: prompt chiaro raggiunge lo stesso flusso delle coordinate; luogo ambiguo produce needs_clarification; coordinate e tempi vengono validati; l'LLM non genera itinerari o minuti senza il motore.

## Fase 7 — Interfaccia e dimostrazione

Collegare una vista frontend al nuovo contratto. Mostrare percorso, cambi, motivi delle esclusioni, freshness, copertura, dati simulati e limiti. Affollamento e traffico entrano solo con fonti reali validate o scenario esplicitamente simulato.

Accettazione completa: domanda naturale → coordinate → percorso → perturbazione → alternativa verificata → risposta con fonti. Dimostrare anche perturbazione scaduta, nessuna alternativa, luogo ambiguo e sorgente indisponibile.

## Requisiti misurabili iniziali proposti

- Massimo tre calcoli per richiesta e budget routing complessivo iniziale di 15 secondi, configurabile. Misurare latenza p50/p95 sul sistema reale prima di dichiarare obiettivi prestazionali raggiunti; l'estrazione/geocodifica ha budget separato.
- Una sola elaborazione AI per combinazione documento/contenuto/versione dell'estrattore completata con successo; retry controllati per errori.
- Ogni blocco applicato deve avere fonte, validità e riferimenti alla rete o geometria verificabile.
- Freshness per fonte configurata e resa visibile; superare una soglia non dimostra automaticamente né servizio regolare né servizio interrotto.
- Distinguere affidabilità della fonte, incertezza di estrazione e completezza della copertura. Non presentare una percentuale di sicurezza inventata dal modello.

## Fuori dal primo incremento

Copertura completa di tutti gli operatori; traffico stradale live generalizzato; affollamento reale senza sensori/dati; garanzia di assenza di ostacoli sconosciuti; assistenza continua durante il viaggio; vincoli altimetrici senza dati. Restano obiettivi evolutivi, non funzioni da dichiarare già presenti.

## Riferimenti verificati

- https://docs.opentripplanner.org/en/latest/Basic-Tutorial/ — costruzione del grafo con GTFS e OSM.
- https://docs.opentripplanner.org/en/latest/RouteRequest/ — configurazione delle richieste; supporto concreto da verificare sulla release fissata e sulla relativa API.
- https://docs.opentripplanner.org/en/latest/Preparing-DEM/ — dati altimetrici per il grafo.

Nessun codice applicativo modificato per redigere questo piano. La documentazione online latest non sostituisce la verifica sulla release che verrà installata.
