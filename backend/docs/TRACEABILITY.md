[PIANIFICATO]

# Tracciabilita'

Matrice che collega ogni requisito a un componente e a un test. Un requisito senza test e' un'intenzione. Un test senza requisito e' codice non necessario.

La matrice si compila in due tempi: la colonna componente alla scrittura del codice, la colonna test eseguendo la suite. Una riga con il test vuoto e' un requisito non ancora coperto.

## 1. Contratti

| Requisito | Componente | Test |
|---|---|---|
| REQ-CONTR-01 | `shared/schemas/finding.py` | `tests/contracts/test_finding_schema.py::test_nove_campi` |
| REQ-CONTR-02 | `shared/schemas/decision.py` | `tests/contracts/test_decision_schema.py::test_sei_campi` |
| REQ-CONTR-03 | `shared/schemas/finding.py` | `tests/contracts/test_finding_schema.py::test_content_libero` |
| REQ-CONTR-04 | `shared/schemas/finding.py` | `tests/contracts/test_finding_schema.py::test_type_incoerente` |
| REQ-CONTR-05 | `shared/schemas/enums.py` | `tests/contracts/test_enums.py::test_severity` |
| REQ-CONTR-06 | `shared/schemas/enums.py` | `tests/contracts/test_enums.py::test_rule_id` |
| REQ-CONTR-07 | `shared/schemas/enums.py` | `tests/contracts/test_enums.py::test_target` |
| REQ-CONTR-08 | `domain/logic/refs.py` | `tests/unit/test_refs.py::test_finding_ref_stabile` |

## 2. Agenti

| Requisito | Componente | Test |
|---|---|---|
| REQ-AGT-01 | `services/agents/*/agent.py` | `tests/unit/agents/test_contract.py::test_finding_o_refusal` |
| REQ-AGT-02 | `services/agents/mobility/agent.py` | `tests/unit/agents/test_mobility.py::test_rifiuto_senza_gtfs` |
| REQ-AGT-03 | `services/agents/mobility/agent.py` | `tests/unit/agents/test_mobility.py::test_rifiuto_punto_non_mappato` |
| REQ-AGT-04 | `services/agents/crowding/agent.py` | `tests/unit/agents/test_crowding.py::test_rifiuto_senza_occupancy` |
| REQ-AGT-05 | `services/agents/crowding/agent.py` | `tests/unit/agents/test_crowding.py::test_rifiuto_senza_geofence` |
| REQ-AGT-06 | `services/agents/context/agent.py` | `tests/unit/agents/test_context.py::test_rifiuto_senza_allerta` |
| REQ-AGT-07 | struttura dei package | `tests/architecture/test_layers.py::test_agenti_isolati` |
| REQ-AGT-08 | struttura dei package | `tests/architecture/test_layers.py::test_agenti_solo_repository` |

## 3. Orchestratore

| Requisito | Componente | Test |
|---|---|---|
| REQ-ORC-01 | `orchestrator/triggers.py` | `tests/unit/orchestrator/test_triggers.py::test_r1` |
| REQ-ORC-02 | `orchestrator/triggers.py` | `tests/unit/orchestrator/test_triggers.py::test_r2` |
| REQ-ORC-03 | `orchestrator/triggers.py` | `tests/unit/orchestrator/test_triggers.py::test_r3` |
| REQ-ORC-04 | `orchestrator/triggers.py` | `tests/unit/orchestrator/test_triggers.py::test_r4` |
| REQ-ORC-05 | `orchestrator/triggers.py` | `tests/unit/orchestrator/test_triggers.py::test_finding_parziali` |
| REQ-ORC-06 | `orchestrator/reasoning.py` | `tests/unit/orchestrator/test_reasoning.py::test_regola_non_scattata` |
| REQ-ORC-07 | `orchestrator/config.py` | `tests/unit/orchestrator/test_config.py::test_soglia_da_yaml` |
| REQ-ORC-08 | `orchestrator/priorities.py` | `tests/unit/orchestrator/test_conflicts.py::test_priorita` |
| REQ-ORC-09 | `orchestrator/reasoning.py` | `tests/unit/orchestrator/test_reasoning.py::test_contiguo_e_corto` |
| REQ-ORC-10 | `orchestrator/plan.py` | `tests/unit/orchestrator/test_plan.py::test_tre_target` |
| REQ-ORC-11 | `orchestrator/plan.py` | `tests/unit/orchestrator/test_plan.py::test_nessun_log_ai_target` |
| REQ-ORC-12 | `orchestrator/pipeline.py` | `tests/unit/orchestrator/test_pipeline.py::test_determinismo` |
| REQ-ORC-13 | `orchestrator/pipeline.py` | `tests/unit/orchestrator/test_pipeline.py::test_nessuna_regola` |

## 4. Rilevanza

| Requisito | Componente | Test |
|---|---|---|
| REQ-REL-01 | `orchestrator/relevance.py` | `tests/unit/orchestrator/test_relevance.py::test_tre_punteggi` |
| REQ-REL-02 | `orchestrator/relevance.py` | `tests/unit/orchestrator/test_relevance.py::test_range_e_determinismo` |
| REQ-REL-03 | `orchestrator/relevance.yaml` | `tests/unit/orchestrator/test_relevance.py::test_peso_da_yaml` |
| REQ-REL-04 | `orchestrator/relevance.py` | `tests/unit/orchestrator/test_relevance.py::test_ordini_diversi` |
| REQ-REL-05 | `shared/schemas/decision.py` | `tests/contracts/test_decision_schema.py::test_senza_relevance` |
| REQ-REL-06 | `orchestrator/relevance.py` | `tests/unit/orchestrator/test_relevance.py::test_scomposizione` |

## 5. API

| Requisito | Componente | Test |
|---|---|---|
| REQ-API-01 | `api/v1/findings.py` | `tests/integration/test_api_findings.py::test_valido_200` |
| REQ-API-02 | `api/middleware/errors.py` | `tests/integration/test_api_findings.py::test_density_422` |
| REQ-API-03 | `api/v1/findings.py` | `tests/integration/test_api_findings.py::test_agent_mismatch` |
| REQ-API-04 | `api/v1/decisions.py` | `tests/integration/test_api_decisions.py::test_end_to_end` |
| REQ-API-05 | `api/middleware/errors.py` | `tests/integration/test_api_errors.py::test_mai_500` |
| REQ-API-06 | `api/v1/scenarios.py` | `tests/integration/test_api_stream.py::test_ordine_eventi` |
| REQ-API-07 | struttura degli endpoint | `tests/architecture/test_layers.py::test_api_senza_dominio` |
| REQ-API-08 | `api/middleware/errors.py` | `tests/integration/test_api_findings.py::test_rifiuto_non_500` |

## 6. Persistenza

| Requisito | Componente | Test |
|---|---|---|
| REQ-PER-01 | `db/migrations.py` | `tests/db/test_migrations.py::test_da_zero` |
| REQ-PER-02 | `database/migrations/001_init.sql` | `tests/db/test_schema.py::test_tracciabilita_riga` |
| REQ-PER-03 | `repositories/*` | `tests/db/test_repositories.py::test_due_implementazioni` |
| REQ-PER-04 | struttura dei package | `tests/architecture/test_layers.py::test_driver_isolati` |
| REQ-PER-05 | `repositories/*` | `tests/db/test_idempotenza.py::test_doppia_ingestion` |
| REQ-PER-06 | `repositories/audit.py` | `tests/db/test_audit.py::test_finding_e_decisione` |

## 7. Connettori

| Requisito | Componente | Test |
|---|---|---|
| REQ-CONN-01 | `connectors/base.py` | `tests/unit/connectors/test_interface.py::test_cinque_connettori` |
| REQ-CONN-02 | `connectors/base.py` | `tests/unit/connectors/test_interface.py::test_esito` |
| REQ-CONN-03 | struttura dei connettori | `tests/architecture/test_layers.py::test_connettori_senza_finding` |
| REQ-CONN-04 | `connectors/*` | `tests/unit/connectors/test_fallback.py::test_flag_coerente` |
| REQ-CONN-05 | `connectors/rss/derivation.py` | `tests/unit/connectors/test_rss.py::test_severity_confidence` |
| REQ-CONN-06 | `connectors/rss/parser.py` | `tests/unit/connectors/test_rss.py::test_pubdate_non_build` |
| REQ-CONN-07 | `connectors/rss/parser.py` | `tests/unit/connectors/test_rss.py::test_mattino_e_date_italiane` |
| REQ-CONN-08 | struttura dei connettori | `tests/architecture/test_layers.py::test_connettori_senza_soglie` |

## 8. Degradazione

| Requisito | Componente | Test |
|---|---|---|
| REQ-DEG-01 | demo e fixture | `tests/e2e/test_offline.py::test_senza_rete` |
| REQ-DEG-02 | `orchestrator/narrative.py` | `tests/unit/orchestrator/test_narrative.py::test_llm_off` |
| REQ-DEG-03 | `agents/mobility/agent.py` | `tests/unit/agents/test_mobility.py::test_otp_spento` |
| REQ-DEG-04 | selezione del profilo | `tests/integration/test_profiles.py::test_memory_senza_db` |
| REQ-DEG-05 | `assumptions.md` | `tests/contracts/test_assumptions.py::test_simulazioni_dichiarate` |

## 9. Non funzionali

| Requisito | Componente | Test |
|---|---|---|
| NFR-01 | `utils/canonical.py` | `tests/unit/test_canonical.py::test_hash_stabile` |
| NFR-02 | `domain/` | `tests/architecture/test_layers.py::test_core_senza_dipendenze` |
| NFR-03 | pipeline | `tests/e2e/test_performance.py::test_entro_due_secondi` |
| NFR-04 | `main.py` | `tests/e2e/test_startup.py::test_entro_tre_secondi` |
| NFR-05 | `orchestrator/config.py` | `tests/unit/test_config_invalid.py::test_fail_fast` |
| NFR-06 | `api/middleware/errors.py` | `tests/integration/test_api_errors.py::test_codici` |
| NFR-07 | repository | `tests/e2e/test_hygiene.py::test_nessun_segreto` |
| NFR-08 | `pyproject.toml` | `tests/e2e/test_offline.py::test_rete_inibita` |
| NFR-09 | suite del dominio | `tests/unit/test_determinismo.py::test_ogni_modulo` |
| NFR-10 | `DEMO.md` | revisione manuale, esito registrato in `DEMO.md` |

## 10. Stato della copertura

| Area | Requisiti | Coperti | Stato |
|---|---|---|---|
| Contratti | 8 | 0 | da implementare |
| Agenti | 8 | 0 | da implementare |
| Orchestratore | 13 | 0 | da implementare |
| Rilevanza | 6 | 0 | da implementare |
| API | 8 | 0 | da implementare |
| Persistenza | 6 | 0 | da implementare |
| Connettori | 8 | 0 | da implementare |
| Degradazione | 5 | 0 | da implementare |
| Non funzionali | 10 | 0 | da implementare |
| **Totale** | **72** | **0** | |

La tabella si aggiorna a ogni area completata, nello stesso commit del codice. Una riga che resta a zero senza motivo e' un allarme: significa che il codice e' stato scritto senza test, oppure che il requisito non e' raggiungibile.

## 11. Regola di uso

Questo file e' il contratto tra chi scrive codice e chi verifica. Le tre domande a cui risponde:

1. quale requisito sto coprendo con questo file di codice?
2. quale test dimostra che il requisito e' coperto?
3. quale requisito non e' ancora coperto?

Se la risposta alla prima domanda manca, il codice non serve. Se manca la seconda, il requisito non e' chiuso. Se la terza ha troppe voci vicine alla demo, lo scope va tagliato.
