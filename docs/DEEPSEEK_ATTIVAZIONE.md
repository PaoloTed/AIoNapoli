# Attivazione DeepSeek

Provider configurato: OpenAI-compatible, endpoint `https://api.deepseek.com`,
modello `deepseek-flash`, verificato nell'elenco modelli dell'account.

La chiave è esclusivamente in `~/.config/napoli-agentic/backend.env`, con
permessi 0600, insieme alla configurazione runtime già usata dai servizi.
Non è nel repository e non è necessaria al frontend.

API e worker sono configurati con `LLM_MODE=live`. Per applicare una nuova
chiave o modificare il modello:

```bash
systemctl --user restart napoli-api napoli-ingestion-worker
```

Il repository conserva soltanto gli esempi non sensibili. Su altre macchine
occorre fornire una chiave dedicata al backend prima di attivare `live`.

Le notizie in coda vengono interpretate dal worker secondo le lease e i
tempi di retry esistenti. L'elaborazione dell'archivio non è istantanea;
verificare avanzamento con `/api/v1/ingestion/status` e i log del worker.
