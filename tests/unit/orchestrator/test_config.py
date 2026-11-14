"""Unit tests verifying orchestrator rule thresholds are driven by YAML config."""

from __future__ import annotations

from pathlib import Path

from app.domain.models.finding import Finding
from app.services.orchestrator.config import load_config
from app.services.orchestrator.triggers import evaluate_r1


def test_soglia_da_yaml(tmp_path: Path, demo_findings: list[Finding]) -> None:
    """REQ-ORC-07: changing rules.yaml threshold changes rule firing outcome without code edits."""
    src_dir = Path(__file__).resolve().parents[3] / "backend" / "app" / "services" / "orchestrator"
    rules_text = (src_dir / "rules.yaml").read_text(encoding="utf-8")
    rel_text = (src_dir / "relevance.yaml").read_text(encoding="utf-8")
    (tmp_path / "relevance.yaml").write_text(rel_text, encoding="utf-8")

    # With default threshold 0.85, demo density 0.91 fires R1
    (tmp_path / "rules.yaml").write_text(rules_text, encoding="utf-8")
    cfg_default = load_config(tmp_path)
    assert evaluate_r1(demo_findings, cfg_default.rules).fired is True

    # Raise threshold in YAML to 0.95 -> R1 must not fire on density 0.91
    (tmp_path / "rules.yaml").write_text(
        rules_text.replace("density_threshold_0_1: 0.85", "density_threshold_0_1: 0.95", 1),
        encoding="utf-8",
    )
    cfg_raised = load_config(tmp_path)
    assert evaluate_r1(demo_findings, cfg_raised.rules).fired is False

