# ANM News Scraper

Scraper delle notizie ANM in JSON pulito.

ANM non pubblica un feed RSS né una API REST documentata per le notizie. La pagina
[Notizia Home](https://www.anm.it/s/notizia-home/Notizia_Home__c/Default?language=it)
è una Salesforce Experience Cloud app: elenco e corpi degli articoli arrivano da due
azioni Aura/Apex pubbliche.

Lo script chiama gli stessi endpoint, normalizza i campi Salesforce e gestisce in modo
esplicito errori di rete, HTTP, protocollo, sessione Aura e singoli articoli.

## Installazione

```bash
python3 -m pip install -r requirements-anm.txt
# oppure: python3 -m pip install requests beautifulsoup4
```

## Uso

```bash
# Tutte le notizie, con corpo completo
python3 anm_scraper.py --output anm_news.json

# Solo elenco e sintesi (nessuna richiesta di dettaglio)
python3 anm_scraper.py --no-details --output anm_news.json

# Ultime 10 notizie
python3 anm_scraper.py --limit 10

# Solo notizie dal 1 novembre 2026
python3 anm_scraper.py --since 2026-11-01

# JSON compatto su stdout
python3 anm_scraper.py --output - --compact
```

Opzioni principali:

| Opzione | Default | Descrizione |
|---|---|---|
| `-o, --output` | `anm_news.json` | File di uscita; `-` per stdout |
| `--limit` | tutte | Numero massimo di articoli |
| `--since` | nessuno | Filtra per data `YYYY-MM-DD` |
| `--no-details` | off | Non scarica il corpo completo |
| `--workers` | `3` | Richieste di dettaglio in parallelo (max 8) |
| `--delay` | `0.2` | Intervallo minimo globale tra richieste, in secondi |
| `--timeout` | `20` | Timeout per richiesta, in secondi |
| `--retries` | `3` | Tentativi aggiuntivi su errori transitori |
| `--user-agent` | identificabile | User-Agent inviato al sito |
| `--compact` | off | JSON senza indentazione |
| `--allow-empty` | off | Non considera un elenco vuoto un errore |
| `-v, --verbose` | off | Log dettagliato |
| `-q, --quiet` | off | Solo errori |

## Struttura del JSON

```json
{
  "meta": {
    "source": "ANM",
    "source_legal_name": "ANM S.p.A.",
    "source_url": "https://www.anm.it/s/notizia-home/Notizia_Home__c/Default?language=it",
    "scraper": "anm_scraper.py",
    "scraper_version": "1.0.0",
    "scraped_at": "2026-11-14T18:58:12+01:00",
    "timezone": "Europe/Rome",
    "method": "Salesforce Experience Cloud Aura/Apex action",
    "listed_count": 57,
    "exported_count": 57,
    "details_requested": true,
    "details_ok": 57,
    "details_failed": 0,
    "errors_count": 0,
    "warnings_count": 0,
    "duration_seconds": 12.5,
    "filters": {"since": null, "limit": null}
  },
  "articles": [
    {
      "id": "a0gR200000Tgr0oIAB",
      "title": "VARIAZIONI AL SERVIZIO ...",
      "title_en": "SURFACE TRANSPORT SERVICE CHANGES ...",
      "date": "2026-11-12",
      "summary": "Per lo svolgimento della manifestazione ...",
      "summary_en": "For the purpose of ...",
      "body_html": "<p>Anm informa ...</p>",
      "body_text": "Anm informa ...",
      "body_html_en": "<p>ANM informs ...</p>",
      "body_text_en": "ANM informs ...",
      "images": [],
      "url": "https://www.anm.it/s/notizia-home/a0gR.../slug?language=it",
      "categories": ["bus", "evento", "servizio"],
      "source": "ANM",
      "body_source": "detail",
      "detail_error": null
    }
  ],
  "errors": []
}
```

Campi articolo:

| Campo | Note |
|---|---|
| `id` | Id Salesforce del record |
| `title`, `title_en` | Titolo italiano e, se disponibile, inglese |
| `date` | Data di pubblicazione ANM in formato `YYYY-MM-DD` |
| `summary`, `summary_en` | Sintesi |
| `body_html`, `body_text` | Corpo completo ripulito da script/iframe e attributi pericolosi |
| `body_html_en`, `body_text_en` | Corpo inglese, se presente |
| `images` | URL assoluti delle immagini nel corpo |
| `url` | URL canonico dell'articolo |
| `categories` | Categorie euristiche: `sciopero`, `metro`, `bus`, `tram`, `alibus`, `accessibilita`, `meteo`, `evento`, `lavori`, `tariffe`, `parcheggio`, `servizio`, `altro` |
| `body_source` | `detail`, `summary` o `unavailable` |
| `detail_error` | Errore del singolo dettaglio, se presente |

Gli articoli sono ordinati per data decrescente.

## Errori ed exit code

| Exit | Significato |
|---|---|
| `0` | Successo completo |
| `1` | Errore fatale: nessun JSON scritto (es. rete assente, endpoint cambiato) |
| `2` | Successo parziale: JSON scritto, ma uno o più dettagli/list record sono falliti |
| `130` | Interrotto con Ctrl-C |

Comportamento:

- retry con backoff esponenziale e jitter su timeout, errori di connessione,
  HTTP `408`, `425`, `429`, `500`, `502`, `503`, `504`;
- rispetto dell'header `Retry-After`;
- se il contesto Aura scade, viene rifatto il bootstrap e la chiamata viene ripetuta una volta;
- se un dettaglio fallisce, l'articolo resta nel JSON con `body_source: "summary"` e
  l'errore viene registrato in `errors`, senza interrompere gli altri;
- se il bootstrap dinamico non riesce, vengono usati `fwuid` e versione applicativa
  incorporati come fallback (possono essere superati dopo un aggiornamento del sito);
- la scrittura del file è atomica: un errore non lascia JSON troncati;
- il rate limit globale evita raffiche di richieste.

Il campo `errors` distingue `severity: "error"` e `severity: "warning"`. Solo gli errori
producono exit code `2`; gli avvisi (es. data mancante durante `--since`) non bloccano.

## Test

```bash
# Test unitari (senza rete)
python3 -m unittest -v test_anm_scraper.py

# Test unitari + test live contro il sito ANM
ANM_LIVE_TEST=1 python3 -m unittest -v test_anm_scraper.py
```

I test live verificano elenco, date, URL e recupero del corpo completo.

## Note operative

- Il sito consente `/s/` in `robots.txt`; lo script usa uno User-Agent identificabile e
  un rate limit conservativo.
- Gli endpoint Aura/Apex sono interni al sito e possono cambiare senza preavviso. In caso
  di errore fatale, controllare `source_url` e i nomi delle azioni in `anm_scraper.py`.
- Le categorie sono euristiche, non una classificazione editoriale ufficiale.
- La data è quella pubblicata da ANM (`Data__c`), non un timestamp di evento.
