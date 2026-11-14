# Connettori

Ingestion dati: recuperano, normalizzano, scrivono su DB. Non decidono nulla.

| Connettore | Fonte | Frequenza | Tabelle alimentate | Fallback | is_simulated |
|------------|-------|-----------|--------------------|----------|--------------|
| GTFS | ANM, EAV | statico giornaliero, real-time circa 10 secondi | stops, routes, trips, stop_times, vehicle_positions, trip_updates | simulazione dichiarata del real-time | false se reale, true su fallback |
| RSS/disruption | comunicati ufficiali | oraria | service_alerts | set di alert simulati | true su fallback |
| Eventi | dataset simulato dichiarato | giornaliera | events | nessuno, dataset gia simulato | true |
| Meteo | Open-Meteo o ARPA Campania | oraria | weather_snapshots | snapshot simulato dichiarato | true su fallback |
| Occupazione | sensori IR termici con dati sintetici | simulata | occupancy_estimates | simulazione statistica se pipeline IR non pronta | true |

Il connettore GTFS ha due modalita' di ingestion, con due client distinti e lo stesso ciclo `run()`. Restano un connettore solo: il confine di layer e' lo stesso.

## Modalita' real-time del connettore GTFS

Ingestion del real-time delle linee di superficie ANM. Il real-time non e' un connettore separato: e' una seconda modalita' del connettore GTFS, con un client dedicato.

Fonte primaria ANM, acquisita tramite il proxy BusOne che la normalizza in GTFS-Realtime. Il proxy non e' la fonte: il `source_id` del finding resta `anm` e il `data_reference` cita l'URL del proxy con il timestamp dell'emissione.

| Risorsa | Endpoint | Formato | Uso |
|---|---|---|---|
| posizioni mezzi | `/anm/gtfs-rt/vehicle-positions.json` | GTFS-RT JSON | ultima posizione per veicolo, entro 90 secondi |
| aggiornamenti corse | `/anm/gtfs-rt/trip-updates.json` | GTFS-RT JSON | ritardi, soppressioni, fermate saltate |
| stato | `/anm/status` | JSON | conteggi e timestamp dell'emissione, per diagnosi |

Regole del connettore:

- header identificativi (`X-BusOne-Client`, `X-BusOne-Use`) in configurazione, mai nel codice;
- nessuna API key;
- polling con `ETag`, nessun WebSocket: una connessione persistente aggiunge un canale da gestire senza valore per la demo;
- risposta vuota non e' un errore: zero righe scritte e `outcome=ok`;
- errore di rete o timeout: fallback attivo, righe con `is_simulated=true`, `outcome=fallback`;
- posizioni piu' vecchie di 90 secondi scritte ma escluse in lettura.

## Regola comune

Ogni connettore dichiara fonte, frequenza e fallback. Nessun connettore decide.