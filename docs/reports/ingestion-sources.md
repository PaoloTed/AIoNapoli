# Registro fonti e ultimo esito di acquisizione

Generato: 2026-11-15T10:42:20+00:00 (UTC). Fonte dati: tabelle `ingestion_sources`, `ingestion_documents`, `ingestion_fetches`.

Il registro riproducibile è `backend/app/config/sources.yaml`: 96 fonti uniche (95 URL unici dei due elenchi del team, inclusi i tentativi non RSS censiti, più lo scraper ANM). Le fonti `non_rss` restano censite ma non vengono chiamate. Eventuali duplicati esatti di URL sarebbero accorpati in una sola acquisizione con tutta la provenienza in `provenance`.

| # | source_id | classe | tipo | HTTP | ultimo esito | doc | filtrati | pending | interpretati | irrilevanti | errore |
|---:|---|---|---|---:|---|---:|---:|---:|---:|---:|---|
| 1 | `google_news_aeroporto` | aggregator | google_news | 200 | ok | 74 | 5 | 69 | 0 | 0 | - |
| 2 | `google_news_aeroporto_7d` | aggregator | google_news | 200 | ok | 27 | 4 | 23 | 0 | 0 | - |
| 3 | `google_news_allerta_meteo` | aggregator | google_news | 200 | ok | 75 | 6 | 69 | 0 | 0 | - |
| 4 | `google_news_crociere` | aggregator | google_news | 200 | ok | 42 | 9 | 33 | 0 | 0 | - |
| 5 | `google_news_crociere_30d` | aggregator | google_news | 200 | ok | 41 | 32 | 9 | 0 | 0 | - |
| 6 | `google_news_eventi_7d` | aggregator | google_news | 200 | ok | 62 | 61 | 1 | 0 | 0 | - |
| 7 | `google_news_viabilita` | aggregator | google_news | 200 | ok | 37 | 2 | 35 | 0 | 0 | - |
| 8 | `google_news_viabilita_7d` | aggregator | google_news | 200 | ok | 24 | 4 | 20 | 0 | 0 | - |
| 9 | `pc_campania` | civil_protection | rss | 200 | ok | 10 | 0 | 10 | 0 | 0 | - |
| 10 | `pc_campania_avvisi` | civil_protection | rss | 200 | ok | 10 | 1 | 9 | 0 | 0 | - |
| 11 | `pc_campania_bollettino` | civil_protection | rss | 200 | ok | 10 | 0 | 10 | 0 | 0 | - |
| 12 | `abc_napoli` | local_government | rss | 200 | parse_error | 0 | 0 | 0 | 0 | 0 | parsing: feed senza entry (possibile endpoint vuoto o cambiato) |
| 13 | `adsp_crociere_en` | local_government | rss | 304 | not_modified | 1 | 0 | 1 | 0 | 0 | - |
| 14 | `adsp_eventi` | local_government | rss | 304 | not_modified | 4 | 0 | 4 | 0 | 0 | - |
| 15 | `adsp_general` | local_government | rss | 304 | not_modified | 10 | 3 | 7 | 0 | 0 | - |
| 16 | `adsp_lavori` | local_government | rss | 304 | not_modified | 2 | 1 | 1 | 0 | 0 | - |
| 17 | `adsp_napoli` | local_government | rss | 304 | not_modified | 10 | 0 | 10 | 0 | 0 | - |
| 18 | `adsp_napoli_newsletter` | local_government | rss | 304 | not_modified | 10 | 0 | 10 | 0 | 0 | - |
| 19 | `adsp_news` | local_government | rss | 304 | not_modified | 7 | 2 | 5 | 0 | 0 | - |
| 20 | `adsp_ordinanze` | local_government | rss | 304 | not_modified | 10 | 4 | 6 | 0 | 0 | - |
| 21 | `adsp_press` | local_government | rss | 304 | not_modified | 10 | 3 | 7 | 0 | 0 | - |
| 22 | `cm_news` | local_government | rss | 200 | ok | 31 | 12 | 19 | 0 | 0 | - |
| 23 | `cm_press` | local_government | rss | 200 | ok | 20 | 6 | 14 | 0 | 0 | - |
| 24 | `comune_avvisi` | local_government | rss | 304 | not_modified | 9 | 1 | 8 | 0 | 0 | - |
| 25 | `comune_comunicati` | local_government | rss | 304 | not_modified | 9 | 1 | 8 | 0 | 0 | - |
| 26 | `comune_general` | local_government | rss | 200 | ok | 1 | 1 | 0 | 0 | 0 | - |
| 27 | `comune_notizie` | local_government | rss | 304 | not_modified | 9 | 0 | 9 | 0 | 0 | - |
| 28 | `regione_campania` | local_government | rss | 304 | not_modified | 50 | 8 | 42 | 0 | 0 | - |
| 29 | `ansa_campania` | local_news | rss | 200 | ok | 55 | 48 | 7 | 0 | 0 | - |
| 30 | `calcionapoli24` | local_news | rss | 200 | ok | 191 | 188 | 3 | 0 | 0 | - |
| 31 | `corriere_mezzogiorno` | local_news | rss | 404 | error | 0 | 0 | 0 | 0 | 0 | HTTP 404: <!DOCTYPE html>  		 		<!-- Timestamp: 20261115113611 -->  		 		  		 		 		     	  		 		 		 		  		 		 		<!--@ REQUEST URI :  /feed/--><!--@Conf type prd |
| 32 | `cronaca_flegrea` | local_news | rss | 200 | ok | 15 | 15 | 0 | 0 | 0 | - |
| 33 | `cronache_campania` | local_news | rss | 304 | not_modified | 20 | 8 | 12 | 0 | 0 | - |
| 34 | `fanpage_napoli` | local_news | rss | 304 | not_modified | 40 | 32 | 8 | 0 | 0 | - |
| 35 | `gazzetta_napoli` | local_news | rss | 304 | not_modified | 10 | 1 | 9 | 0 | 0 | - |
| 36 | `grande_napoli` | local_news | rss | 200 | ok | 30 | 20 | 10 | 0 | 0 | - |
| 37 | `ilmattino_napoli` | local_news | rss | 200 | ok | 20 | 16 | 4 | 0 | 0 | - |
| 38 | `internapoli` | local_news | rss | 200 | ok | 31 | 20 | 11 | 0 | 0 | - |
| 39 | `metropolisweb` | local_news | rss | 304 | not_modified | 68 | 26 | 42 | 0 | 0 | - |
| 40 | `napolitan` | local_news | rss | 304 | not_modified | 10 | 2 | 8 | 0 | 0 | - |
| 41 | `napolitoday` | local_news | rss | 200 | ok | 26 | 20 | 6 | 0 | 0 | - |
| 42 | `napolitoday_feed` | local_news | rss | 404 | error | 0 | 0 | 0 | 0 | 0 | HTTP 404: <!DOCTYPE html>



 <html lang="it" data-experiment="b"




  data-premium--available-plus









 data-context="web"  >

   |
| 43 | `pozzuoli_news24` | local_news | rss | 304 | not_modified | 10 | 7 | 3 | 0 | 0 | - |
| 44 | `tuttonapoli` | local_news | rss | 200 | ok | 20 | 20 | 0 | 0 | 0 | - |
| 45 | `vesuviolive` | local_news | rss | 304 | not_modified | 50 | 13 | 37 | 0 | 0 | - |
| 46 | `aci_comunicati` | national_context | rss | 304 | not_modified | 10 | 9 | 1 | 0 | 0 | - |
| 47 | `aci_napoli` | national_context | rss | 304 | not_modified | 2 | 0 | 2 | 0 | 0 | - |
| 48 | `aci_notizie` | national_context | rss | 304 | not_modified | 10 | 8 | 2 | 0 | 0 | - |
| 49 | `enac` | national_context | rss | 304 | not_modified | 10 | 10 | 0 | 0 | 0 | - |
| 50 | `ingv_terremoti` | national_context | atom | 200 | ok | 313 | 308 | 5 | 0 | 0 | - |
| 51 | `pc_nazionale_criticita` | national_context | rss | 200 | ok | 2 | 2 | 0 | 0 | 0 | - |
| 52 | `pc_nazionale_vigilanza` | national_context | rss | 200 | ok | 2 | 2 | 0 | 0 | 0 | - |
| 53 | `radio_traffic` | national_context | rss | 304 | not_modified | 10 | 5 | 5 | 0 | 0 | - |
| 54 | `vigilfuoco` | national_context | rss | 200 | ok | 6 | 5 | 1 | 0 | 0 | - |
| 55 | `anm_news` | official_transport | anm_scraper | 200 | ok | 57 | 7 | 50 | 0 | 0 | - |
| 56 | `cciss` | official_transport | rss | 200 | ok | 99 | 71 | 28 | 0 | 0 | - |
| 57 | `eav_access` | official_transport | rss | 200 | ok | 10 | 0 | 10 | 0 | 0 | - |
| 58 | `eav_bus` | official_transport | rss | 200 | ok | 10 | 0 | 10 | 0 | 0 | - |
| 59 | `eav_flegree` | official_transport | rss | 200 | ok | 10 | 0 | 10 | 0 | 0 | - |
| 60 | `eav_general` | official_transport | rss | 200 | ok | 10 | 0 | 10 | 0 | 0 | - |
| 61 | `eav_metro` | official_transport | rss | 200 | ok | 10 | 0 | 10 | 0 | 0 | - |
| 62 | `eav_news` | official_transport | rss | 200 | ok | 10 | 1 | 9 | 0 | 0 | - |
| 63 | `eav_plants` | official_transport | rss | 200 | ok | 10 | 0 | 10 | 0 | 0 | - |
| 64 | `eav_press` | official_transport | rss | 200 | ok | 10 | 0 | 10 | 0 | 0 | - |
| 65 | `eav_rail` | official_transport | rss | 200 | ok | 10 | 0 | 10 | 0 | 0 | - |
| 66 | `eav_strike` | official_transport | rss | 200 | ok | 10 | 0 | 10 | 0 | 0 | - |
| 67 | `eav_suburbane` | official_transport | rss | 200 | ok | 10 | 0 | 10 | 0 | 0 | - |
| 68 | `eav_svr` | official_transport | rss | 200 | ok | 10 | 4 | 6 | 0 | 0 | - |
| 69 | `eav_vesuviane` | official_transport | rss | 200 | ok | 10 | 0 | 10 | 0 | 0 | - |
| 70 | `mit_scioperi` | official_transport | rss | 200 | ok | 30 | 26 | 4 | 0 | 0 | - |
| 71 | `rfi_camp_news` | official_transport | rss | 200 | ok | 34 | 15 | 19 | 0 | 0 | - |
| 72 | `rfi_camp_notices` | official_transport | rss | 200 | ok | 42 | 20 | 22 | 0 | 0 | - |
| 73 | `rfi_camp_press` | official_transport | rss | 200 | ok | 100 | 6 | 94 | 0 | 0 | - |
| 74 | `rfi_camp_updates` | official_transport | rss | 200 | ok | 8 | 0 | 8 | 0 | 0 | - |
| 75 | `rfi_nat_notices` | official_transport | rss | 200 | ok | 100 | 94 | 6 | 0 | 0 | - |
| 76 | `rfi_nat_updates` | official_transport | rss | 200 | ok | 60 | 53 | 7 | 0 | 0 | - |
| 77 | `spn_a3` | official_transport | rss | 304 | not_modified | 10 | 6 | 4 | 0 | 0 | - |
| 78 | `campaniartecard` | tourism_culture | rss | 304 | not_modified | 10 | 10 | 0 | 0 | 0 | - |
| 79 | `capodimonte` | tourism_culture | rss | 304 | not_modified | 10 | 0 | 10 | 0 | 0 | - |
| 80 | `citta_scienza` | tourism_culture | rss | 304 | not_modified | 12 | 0 | 12 | 0 | 0 | - |
| 81 | `ercolano` | tourism_culture | rss | 200 | ok | 10 | 2 | 8 | 0 | 0 | - |
| 82 | `madre` | tourism_culture | rss | 200 | ok | 13 | 11 | 2 | 0 | 0 | - |
| 83 | `mann` | tourism_culture | rss | - | error | 0 | 0 | 0 | 0 | 0 | rete: ConnectError |
| 84 | `mostra_oltremare` | tourism_culture | rss | 304 | not_modified | 10 | 9 | 1 | 0 | 0 | - |
| 85 | `napoli_da_vivere` | tourism_culture | rss | 304 | not_modified | 10 | 5 | 5 | 0 | 0 | - |
| 86 | `napolimilionaria` | tourism_culture | rss | 304 | not_modified | 10 | 2 | 8 | 0 | 0 | - |
| 87 | `parco_vesuvio` | tourism_culture | rss | 304 | not_modified | 10 | 0 | 10 | 0 | 0 | - |
| 88 | `pompeiisites` | tourism_culture | rss | 200 | error | 0 | 0 | 0 | 0 | 0 | Content-Type non feed: text/html; charset=UTF-8 |
| 89 | `reggia_caserta` | tourism_culture | rss | 200 | ok | 10 | 0 | 10 | 0 | 0 | - |
| 90 | `teatro_san_carlo` | tourism_culture | rss | 304 | not_modified | 10 | 7 | 3 | 0 | 0 | - |
| 91 | `anm_feed` | unsupported | non_rss | - | - | 0 | 0 | 0 | 0 | 0 | - |
| 92 | `anm_rss2` | unsupported | non_rss | - | - | 0 | 0 | 0 | 0 | 0 | - |
| 93 | `gesac_feed` | unsupported | non_rss | - | - | 0 | 0 | 0 | 0 | 0 | - |
| 94 | `luceverde_feed` | unsupported | non_rss | - | - | 0 | 0 | 0 | 0 | 0 | - |
| 95 | `repubblica_napoli` | unsupported | non_rss | - | - | 0 | 0 | 0 | 0 | 0 | - |
| 96 | `trenitalia_feed` | unsupported | non_rss | - | - | 0 | 0 | 0 | 0 | 0 | - |

## Fonti con errore persistito

- `abc_napoli` — parsing: feed senza entry (possibile endpoint vuoto o cambiato)
- `corriere_mezzogiorno` — HTTP 404: <!DOCTYPE html>  		 		<!-- Timestamp: 20261115113611 -->  		 		  		 		 		     	  		 		 		 		  		 		 		<!--@ REQUEST URI :  /feed/--><!--@Conf type prd --><!--@GLOBAL CONFIG prd--><!--@ fe-include /fe-
- `napolitoday_feed` — HTTP 404: <!DOCTYPE html>



 <html lang="it" data-experiment="b"




  data-premium--available-plus









 data-context="web"  >

   <head>
    <script>
 ~function(sDomain){sDomain=s
- `mann` — rete: ConnectError
- `pompeiisites` — Content-Type non feed: text/html; charset=UTF-8

## Note

- `anm_news` usa `backend/app/services/ingestion/vendor/anm_scraper.py` (copia invariata, SHA-256 `33e44664a8f0ab30685b1d0a66631c180087e58f74cb0a859d9ac65cda2acbec`).
- Le fonti con `enabled=false` e tipo `non_rss` documentano i tentativi ANM/Trenitalia/GESAC/Luceverde/Repubblica senza creare feed inventati.
- I conteggi `pending` includono documenti in attesa del provider AI; con `LLM_MODE=off` o senza credenziali non vengono creati avvisi.
- Il secondo polling di una fonte invariata non crea nuovi documenti né nuove interpretazioni; i cambi reali del ticker/news producono una nuova revisione.
