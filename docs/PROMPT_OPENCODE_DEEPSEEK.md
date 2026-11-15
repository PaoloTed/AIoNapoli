# Prompt operativo per DeepSeek in OpenCode

Copia il testo sotto in OpenCode, con il repository aperto come directory di lavoro.

---

Devi allineare questo backend al piano concordato con il proprietario. Il lavoro viene revisionato da un secondo assistente: procedi per checkpoint e fermati alla fine di ciascuno. Non implementare tutte le fasi nello stesso turno.

## Letture iniziali obbligatorie

1. Leggi le istruzioni AGENTS.md applicabili, se presenti, e lo stato Git.
2. Leggi `docs/PIANO_ALLINEAMENTO_BACKEND.md` e `docs/RECUPERO_PROGETTO.md`.
3. Esamina il codice effettivo, Docker, migrazioni e test; la documentazione non prova che una funzione sia implementata.
4. Esamina `git show c84c5f45c5368be64c73ef48b2460b09f04fa68b` e l'infrastruttura GTFS attuale.
5. Per il web scraping delle news ANM devi usare lo strumento fornito dal team, che puoi prendere da `~/Scrivania/Documenti utili hackalon` (su questa macchina: `/home/r0x4n/Scrivania/Documenti utili hackalon`).

## Obiettivo e decisioni da rispettare

L'utente chiede un viaggio in linguaggio naturale. Il sistema risolve origine/destinazione, calcola itinerari reali, verifica perturbazioni temporali e territoriali, ricalcola alternative e spiega la scelta con fonti.

Conserva il database GTFS esistente e recuperane l'importatore: non sostituirlo automaticamente con seed o tabelle demo. Verifica e riconcilia le differenze tra schema prodotto dall'importatore e schema atteso dal backend.

Il territorio OSM deve essere disponibile sia al grafo OTP sia, per strade e POI utili, a PostgreSQL/PostGIS. Le perturbazioni vanno persistite e collegate a linee, corse, fermate e segmenti stradali. Preferisci un database con separazione logica per rete, città e dinamico.

GTFS + OSM alimentano il grafo OTP. Scrivere una perturbazione nel database non modifica automaticamente il routing. Verifica i vincoli effettivamente applicabili nella release/API scelta; non inventare endpoint o parametri.

Mantieni lo stack esistente salvo incompatibilità dimostrate. Non rifare frontend e backend da zero. Non aggiungere framework, broker o dipendenze pesanti senza un bisogno concreto nel checkpoint corrente. Non cancellare file, volumi o dati dell'utente, non eseguire reset distruttivi e non fare commit/push senza istruzione.

Mantieni modalità reale e demo separate: un servizio non disponibile, una query errata o l'assenza di un percorso non devono diventare un viaggio fittizio nel profilo reale. Non esporre credenziali, token o contenuti di file segreti nei report.

## Protocollo dei checkpoint

Inizia ORA dal CHECKPOINT 0 soltanto.

### CHECKPOINT 0 — Audit e proposta concreta, senza modifiche applicative

- Rileva HEAD, modifiche locali, runtime disponibili e stato dei servizi, senza avviare importatori o entrypoint con effetti collaterali.
- Verifica database GTFS, schema di importazione, volume e database territoriali eventualmente già presenti. Se Docker/database non sono accessibili dichiaralo: non assumere che siano vuoti o funzionanti.
- Verifica routing, contratto del client OTP, connettori, scraper, profilo persistente e fallback attuali.
- Rileva se PBF e GTFS sono già scaricati: riusali dopo verifica. Per il GTFS verifica almeno calendario, copertura, identificativi e data di servizio.
- Proponi release OTP, input, comando di costruzione e prova di esclusione supportata; usa documentazione ufficiale della release, non supposizioni.
- Individua le modifiche minime e i file del checkpoint successivo; segnala conflitti con lavoro locale.
- Puoi scrivere solo il report del checkpoint, senza cambiare codice, configurazioni operative o dati.
- FERMATI e attendi che l'utente riporti l'esito della revisione.

### CHECKPOINT SUCCESSIVI — solo dopo approvazione del precedente

Segui le fasi 1–7 del piano, un checkpoint per volta. Se una fase è troppo ampia, suddividila in sotto-checkpoint con risultati verificabili e comunica la suddivisione nel report; non estendere autonomamente il perimetro.

- Fase 1: OTP reale con dati validati e prova di ricalcolo con esclusione supportata.
- Fase 2: integrazione schema GTFS, import territoriale PostGIS e relazioni dinamiche. Se necessario dividi in 2A GTFS, 2B città, 2C perturbazioni.
- Fase 3: Mobility e Imprevisti con casi strutturati di prova, date, modalità e incertezza.
- Fase 4: endpoint di viaggio e orchestratore, massimo tre calcoli, riconoscimento dei candidati ripetuti e stati espliciti.
- Fase 5: worker, scraper ANM/RSS/realtime, deduplicazione e interpretazione AI dei soli contenuti nuovi o modificati.
- Fase 6: prompt, geocodifica, preferenze e chiarimenti.
- Fase 7: collegamento frontend e demo verificata.

Le dipendenze minime, come download ed estrazione PBF per costruire OTP, appartengono alla fase che le richiede: non anticipare per questo l'intera importazione territoriale o tutte le fasi successive.

Prima di ogni modifica rileggi lo stato dei file interessati. Implementa soltanto il checkpoint autorizzato, esegui verifiche significative e conserva i dettagli in un report. Se non puoi eseguire una verifica scrivi NON ESEGUITA e il motivo. Non chiamare una fase completata se il suo criterio principale non è dimostrato.

## Acquisizione e importazione della città

Nel repository esistono già:
- `PBF_URL` verso `https://download.geofabrik.de/europe/italy/sud-latest.osm.pbf`;
- uno script `infra/postgres/scripts/download-monthly.sh` che prevede il download;
- installazione di `osmium-tool` e `osm2pgsql` nel Dockerfile PostgreSQL.

Verifica questo stato: non considerare installazione degli strumenti o download equivalenti a un'importazione OSM già effettuata. Non eseguire tutto lo script mensile solo per scaricare OSM: include anche operazioni GTFS da verificare prima.

Quando il checkpoint relativo è autorizzato:
1. Riusa un PBF locale integro oppure scarica il file Sud da Geofabrik con verifica TLS, errori HTTP gestiti, retry e file temporaneo; pubblica il file definitivo solo dopo validazione.
2. Registra URL, data del download, timestamp dei dati, checksum, dimensione e attribuzione OpenStreetMap contributors/ODbL. Non aggiungere PBF o grafi a Git.
3. Estrai con `osmium extract` l'area necessaria a Napoli e ai collegamenti del primo perimetro. Definisci confini configurabili con margine e motivali; non chiamare “intera area metropolitana” un ritaglio non verificato. Conserva la struttura e i tag necessari al routing, evitando estratti composti soltanto da strade filtrate.
4. Usa l'estratto per OTP e importalo con osm2pgsql in uno schema territoriale separato, tramite staging. Verifica la versione installata e lo stile/output compatibile. Il refresh non deve eliminare gli oggetti referenziati dalle perturbazioni: prevedi identità stabili o mapping/versioni.
5. Esponi strade e POI utili: tipo/id OSM, nomi, tag di accesso/direzione/livello disponibili e geometria; per POI poligonali conserva la geometria e ricava un punto rappresentativo se utile. Distingui way OSM da segmento topologico: il primo non coincide automaticamente con il secondo.
6. Aggiungi indici spaziali e prove SQL per strade/POI noti, conteggi, geometrie valide e ricerca spaziale. Usa CRS metrico o geography per distanze, non buffer in gradi.
7. Documenta un comando riproducibile per download, estrazione, import e verifica; definisci il comportamento di una seconda esecuzione senza danneggiare il GTFS.

Il geocoder rimane un servizio/adattatore distinto: l'importazione OSM non crea da sola una ricerca affidabile per tutti gli indirizzi. Non dichiarare disponibili tutti i civici, tutti i POI o la gestione delle salite senza averlo verificato.

Fonti ufficiali di riferimento:
- https://download.geofabrik.de/europe/italy/sud.html
- https://docs.osmcode.org/osmium/latest/osmium-extract.html
- https://osm2pgsql.org/doc/manual.html
- https://docs.opentripplanner.org/ (seleziona la release effettiva)

## Formato del risultato da riportare al revisore

Salva dettagli riproducibili in `docs/reports/checkpoint-<numero>.md`, senza segreti o dump enormi. Riporta le eventuali modifiche ai file anche se preesistenti; non attribuirti lavoro altrui.

La risposta finale deve contenere al massimo 500 parole, secondo questa struttura:

CHECKPOINT: <numero e titolo>
ESITO: COMPLETATO / PARZIALE / BLOCCATO
BASE: <HEAD iniziale; modifiche locali rilevanti>
RISULTATO: <cosa funziona realmente, massimo 4 punti>
FILE: <principali file modificati e link al report completo>
VERIFICHE: <comando; PASS/FAIL/NON ESEGUITA; risultato essenziale>
EVIDENZA: <esempio concreto, ID o estratto breve utile alla verifica>
LIMITI: <problemi aperti, vincoli non applicati, simulazioni e verifiche mancanti>
PROSSIMO CHECKPOINT: <perimetro esatto proposto>

Concludi: “Mi fermo qui in attesa della revisione del checkpoint.”

Se la revisione richiede correzioni, correggi soltanto il checkpoint corrente e ripeti il report. Passa al successivo solo quando l'utente ti trasmette esplicitamente l'ok. Non interpretare il superamento di un test come approvazione a proseguire.

Inizia adesso con il CHECKPOINT 0.
