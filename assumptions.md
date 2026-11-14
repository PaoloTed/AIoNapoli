[PIANIFICATO]

# Assumptions

Simulazioni, sostituzioni e semplificazioni dichiarate. Regola 4 dei principi anti-slop: ogni fonte ha un flag `is_simulated`, e ogni simulazione e' dichiarata qui.

Un finding con `is_simulated=true` che non trova la propria voce in questo file viola la regola. Il test `tests/contracts/test_assumptions.py` verifica la coerenza tra questo file e i dati prodotti.

## 1. Simulazioni dichiarate

| # | Cosa e' simulato | Perche' | Fonte reale possibile | Effetto |
|---|---|---|---|---|
| A1 | dataset eventi | non esiste un open data con geo-fence e affluenza attesa per gli eventi di Napoli | nessuna, la traccia stessa prevede il dataset simulato | finding di context e crowding con `is_simulated=true` |
| A2 | stime di occupazione dei mezzi | la pipeline di sensori IR termici produce dati sintetici nell'arco dell'hackathon | sensori fisici, fuori scope | finding di crowding con `is_simulated=true` |
| A3 | real-time del trasporto pubblico | i feed GTFS real-time di ANM ed EAV non sono disponibili in modo stabile | feed real-time ufficiale | finding di mobilita con `is_simulated=true` |
| A4 | set di alert in fallback | quando le fonti RSS non rispondono serve comunque una base per la demo | feed RSS ufficiali | alert scritti con `is_simulated=true` |
| A5 | snapshot meteo in fallback | quando il servizio meteo non risponde | Open-Meteo o ARPA Campania | snapshot scritto con `is_simulated=true` |
| A6 | itinerari di riserva dell'Agente Mobilita | se OpenTripPlanner non risponde, la demo deve comunque mostrare un percorso | risposta GraphQL registrata in fixture | finding di mobilita con `is_simulated=true` e motivo del fallback nel contenuto |

## 2. Semplificazioni dichiarate

| # | Semplificazione | Motivo | Cosa cambierebbe in produzione |
|---|---|---|---|
| S1 | copertura di una parte della rete, non di tutta la citta' | la traccia chiede pochi servizi che collaborano | import completo dei feed e integrazione con tutte le agenzie |
| S2 | zona derivata da una mappatura curata, non da un calcolo spaziale | il calcolo deve essere spiegabile in cinque righe | zone calcolate dalla geometria con confini ufficiali |
| S3 | severita' e confidence degli alert derivate da regole su testo e fonte | nessun feed espone i due campi come dato strutturato | classificatore supervisionato con dati etichettati |
| S4 | retro-compatibilita' dei feed non gestita | i feed possono cambiare schema | monitoraggio dello schema e allarmi |
| S5 | retention dei dati limitata alla durata dell'evento | non serve storico oltre la demo | politiche di retention e archivio |

## 3. Cosa non e' simulato

| Dato | Fonte reale | Note |
|---|---|---|
| fermate, linee, corse, orari | GTFS ANM ed EAV | feed statici scaricati |
| geometria della citta' | OpenStreetMap, estratto di Napoli | usato per il routing |
| meteo | Open-Meteo, dato corrente e previsione | senza chiave |
| comunicati e notizie | feed RSS ufficiali e testate locali | vedi contratto dei feed |

## 4. Regola di aggiornamento

Una simulazione nuova si aggiunge qui nello stesso commit che la introduce. Una simulazione non piu' attiva si marca `superata` con la data, non si cancella.
