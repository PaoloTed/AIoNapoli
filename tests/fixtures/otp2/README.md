# OTP 2.10.0 payload fixtures

Questi file sono payload JSON registrati dalla release OTP 2.10.0 avviata nel
CHECKPOINT 1A (feed EAV `1`, data di prova `2026-11-16`) e usati dai test
offline del client OTP2.

| File | Origine |
|---|---|
| `plan_baseline_b.json` | caso B Napoli P. Garibaldi → Torre Annunziata, 6 itinerari |
| `plan_excluded_b.json` | stesso caso, esclusione route `1:1`, 4 itinerari |
| `no_route_a.json` | caso A Piscinola → Aversa, esclusione `1:2`, nessun itinerario transit |
| `graphql_error.json` | errore GraphQL reale `CoordinateValue!` con HTTP 200 |
| `plan_with_warning.json` | `plan_baseline_b.json` con un `routingErrors` aggiunto per esercitare il percorso "itinerari utilizzabili + avvisi"; la forma del payload è quella della release |

Le richieste per `plan_baseline_b`, `plan_excluded_b` e `no_route_a` sono in
`$OTP_WORK/probe-artifacts-1b-final/` e si rigenerano con
`infra/otp/probe.py`. La richiesta/risposta `graphql_error` è in
`$OTP_WORK/artifacts/baseline-float-error-{request,response}.json`.
Il fixture con warning è costruito nel test, non è una risposta OTP originale.
