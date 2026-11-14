# Connettori

Ingestion dati: recuperano, normalizzano, scrivono su DB. Non decidono nulla.

| Connettore | Fonte | Frequenza | Tabelle alimentate | Fallback | is_simulated |
|------------|-------|-----------|--------------------|----------|--------------|
| GTFS | ANM, EAV | giornaliera statico, real-time dove disponibile | stops, routes, trips, stop_times, service_alerts | simulazione dichiarata del real-time | true su fallback |
| RSS/disruption | comunicati ufficiali | oraria | service_alerts | set di alert simulati | true su fallback |
| Eventi | dataset simulato dichiarato | giornaliera | events | nessuno, dataset gia simulato | true |
| Meteo | Open-Meteo o ARPA Campania | oraria | weather_snapshots | snapshot simulato dichiarato | true su fallback |
| Occupazione | sensori IR termici con dati sintetici | simulata | occupancy_estimates | simulazione statistica se pipeline IR non pronta | true |

## Regola comune

Ogni connettore dichiara fonte, frequenza e fallback. Nessun connettore decide.