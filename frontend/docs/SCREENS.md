[PIANIFICATO]

# Schermate

Rotte, contenuto, dati usati, stati. Una schermata per destinatario, piu' una schermata operatore che e' anche la scena della demo.

## 1. Rotte

| Rotta | Destinatario | Scopo | Dato iniziale |
|---|---|---|---|
| `/` | tutti | scelta del punto di vista | nessuno |
| `/operator` | operatore | sala operativa: dati, regole, decisione, piano, rilevanza | `GET /api/v1/scenario/{id}` |
| `/tourist` | turista | come arrivo, cosa faccio adesso | `GET /api/v1/scenario/{id}` |
| `/citizen` | cittadino | quale servizio pubblico prendo | `GET /api/v1/scenario/{id}` |

`/` non e' una landing di marketing: e' una scelta fra tre letture dello stesso scenario. Tre card, una per destinatario, con la frase che descrive cosa si vede.

Nessuna autenticazione, nessun login, nessun profilo. Cambiare destinatario e' cambiare rotta.

## 2. Shell comune

Presente in tutte le schermate.

| Elemento | Contenuto |
|---|---|
| Intestazione | nome dello scenario, `scenario_id`, data e ora in `Europe/Rome` |
| Selettore scenario | lista chiusa da `NEXT_PUBLIC_DEMO_SCENARIO`, nessun endpoint di elenco |
| Stato del contratto | pill con `contract_version`; rossa se diversa da quella attesa dal client |
| Stato del sistema | `live` / `degraded` / `offline`, derivato dal fetch e dallo stream |
| Navigazione | tre voci: Operatore, Turista, Cittadino |

## 3. `/operator` — sala operativa

Schermata pensata per desktop, larga almeno 1280 px. E' la schermata della demo: ogni elemento corrisponde a un passo del copione in [DEMO.md](../../backend/docs/DEMO.md).

### 3.1 Layout

```
+----------------------------------------------------------------+
| intestazione: scenario - ora - stato contratto - stato sistema |
+-----------------------------+----------------------------------+
| mappa: mezzi, geo-fence,    | pannello dati                    |
| zona evidenziata            | 3 FindingCard + provenienza      |
|                             +----------------------------------+
|                             | timeline delle regole (SSE)      |
+-----------------------------+----------------------------------+
| decisione: trigger, conflitto, decision_id, ripeti              |
+----------------------------------------------------------------+
| piano: tre colonne operator / tourist / citizen                |
| rilevanza: barre per target con contributi                     |
+----------------------------------------------------------------+
```

### 3.2 Dati e componenti

| Blocco | Dato | Endpoint | Componente |
|---|---|---|---|
| mappa | `vehicle_positions`, `findings[].content.zone_id` | `GET /scenario/{id}` | `MapPanel` |
| pannello dati | `findings[]` | `GET /scenario/{id}` | `FindingCard`, `ProvenanceChip` |
| timeline | eventi SSE | `GET /scenario/{id}/stream` | `RuleTimeline` |
| decisione | `decision.trigger`, `decision.conflict`, `decision_id` | `POST /decision` | `DecisionHeader` |
| piano | `decision.plan`, `relevance.targets[*].order` | `POST /decision` | `PlanColumn` |
| rilevanza | `relevance.targets[*].items[].contributions` | `POST /decision` | `RelevanceBar` |
| reasoning log | `decision.reasoning_log` | `POST /decision` | `ReasoningList` (solo qui) |

L'operatore e' l'unico destinatario a cui il reasoning log e' mostrato (FE-REQ-21).

### 3.3 Sequenza di caricamento

1. `GET /scenario/{id}`: mappa e pannello dati compaiono subito, con scheletri.
2. `POST /decision`: si ottiene la decisione completa. L'interfaccia e' gia' utilizzabile.
3. `GET /scenario/{id}/stream`: si apre lo stream e la timeline si anima. Se lo stream fallisce, la timeline resta vuota con nota "stream non disponibile" e il resto resta valido.

La decisione si chiede prima dello stream, non dopo: se lo stream cade, la demo ha comunque una decisione da mostrare.

### 3.4 Azione "ripeti"

Un pulsante esegue di nuovo `POST /decision` e confronta i `decision_id`. Esito mostrato in una riga: `same` con il valore, oppure `diverso` con i due valori. Serve a rendere visibile il determinismo (REQ-ORC-12) senza spiegarlo a voce.

## 4. `/tourist` — turista

Schermata mobile-first. Due lingue: italiano e inglese, con selettore nella shell.

| Blocco | Contenuto |
|---|---|
| mappa compatta | posizione dell'evento, zona satura, mezzi disponibili |
| messaggio principale | `narrative.items[].texts.it` se presente, altrimenti `PlanItem.action` |
| alternativa | item del piano con `target=tourist`, ordinati per `relevance.targets.tourist.order` |
| tempo stimato | ricavato dal testo dell'azione; se assente, non si mostra una stima inventata |
| avvertenza | chip "dato simulato" su ogni informazione che poggia su un finding con `is_simulated=true` |

Non sono mostrati: `reasoning_log`, `rationale`, punteggi, identificatori interni, stato delle regole (FE-REQ-21).

Il turista vede al massimo tre azioni. Se il piano ne contiene di piu', l'interfaccia mostra le prime tre secondo `order` e una riga "altre N azioni" non espandibile in demo.

## 5. `/citizen` — cittadino

Stessa struttura del turista, contenuto diverso.

| Blocco | Contenuto |
|---|---|
| messaggio principale | item con `target=citizen`, ordine per rilevanza del cittadino |
| servizio pubblico | nome del servizio e tempo, solo se presenti nel testo dell'azione |
| stato della zona | densita' o congestione come frase, non come numero grezzo: "zona molto affollata" sopra 0.85 |

Nessun numero di confidenza, nessun identificatore, nessun reasoning log.

## 6. Stati di ogni schermata

| Stato | Quando | Cosa si vede |
|---|---|---|
| `loading` | fetch in corso | scheletri con la forma del contenuto finale, non spinner centrati |
| `ready` | dati completi | schermata piena |
| `partial` | `findings` con meno di tre elementi | i finding presenti, e per gli assenti una card "dato non disponibile" con il `reason_code` del rifiuto se noto |
| `no_rules` | `conflict.detected=false` | banner "nessuna regola scattata", piano di monitoraggio visibile, nessun errore |
| `degraded` | SSE non disponibile o fallback attivo | banner con la sorgente sostituita e chip "simulato", resto della schermata integro |
| `error` | 4xx/5xx non recuperabile | messaggio con `code`, `detail` e pulsante "riprova" |
| `contract_mismatch` | `contract_version` inattesa | banner permanente, interfaccia in sola lettura sui campi sconosciuti |
| `empty` | `scenario_not_found` | stato vuoto con lo scenario richiesto e il link agli scenari noti |

## 7. Mappa con il copione della demo

| Passo [DEMO.md](../../backend/docs/DEMO.md) | Tempo | Componente | Cosa deve essere visibile |
|---|---|---|---|
| 1 | 0-10 s | `FindingCard` x3 | fonte, `is_simulated`, timestamp, severità |
| 2 | 10-20 s | `MapPanel` | mezzi reali, orario dell'ultima posizione |
| 3 | 20-35 s | `RuleTimeline` | R1-R4 con esito e soglia |
| 4 | 35-50 s | `DecisionHeader` | conflitto e testo del conflitto |
| 5 | 50-65 s | `PlanColumn` x3 | tre piani, tre destinatari |
| 6 | 65-78 s | `RelevanceBar` | contributi per feature, differenza fra target |
| 7 | 78-90 s | `DecisionHeader` | `decision_id` e ripetizione identica |

Se un componente non e' visibile entro il tempo del passo, il passo va accorciato: il copione non si allunga per l'interfaccia.

## 8. Cosa non c'e' nel frontend

- Nessuna schermata di amministrazione.
- Nessuna configurazione delle soglie: vivono in `rules.yaml`, e l'interfaccia non le modifica.
- Nessun editor di finding: i finding arrivano dalle verticali.
- Nessuna vista di database o tabelle.
- Nessun grafico storico: lo scenario e' un istante, non una serie.
