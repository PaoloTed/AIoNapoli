"""E2E test verifying backward compatibility and coexistence of negotiation flags (D-20, D-21)."""

from __future__ import annotations

from datetime import datetime, timezone

from app.services.facade import BackendService
from app.services.orchestrator.config import load_config
from app.utils.clock import FixedClock


def test_negotiation_coexistence_and_retrocompatibilita() -> None:
    """Verifica che con ENABLE_NEGOTIATION=False la decisione su fixture sia identica."""
    clock = FixedClock(datetime(2026, 11, 15, 14, 0, tzinfo=timezone.utc))
    config_base = load_config()

    config_neg_on = config_base.model_copy(
        update={"enable_negotiation": True, "findings_source": "fixtures"}
    )
    config_neg_off = config_base.model_copy(
        update={"enable_negotiation": False, "findings_source": "fixtures"}
    )

    service_on = BackendService(config=config_neg_on, clock=clock)
    service_off = BackendService(config=config_neg_off, clock=clock)

    resp_on, trace_on = service_on.decide_from_request({"scenario_id": "bagnoli"})
    resp_off, trace_off = service_off.decide_from_request({"scenario_id": "bagnoli"})

    # On identical fixtures, decisions must be completely deterministic
    assert resp_on.decision_id == resp_off.decision_id
    assert resp_on.decision.trigger.rule_id == resp_off.decision.trigger.rule_id
    assert len(resp_on.decision.plan) == len(resp_off.decision.plan)
