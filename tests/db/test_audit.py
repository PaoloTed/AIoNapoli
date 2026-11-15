"""Audit persistence tests verifying Findings and Decisions are stored with content hashes."""

from __future__ import annotations

from app.db.migrations import apply_migrations
from app.db.session import get_sqlite_connection
from app.domain.logic.refs import compute_finding_ref
from app.domain.models.config import AppConfig
from app.domain.models.finding import Finding
from app.repositories.audit import InMemoryAuditStore, PostgresAuditStore
from app.services.orchestrator.pipeline import run_pipeline
from app.utils.clock import FixedClock


def test_finding_e_decisione(
    demo_findings: list[Finding],
    app_config: AppConfig,
    fixed_clock: FixedClock,
) -> None:
    """REQ-PER-06: every evaluated Finding and Decision is stored by finding_ref and decision_id."""
    out = run_pipeline(demo_findings, app_config, clock=fixed_clock)
    conn = get_sqlite_connection(":memory:")
    try:
        apply_migrations(conn)
        stores = (InMemoryAuditStore(), PostgresAuditStore(conn))
        for store in stores:
            for f in demo_findings:
                f_ref = compute_finding_ref(f)
                store.save_finding(f, f_ref)
                # Verify idempotent re-save does not duplicate
                store.save_finding(f, f_ref)
                assert store.get_finding(f_ref) is not None

            assert len(store.list_findings()) == len(demo_findings)

            store.save_decision(out.decision, out.decision_id)
            store.save_decision(out.decision, out.decision_id)
            stored_dec = store.get_decision(out.decision_id)
            assert stored_dec is not None
            assert stored_dec["decision_id"] == out.decision_id
            assert len(store.list_decisions()) == 1
    finally:
        conn.close()
