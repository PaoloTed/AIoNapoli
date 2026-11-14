[PIANIFICATO]

# Metriche

Metriche prima e dopo, con il metodo di misura. Solo metriche calcolate da campi esistenti. Una stima si dichiara come stima.

La definizione operativa di ogni metrica e' in [OPERATIONS.md](OPERATIONS.md) sezione 7. Questo file registra i valori misurati.

## 1. Metriche del sistema

| Metrica | Come si misura | Prima | Dopo | Delta |
|---|---|---|---|---|
| tempo tra finding e decisione | timestamp della decisione meno timestamp del finding piu' recente | da compilare | da compilare | |
| passi del reasoning log | lunghezza di `reasoning_log` | da compilare | da compilare | |
| copertura dei target | target distinti in `plan` su tre | da compilare | da compilare | |
| azioni raccomandate | lunghezza di `plan` | da compilare | da compilare | |
| quota di dati simulati | finding con `is_simulated=true` sul totale | da compilare | da compilare | |
| decisioni identiche su input identico | confronto di `decision_id` su due esecuzioni | da compilare | da compilare | |

## 2. Metriche della demo

| Metrica | Valore misurato | Data della misura |
|---|---|---|
| durata della demo | da compilare | |
| tempo di risposta di OTP | da compilare | |
| itinerari restituiti per la coppia Bagnoli-Fuorigrotta | da compilare | |
| righe ingerite per connettore | da compilare | |
| veicoli reali osservati nella zona dell'evento | da compilare | |
| eta' media delle posizioni reali | da compilare | |
| corse con ritardo osservato | da compilare | |
| quota di finding con `is_simulated=false` | da compilare | |

Le ultime quattro metriche sono quelle che dimostrano il valore del real-time. Se sono a zero, il passo 2 della demo non ha sostanza.

## 3. Cosa non si dichiara

Nessuna metrica di impatto urbano non misurata: minuti risparmiati dai cittadini, riduzione della congestione, persone raggiunte. Il sistema misura il proprio comportamento, non l'effetto sulla citta'. Se serve una stima, va etichettata come stima e separata dalle misure.

## 4. Metodo

- Ogni valore e' prodotto dal comando `python -m app.cli demo --scenario bagnoli --report`.
- Il file di output e' versionato accanto a questa pagina quando esiste.
- Una metrica senza comando che la produce non entra in tabella.
