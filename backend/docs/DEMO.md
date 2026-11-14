[PIANIFICATO]

# Demo

Copione della demo: sequenza, tempi, cosa si vede, cosa si dice. Si compila quando la demo esiste. Questo file e' il riferimento per la voce NFR-10: il reasoning log deve essere leggibile in cinque righe, e la verifica e' manuale con esito registrato qui.

## 1. Scenario

Giornata critica a Napoli: regata dell'America's Cup a Bagnoli, Linea 2 ferma per un guasto, pioggia in arrivo nel pomeriggio.

## 2. Sequenza

| # | Tempo | Cosa si vede | Cosa si dice |
|---|---|---|---|
| 1 | 0-10 s | i tre finding entrano nel sistema | quali dati sono arrivati, da quali fonti, quali simulati |
| 2 | 10-20 s | le posizioni reali dei bus ANM sulla zona dell'evento | il real-time e' reale, non simulato: fonte ANM, aggiornamento ogni dieci secondi |
| 3 | 20-35 s | le quattro regole vengono valutate, lo stream mostra quali scattano e quali no | perche' R1 scatta e R3 no, con la soglia |
| 4 | 35-50 s | il conflitto tra percorso proposto e zona satura | l'orchestratore rifiuta la deviazione proposta |
| 5 | 50-65 s | la priorita' applicata e il piano per i tre target | stessa situazione, tre output diversi |
| 6 | 65-78 s | il punteggio di rilevanza con i contributi per feature | perche' questa azione e' prima per il turista |
| 7 | 78-90 s | l'identificatore della decisione e la ripetizione identica | stessa situazione, stessa decisione, verificabile |

## 2.1 Cosa si dice sul real-time

Frase da usare, perche' e' il punto in cui il progetto si distingue:

> Le posizioni dei bus sono reali e arrivano da ANM. Il guasto della Linea 2 e' dichiarato da un comunicato, non osservato: la metropolitana non pubblica un feed. L'alternativa che proponiamo, pero', e' verificata su bus che stanno davvero circolando in questo momento.

Il limite va detto prima che lo chieda qualcuno. Un dato reale parziale e' piu' credibile di un dato completo simulato.

## 3. Varianti

| Variante | Quando | Cosa cambia |
|---|---|---|
| senza rete | rete assente al venue | nessun cambiamento visibile, il copione resta identico |
| senza real-time | proxy non raggiungibile | il passo 2 e' dichiarato simulato, il resto non cambia |
| senza OTP | grafo non disponibile | l'itinerario e' dichiarato simulato, il passo 1 lo dice |
| senza modello linguistico | modello non disponibile | il testo e' da template, la decisione e' identica |
| con Postgres | database disponibile | si mostra la query spaziale sul geo-fence dopo il passo 5 |

## 4. Verifica manuale del reasoning log

| Data | Esecutore | Passi nel log | Leggibile in cinque righe | Note |
|---|---|---|---|---|
| da compilare | da compilare | | | |

## 5. Cosa non si mostra

- Il database in fase di migrazione.
- Il build del grafo di OpenTripPlanner.
- Il codice.
- Metriche non calcolate da un campo esistente.
