# Consegna: frontend e backend collegati

Il frontend remoto è stato integrato su main senza conflitti. La chat pubblica
chiama `POST /api/v1/journeys`: mostra itinerari OTP, cambi, cammino, problemi
evitati, contributi degli agenti, errori e chiarimenti selezionabili. La posizione
è richiesta soltanto tramite il pulsante dedicato. Nessun fallback a itinerari
mock nella chat live. `NEXT_PUBLIC_USE_MOCKS=true` seleziona esplicitamente la
precedente chat dimostrativa.

Le API passano dal proxy Next `/api/v1/*` al backend configurato in
`BACKEND_URL` (default `http://127.0.0.1:8000`). Lasciare
`NEXT_PUBLIC_API_BASE_URL` vuoto per usare il proxy. Non servono segreti nel
frontend. La pagina operatore `/operator/situation` legge stato e ultime news
dal database attraverso le API; le mappe e schede degli scenari restano demo.

## Stato verificato

- Database Docker e OTP attivi; pipeline GTFS preservata.
- News realmente persistite, incluse news ANM dello scraper del team.
- Il worker periodico viene eseguito separatamente dall'API.
- Test ordinari backend: 186 passati, 16 skipped, 5 deselected.
- Test di catalogazione live: un documento ANM reale viene interpretato con
  risposta **mock dichiarata**, catalogato come simulato e isolato dai viaggi reali.
- Frontend: typecheck, 18 test e build di produzione.
- Browser Chromium: invio dalla chat di “Da metro Chiaiano al MANN domani
  alle 8”, visualizzazione del percorso consigliato, proxy stato news HTTP
  200, nessun errore JavaScript. Screenshot locale:
  `/tmp/napoli-delivery/frontend-live.png`.
- Prova API reale Chiaiano → MANN: due itinerari, trace Mobility/Imprevisti/
  orchestratore. L'Input dichiara il parser deterministico.

**Limite ancora aperto:** mancano le credenziali del provider AI. Le news vengono
scaricate e conservate ma quelle rilevanti restano pending/needs_review senza
interpretazione live. Le perturbazioni reali non possono essere dichiarate
complete. La UI mostra la copertura incompleta e l'uso del parser locale.
Configurare `LLM_MODE=live`, `LLM_PROVIDER=openai_compatible`, `LLM_BASE_URL`,
`LLM_API_KEY`, `LLM_MODEL` secondo `BACKEND_RUNBOOK.md`, poi riavviare API e
worker e recuperare i job sospesi con gli strumenti ingestion. Non commettere
credenziali. Nessuna credenziale di OpenCode è stata riutilizzata.

## Avvio standard

Backend: impostare le variabili PostgreSQL/OTP del runbook, poi:

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Worker, con la stessa configurazione del backend:

```bash
python -m app.cli ingestion run --interval 30
```

Frontend, da `frontend/` con Node 22+:

```bash
npm ci
npm run build
npm start
```

Aprire `http://localhost:3000`. API dirette: `http://127.0.0.1:8000/docs`.

## Sessione di consegna su questa macchina

Servizi utente: `napoli-api`, `napoli-ingestion-worker`, `napoli-frontend`.
Configurazione backend privata, fuori Git:
`~/.config/napoli-agentic/backend.env` (permessi 0600). Le unità di questa
sessione sono transitorie; per un'installazione persistente usare il runbook.

```bash
systemctl --user status napoli-api napoli-ingestion-worker napoli-frontend
journalctl --user -u napoli-api -n 30
systemctl --user stop napoli-api napoli-ingestion-worker napoli-frontend
```

Non arrestare/cancellare il volume database per riavviare l'applicazione.
