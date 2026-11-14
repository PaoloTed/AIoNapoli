[PIANIFICATO]

# Assumptions

Simulazioni, sostituzioni e semplificazioni dichiarate. Regola 4 dei principi anti-slop: ogni fonte ha un flag `is_simulated`, e ogni simulazione e' dichiarata qui.

Un finding con `is_simulated=true` che non trova la propria voce in questo file viola la regola. Il test `tests/contracts/test_assumptions.py` verifica la coerenza tra questo file e i dati prodotti.

## 1. Simulazioni dichiarate

| # | Cosa e' simulato | Perche' | Fonte reale possibile | Effetto |
|---|---|---|---|---|
| A1 | dataset eventi | non esiste un open data con geo-fence e affluenza attesa per gli eventi di Napoli | nessuna, la traccia stessa prevede il dataset simulato | finding di context e crowding con `is_simulated=true` |
| A2 | stime di occupazione dei mezzi | la pipeline di sensori IR termici produce dati sintetici nell'arco dell'hackathon | sensori fisici, fuori scope | finding di crowding con `is_simulated=true` |
| A3 | real-time delle linee non coperte dal proxy | il proxy BusOne copre le linee di superficie ANM; la metropolitana e la rete EAV restano senza feed real-time | feed real-time ufficiale della metropolitana e di EAV | finding di mobilita con `is_simulated=true` per quelle linee |
| A4 | set di alert in fallback | quando le fonti RSS non rispondono serve comunque una base per la demo | feed RSS ufficiali | alert scritti con `is_simulated=true` |
| A5 | snapshot meteo in fallback | quando il servizio meteo non risponde | Open-Meteo o ARPA Campania | snapshot scritto con `is_simulated=true` |
| A6 | itinerari di riserva dell'Agente Mobilita | se OpenTripPlanner non risponde, la demo deve comunque mostrare un percorso | risposta GraphQL registrata in fixture | finding di mobilita con `is_simulated=true` e motivo del fallback nel contenuto |
| A7 | posizioni dei mezzi quando il proxy non risponde | il proxy BusOne e' un servizio di terze parti, fuori dal controllo del progetto | feed real-time ufficiale | `vehicle_positions` e `trip_updates` scritte con `is_simulated=true` |

## 2. Semplificazioni dichiarate

| # | Semplificazione | Motivo | Cosa cambierebbe in produzione |
|---|---|---|---|
| S1 | copertura di una parte della rete, non di tutta la citta' | la traccia chiede pochi servizi che collaborano | import completo dei feed e integrazione con tutte le agenzie |
| S2 | zona derivata da una mappatura curata, non da un calcolo spaziale | il calcolo deve essere spiegabile in cinque righe | zone calcolate dalla geometria con confini ufficiali |
| S3 | severita' e confidence degli alert derivate da regole su testo e fonte | nessun feed espone i due campi come dato strutturato | classificatore supervisionato con dati etichettati |
| S4 | retro-compatibilita' dei feed non gestita | i feed possono cambiare schema | monitoraggio dello schema e allarmi |
| S5 | retention dei dati limitata alla durata dell'evento | non serve storico oltre la demo | politiche di retention e archivio |
| S6 | real-time acquisito da un proxy di terze parti, non dalla fonte primaria | ANM non pubblica i propri dati real-time come feed standard; il proxy li normalizza | accordo diretto con ANM o feed GTFS-RT ufficiale |
| S7 | copertura delle linee di superficie ANM, non della metropolitana | il proxy non espone la metropolitana | integrazione con il feed della metropolitana |

## 2.1 Vincoli d'uso delle fonti esterne

| Fonte | Vincolo | Conseguenza |
|---|---|---|
| proxy BusOne | uso non profit gratuito, uso commerciale con accordo scritto | uso dichiarato `nonprofit`, nessun accordo richiesto per l'hackathon |
| proxy BusOne | header identificativi richiesti per l'uso continuativo | `X-BusOne-Client` e `X-BusOne-Use` in configurazione, mai nel codice |
| proxy BusOne | servizio di terze parti senza garanzia di continuita' | fallback dichiarato obbligatorio, vedi A7 |
| feed RSS | i feed cambiano schema e URL | contratto dei feed datato, parser difensivo |

## 3. Cosa non e' simulato

| Dato | Fonte reale | Note |
|---|---|---|
| fermate, linee, corse, orari | GTFS ANM ed EAV | feed statici scaricati |
| posizioni dei mezzi ANM di superficie | GTFS-RT via proxy BusOne, origine ANM | GPS misurati, aggiornamento circa 10 secondi, `is_simulated=false` |
| aggiornamenti delle corse ANM di superficie | GTFS-RT TripUpdates via proxy BusOne, origine ANM | passaggi osservati e stime, `is_simulated=false` |
| geometria della citta' | OpenStreetMap, estratto di Napoli | usato per il routing |
| meteo | Open-Meteo, dato corrente e previsione | senza chiave |
| comunicati e notizie | feed RSS ufficiali e testate locali | vedi contratto dei feed |

## 3.1 Attribuzione della fonte primaria

Il proxy BusOne rielabora dati che restano dei rispettivi titolari. La fonte primaria dei dati real-time di ANM e' ANM. Nel sistema:

```
source_id      = "anm"
data_reference = URL del proxy, con timestamp dell'emissione
```

Il proxy e' il trasporto, ANM e' la fonte. Un finding che citasse il proxy come `source_id` violerebbe la regola 3 dei principi anti-slop.

## 4. Regola di aggiornamento

Una simulazione nuova si aggiunge qui nello stesso commit che la introduce. Una simulazione non piu' attiva si marca `superata` con la data, non si cancella.
