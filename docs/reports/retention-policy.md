# Retention manuale — grafi OTP e staging GTFS

Stato: **policy documentata, nessun cleanup eseguito**. Questo documento non
autorizza cancellazioni automatiche. Volumi Docker, database, schemi GTFS,
grafi correnti e precedenti non vanno rimossi senza conferma esplicita.

## 1. Cosa non si cancella mai automaticamente

- volume Docker `hackaton2026cds_postgres_data`;
- database `mobility` e schema `public`;
- schema GTFS attivo di ogni dataset (`gtfs_eav`, `gtfs_anm`);
- schema indicato come precedente nell'ultima pubblicazione;
- grafo puntato da `/home/r0x4n/otp-live`;
- directory indicata in `data/otp-rebuild/current.json` e
  `previous_version`;
- tabelle di audit `gtfs_imports`, `osm_imports`, `findings`, `decisions`;
- dati OSM (`osm_territory`, `data/osm`).

`docker compose down -v`, `DROP SCHEMA ... CASCADE`, `rm -rf` su
`/home/r0x4n/otp-graphs` e `docker system prune --volumes` sono operazioni
vietate senza approvazione.

## 2. Inventario (solo lettura)

```bash
readlink -f /home/r0x4n/otp-live
jq '{version, previous_version, graph_sha256, datasets}' \
  data/otp-rebuild/current.json

du -sh /home/r0x4n/otp-graphs/* | sort -h
ls -lt /home/r0x4n/otp-graphs | head

sg docker -c 'docker exec napoli-postgres-mobility psql -U postgres -d mobility -X -c "
  SELECT nspname
  FROM pg_namespace
  WHERE left(nspname, 5) = '"'"'gtfs_'"'"'
  ORDER BY nspname;"'
```

Controllo di coerenza prima di qualsiasi scelta:

```bash
python3 infra/otp/check_pipeline_consistency.py
```

## 3. Policy per `/home/r0x4n/otp-graphs`

- Conservare sempre il grafo live e il suo `previous_version`.
- Conservare almeno le ultime **due** build per dataset, oltre alla live.
- Conservare una build se è citata in un report, in un test o in un'indagine.
- Una build candidata alla rimozione deve essere:
  1. non puntata da `otp-live`;
  2. non presente come `version`/`previous_version` in `current.json`;
  3. più vecchia delle ultime due build;
  4. verificata con `check_pipeline_consistency.py` prima e dopo la scelta.
- Archiviare prima di rimuovere:

```bash
# Esempio: scelta manuale di una directory non live, dopo approvazione.
# Non eseguire senza sostituire <graph-old> con un path verificato.
tar -C /home/r0x4n/otp-graphs -czf \
  /home/r0x4n/otp-graphs-archive/<graph-old>.tar.gz <graph-old>
# rm -rf /home/r0x4n/otp-graphs/<graph-old>
```

La rimozione deve essere fatta una directory alla volta, con il path assoluto
ricontrollato. Non usare wildcard.

## 4. Policy per gli staging `gtfs_*_stage_*` e `gtfs_*_prev_*`

- Gli staging sono conservati dall'import per audit e non vengono cancellati
  dallo script di import.
- Conservare lo staging/previous dell'ultima importazione pubblicata.
- Conservare almeno **tre** schemi storici per dataset (`eav`, `anm`) prima di
  considerare la rimozione manuale.
- Non rimuovere uno schema mentre un import è in corso. Verificare:

```bash
sg docker -c 'docker exec napoli-postgres-mobility psql -U postgres -d mobility -X -c "
  SELECT import_id, dataset_key, status, staging_schema, target_schema, started_at
  FROM public.gtfs_imports
  ORDER BY import_id DESC LIMIT 10;"'
```

- Un `DROP SCHEMA ... CASCADE` è ammesso solo dopo conferma esplicita, dopo
  aver verificato che il nome non sia `gtfs_eav`, `gtfs_anm` o il previous
  citato da `gtfs_datasets`, e dopo un backup logico se richiesto.
- Non cancellare mai `public` o `osm_territory`.

## 5. Cosa fare in caso di divergenza

Se `check_pipeline_consistency.py` esce con codice 1:

1. non cancellare nulla;
2. conservare `current.json`, `last-result.json`, `sync.log` e il grafo live;
3. verificare `gtfs_datasets.source_sha256`, gli ZIP in
   `/home/r0x4n/otp-live/otp-data/` e `graph.obj`;
4. ricostruire in una directory separata e validare sulla porta 8081;
5. eseguire lo switch atomico solo dopo la validazione; il rollback è il
   puntamento precedente.

## 6. Registro delle operazioni

Ogni cleanup manuale futuro deve essere annotato in `docs/reports/` con:

- data e operatore;
- path/schema rimosso e dimensione;
- verifica che non fosse live/previous;
- output di `check_pipeline_consistency.py` prima e dopo;
- eventuale archivio creato.
