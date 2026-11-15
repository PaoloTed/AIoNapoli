# Agenti

Specifica degli agenti specializzati: dominio, input, output, casi di rifiuto.

## Contratto comune

Ogni agente produce un finding con i campi obbligatori:
agent, type, content, confidence, severity, source_id, data_reference,
is_simulated, timestamp.

## Agente Mobilita

- Dominio: percorsi, tempi, saturazione linee, stato reale delle corse di superficie.
- Input: stops, routes, trips, stop_times, service_alerts, vehicle_positions, trip_updates.
- Output: finding type route_disruption o route_alternative.
- Rifiuto: manca il GTFS per la linea richiesta.
- Rifiuto: punto di partenza o arrivo non mappato su una fermata.
- Rifiuto: finestra temporale oltre l'orizzonte del GTFS statico senza
  simulazione dichiarata.
- Rifiuto: real-time richiesto per una linea non coperta dal feed, senza
  simulazione dichiarata.
- Rifiuto: OTP non restituisce itinerari (`no_route`), va in timeout
  (`otp_timeout`), non è raggiungibile (`otp_unavailable`) o restituisce un
  errore HTTP/GraphQL/risposta invalida (`otp_error`).

## Agente Affollamento

- Dominio: densita in punti di interesse, saturazione mezzi.
- Input: occupancy_estimates, events, weather_snapshots, storico.
- Output: finding type density_alert.
- Rifiuto: occupancy assente e nessuna simulazione dichiarata.
- Rifiuto: evento senza geo-fence.
- Rifiuto: densita stimata fuori dal range 0..1.

## Agente Contesto

- Dominio: impatto atteso di eventi, meteo e alert.
- Input: events, weather_snapshots, service_alerts.
- Output: finding type impact_assessment.
- Rifiuto: meteo senza livello di allerta.
- Rifiuto: evento senza finestra temporale.
- Rifiuto: alert senza fonte citata.

## Cosa gli agenti non fanno

- Non calcolano percorsi con LLM.
- Non inventano fonti.
- Non parlano tra loro direttamente.