"""Unit tests for target-specific RelevanceScore computation and decomposition."""

from __future__ import annotations

from pathlib import Path

from app.domain.models.config import AppConfig
from app.domain.models.decision import PlanTarget
from app.domain.models.finding import Finding
from app.services.orchestrator.config import load_config
from app.services.orchestrator.pipeline import run_pipeline
from app.services.orchestrator.relevance import score_relevance
from app.utils.clock import FixedClock


def test_tre_punteggi(
    demo_findings: list[Finding],
    app_config: AppConfig,
    fixed_clock: FixedClock,
) -> None:
    """REQ-REL-01: every plan item receives a score for operator, tourist, and citizen."""
    out = run_pipeline(demo_findings, app_config, clock=fixed_clock)
    assert set(out.relevance.targets.keys()) == set(PlanTarget)
    n_items = len(out.decision.plan)
    for target in PlanTarget:
        t_rel = out.relevance.targets[target]
        assert len(t_rel.items) == n_items
        assert sorted(t_rel.order) == list(range(n_items))


def test_range_e_determinismo(
    demo_findings: list[Finding],
    app_config: AppConfig,
    fixed_clock: FixedClock,
) -> None:
    """REQ-REL-02: relevance scores are deterministic and bounded in [0, 1]."""
    out = run_pipeline(demo_findings, app_config, clock=fixed_clock)
    r1 = score_relevance(out.decision, demo_findings, app_config.relevance)
    r2 = score_relevance(out.decision, demo_findings, app_config.relevance)
    assert r1.model_dump() == r2.model_dump()
    for target_rel in r1.targets.values():
        for scored in target_rel.items:
            assert 0.0 <= scored.score <= 1.0


def test_peso_da_yaml(
    tmp_path: Path,
    demo_findings: list[Finding],
    fixed_clock: FixedClock,
) -> None:
    """REQ-REL-03: changing weights in relevance.yaml alters scores without code edits."""
    src_dir = Path(__file__).resolve().parents[3] / "backend" / "app" / "services" / "orchestrator"
    (tmp_path / "rules.yaml").write_text(
        (src_dir / "rules.yaml").read_text(encoding="utf-8"), encoding="utf-8"
    )
    rel_text = (src_dir / "relevance.yaml").read_text(encoding="utf-8")
    (tmp_path / "relevance.yaml").write_text(rel_text, encoding="utf-8")
    cfg1 = load_config(tmp_path)
    out1 = run_pipeline(demo_findings, cfg1, clock=fixed_clock)

    modified = """rounding: 4
filter_threshold: null

features:
  - name: severity_score
    type: float
  - name: confidence
    type: float
  - name: affects_public_service
    type: binary
  - name: priority_rank
    type: float
  - name: affects_route
    type: binary
  - name: time_to_event
    type: float

weights:
  operator:
    severity_score: 0.10
    confidence: 0.10
    affects_public_service: 0.70
    priority_rank: 0.10
  tourist:
    affects_route: 0.35
    time_to_event: 0.30
    severity_score: 0.20
    confidence: 0.15
  citizen:
    affects_public_service: 0.40
    affects_route: 0.25
    severity_score: 0.20
    confidence: 0.15
"""
    (tmp_path / "relevance.yaml").write_text(modified, encoding="utf-8")
    cfg2 = load_config(tmp_path)
    out2 = run_pipeline(demo_findings, cfg2, clock=fixed_clock)
    assert (
        out1.relevance.targets[PlanTarget.OPERATOR] != out2.relevance.targets[PlanTarget.OPERATOR]
    )


def test_ordini_diversi(
    demo_findings: list[Finding],
    app_config: AppConfig,
    fixed_clock: FixedClock,
) -> None:
    """REQ-REL-04: operator, tourist, and citizen rank the same demo items in distinct orders."""
    out = run_pipeline(demo_findings, app_config, clock=fixed_clock)
    op_order = tuple(out.relevance.targets[PlanTarget.OPERATOR].order)
    tour_order = tuple(out.relevance.targets[PlanTarget.TOURIST].order)
    cit_order = tuple(out.relevance.targets[PlanTarget.CITIZEN].order)
    assert len({op_order, tour_order, cit_order}) == 3


def test_scomposizione(
    demo_findings: list[Finding],
    app_config: AppConfig,
    fixed_clock: FixedClock,
) -> None:
    """REQ-REL-06: every score equals the rounded sum of its feature contributions."""
    out = run_pipeline(demo_findings, app_config, clock=fixed_clock)
    rounding = out.relevance.rounding
    for target_rel in out.relevance.targets.values():
        for scored in target_rel.items:
            assert scored.contributions
            total = round(sum(c.contribution for c in scored.contributions), rounding)
            assert total == scored.score
