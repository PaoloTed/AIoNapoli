[COMPLETATO]

# Metriche

Metriche prima e dopo, con il metodo di misura. Solo metriche calcolate da campi esistenti. Una stima si dichiara come stima.

La definizione operativa di ogni metrica e' in [OPERATIONS.md](OPERATIONS.md) sezione 7. Questo file registra i valori misurati.

## 1. Metriche del sistema

| Metrica | Come si misura | Prima | Dopo | Delta |
|---|---|---|---|---|
| tempo tra finding e decisione | timestamp della decisione meno timestamp del finding piu' recente | non misurato (nessuna pipeline) | `1.41 ms` runtime locale (`9328.999 s` rispetto al timestamp fisso della fixture) | pipeline end-to-end < 2 s |
| passi del reasoning log | lunghezza di `reasoning_log` | 0 | `5` (contigui 1..5) | entro soglia NFR-10 (<= 5) |
| copertura dei target | target distinti in `plan` su tre | 0/3 | `3/3` (`operator`, `tourist`, `citizen`) | +3 target coperti |
| azioni raccomandate | lunghezza di `plan` | 0 | `3` | 1 azione prioritaria per target |
| quota di dati simulati | finding con `is_simulated=true` sul totale | N/D | `0.67` (2/3 nello scenario `bagnoli`) | dichiarato per singolo finding |
| decisioni identiche su input identico | confronto di `decision_id` su due esecuzioni | non deterministico | `true` (`23afe929acf8f472` == `23afe929acf8f472`) | 100% deterministico |

## 2. Metriche della demo

| Metrica | Valore misurato | Data della misura |
|---|---|---|
| durata della demo | `1.41 ms` calcolo pipeline locale (`< 2.0 s` budget NFR-03 verificato da `pytest`) | 2026-11-14 |
| tempo di risposta di OTP | offline / fallback fixture deterministica (`shared/mocks/otp_fixture.json`) | 2026-11-14 |
| itinerari restituiti per la coppia Bagnoli-Fuorigrotta | `1` itinerario da fixture OTP (`20 min`, Bus 151 + Cumana) | 2026-11-14 |
| righe ingerite per connettore | `rss: 1`, `gtfs (static seed): 29`, `gtfs-rt (fallback): 2`, `weather: 1`, `events: 1`, `occupancy: 1` | 2026-11-14 |
| veicoli reali osservati nella zona dell'evento | `2` posizioni (`ANM-2231`, `ANM-1514`) nello scenario `bagnoli` (fallback offline in assenza di proxy live) | 2026-11-14 |
| eta' media delle posizioni reali | finestra massima applicata `<= 90 s` (`rt_max_age_s=90`, filtro verificato in `test_rt_freshness.py`) | 2026-11-14 |
| corse con ritardo osservato | `0` con feed `trip-updates` offline/fallback; soglia ritardo agente `>= 300 s` | 2026-11-14 |
| quota di finding con `is_simulated=false` | `0.33` (`1/3`: finding `mobility` nello scenario `bagnoli`) | 2026-11-14 |

Le ultime quattro metriche sono quelle che dimostrano il valore del real-time. Se sono a zero, il passo 2 della demo non ha sostanza.

## 3. Cosa non si dichiara

Nessuna metrica di impatto urbano non misurata: minuti risparmiati dai cittadini, riduzione della congestione, persone raggiunte. Il sistema misura il proprio comportamento, non l'effetto sulla citta'. Se serve una stima, va etichettata come stima e separata dalle misure.

## 4. Metodo

- Ogni valore e' prodotto dal comando `python -m app.cli demo --scenario bagnoli --report`.
- Il file di output e' versionato accanto a questa pagina quando esiste.
- Una metrica senza comando che la produce non entra in tabella.
