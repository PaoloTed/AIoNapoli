# Orchestratore

Riceve i finding, applica regole di trigger deterministiche, rileva e risolve
conflitti, produce un piano declinato per tre destinatari e un reasoning log.

## Regole di trigger

- R1_line2_crowding: se mobility.severity >= high e crowding.content.density
  > 0.85, allora evaluate_jointly.
- R2_conflict_route_vs_density: se mobility propone un percorso e crowding
  segnala la stessa zona satura, allora conflict=true.
- R3_weather_capacity: se context segnala pioggia intensa e crowding stima
  densita > 0.7, allora riduci capacita stimata.
- R4_event_surge: se events ha affluenza attesa oltre soglia e mobility
  segnala saturazione, allora valuta alternative.

## Priorita nei conflitti

- P1 sicurezza delle persone (Affollamento): prevale su tempo e esperienza.
- P2 tempo di percorrenza (Mobilita): prevale su esperienza.
- P3 esperienza e alternative (Contesto): ultima priorita.

## Formato del reasoning log

Ogni passo contiene: step, agent, finding_ref, rule_applied, outcome.
Una riga per passo, leggibile da un umano in 5 righe.

## Declinazione del piano

- Operatore: "Percorso X con priorita 1 per sicurezza; motivazione: densita
  sopra soglia in zona Y."
- Turista: "Alternativa: linea Z, tempo stimato 20 min. Alternative: line Z,
  estimated time 20 min."
- Cittadino: "Raggiungi il servizio pubblico S in 15 min via percorso A."

## Cosa l'orchestratore non fa

- Non esegue azioni sulla citta: produce raccomandazioni.
- Non usa LLM per decidere i trigger.
- Non duplica il lavoro degli agenti.