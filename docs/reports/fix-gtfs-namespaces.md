# Correzione riferimenti ANM/EAV — 2026-11-15

## Problema

Le chiavi `gtfs:route:<id>`, `gtfs:trip:<id>` e `gtfs:stop:<id>` non
includevano il dataset. La sincronizzazione di ANM poteva sovrascrivere un
riferimento EAV con lo stesso ID originale. Il repository cercava prima il
riferimento globale e controllava sempre i calendari nello schema EAV.

## Correzione

- Chiavi `gtfs:<dataset_key>:<tipo>:<id>`, uguali in SQL e repository.
- `DisruptionLinkInput.dataset_key` seleziona il feed prima della ricerca.
  L'omissione mantiene il default configurato nel repository, non effettua
  una ricerca trasversale. Per ANM specificare `anm`.
- `find_applicable(..., dataset_key="anm")` seleziona soltanto ANM.
- Le verifiche di calendario risolvono lo schema da `gtfs_datasets` per il
  dataset richiesto, con identificatore SQL validato e valori parametrizzati.
- Identità distinte anche per link non risolti appartenenti a feed diversi.
- Migrazione 005: conversione delle chiavi, FK con `ON UPDATE CASCADE`,
  aggiornamento dei link operativi e vincolo CHECK sul formato delle chiavi.
  Lo storico JSON delle revisioni resta invariato. Un vecchio link con
  dataset discordante resta conservato, ma viene marcato non risolto.
- Script di sincronizzazione aggiornato sia nel repository sia nel container
  attivo (`/usr/local/share/sync-gtfs-refs.sql`). Le future immagini devono
  essere costruite dai sorgenti aggiornati, come previsto dal Dockerfile.

## Verifica sul database Docker

Database `mobility`, container `napoli-postgres-mobility`. La migrazione 005
risulta registrata e i cataloghi dei due feed risultano sincronizzati.

| Dataset | Route | Stop | Trip |
|---|---:|---:|---:|
| ANM | 112 | 2.392 | 32.177 |
| EAV | 124 | 4.208 | 7.415 |

Esempio reale di collisione risolta: esistono contemporaneamente
`gtfs:anm:stop:6238` e `gtfs:eav:stop:6238`.

Tutti i 10 link esistenti sono presenti e risolti; nessuna FK orfana o
discordanza tra dataset del link e dataset dell'entità. Il catalogo EAV
contiene nuovamente tutte le 11.747 entità (prima della ricostruzione erano
11.744), mantenendo le 34.681 entità ANM.

Durante l'intervento anche l'integrazione ANM esterna ha aggiornato il
repository e il database: all'esecuzione finale del runner la migrazione
risultava già applicata. Le evidenze qui dichiarate sono le verifiche finali
eseguite, non l'attribuzione esclusiva di ogni scrittura concorrente.

## Test eseguiti

- 12 test mirati offline: chiavi per route/trip/stop, selezione dataset,
  calendari, link non risolti e migrazioni SQLite.
- 7 test PostgreSQL: due nuove regressioni in schemi temporanei isolati e
  cinque test esistenti delle perturbazioni. Verificati migrazione legacy,
  conservazione ID dei link e audit, collisioni per tutti i tipi GTFS,
  refresh ripetuto e ricerca delle perturbazioni separata per dataset.
- Suite ordinaria: **129 passed, 12 skipped**, 3 warning, fuori dal sandbox.
  I test PostgreSQL opt-in sono stati eseguiti separatamente come sopra.
- Ruff sui file Python interessati: nessun errore; `bash -n` importatore GTFS
  superato. Nel sandbox la suite si arresta all'avvio del TestClient AnyIO;
  l'esecuzione fuori dal sandbox completa in meno di un secondo.

Comandi principali:

```bash
/home/r0x4n/otp-1b-venv-pyproject/bin/python -m pytest -q
```

Per le verifiche PostgreSQL impostare `DISRUPTION_TEST_DATABASE_URL` in modo
sicuro ed eseguire `tests/db/test_disruption_namespaces_postgres.py` e
`tests/db/test_disruptions_postgres.py` con socket consentiti. Le nuove prove
creano e rimuovono soltanto schemi temporanei `test_namespaces_*`.

## Limiti

Questo intervento corregge identità e persistenza dei riferimenti delle
perturbazioni; non implementa scraping, matching geografico automatico,
agenti o ricalcolo delle strade chiuse. Nessun commit creato.
