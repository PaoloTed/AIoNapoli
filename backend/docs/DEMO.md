[PIANIFICATO]

# Demo

Copione della demo: sequenza, tempi, cosa si vede, cosa si dice. Si compila quando la demo esiste. Questo file e' il riferimento per la voce NFR-10: il reasoning log deve essere leggibile in cinque righe, e la verifica e' manuale con esito registrato qui.

## 1. Scenario

Giornata critica a Napoli: regata dell'America's Cup a Bagnoli, Linea 2 ferma per un guasto, pioggia in arrivo nel pomeriggio.

## 2. Sequenza

| # | Tempo | Cosa si vede | Cosa si dice |
|---|---|---|---|
| 1 | 0-10 s | i tre finding entrano nel sistema | quali dati sono arrivati, da quali fonti, quali simulati |
| 2 | 10-30 s | le quattro regole vengono valutate, lo stream mostra quali scattano e quali no | perche' R1 scatta e R3 no, con la soglia |
| 3 | 30-45 s | il conflitto tra percorso proposto e zona satura | l'orchestratore rifiuta la deviazione proposta |
| 4 | 45-60 s | la priorita' applicata e il piano per i tre target | stessa situazione, tre output diversi |
| 5 | 60-75 s | il punteggio di rilevanza con i contributi per feature | perche' questa azione e' prima per il turista |
| 6 | 75-90 s | l'identificatore della decisione e la ripetizione identica | stessa situazione, stessa decisione, verificabile |

## 3. Varianti

| Variante | Quando | Cosa cambia |
|---|---|---|
| senza rete | rete assente al venue | nessun cambiamento visibile, il copione resta identico |
| senza OTP | grafo non disponibile | l'itinerario e' dichiarato simulato, il passo 1 lo dice |
| senza modello linguistico | modello non disponibile | il testo e' da template, la decisione e' identica |
| con Postgres | database disponibile | si mostra la query spaziale sul geo-fence dopo il passo 4 |

## 4. Verifica manuale del reasoning log

| Data | Esecutore | Passi nel log | Leggibile in cinque righe | Note |
|---|---|---|---|---|
| da compilare | da compilare | | | |

## 5. Cosa non si mostra

- Il database in fase di migrazione.
- Il build del grafo di OpenTripPlanner.
- Il codice.
- Metriche non calcolate da un campo esistente.
