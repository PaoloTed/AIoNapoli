"""Unit tests verifying fail-fast configuration loading on invalid files/values."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.orchestrator.config import ConfigInvalidError, load_config


def test_fail_fast(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """NFR-05: malformed YAML, missing files, or invalid thresholds fail fast at load time."""
    # Missing files in empty directory
    with pytest.raises(ConfigInvalidError) as exc_missing:
        load_config(tmp_path)
    assert exc_missing.value.code == "config_invalid"

    # Malformed YAML syntax
    (tmp_path / "rules.yaml").write_text("r1: [broken\n", encoding="utf-8")
    (tmp_path / "relevance.yaml").write_text("rounding: 4\n", encoding="utf-8")
    with pytest.raises(ConfigInvalidError) as exc_yaml:
        load_config(tmp_path)
    assert exc_yaml.value.code == "config_invalid"

    # Out-of-range density threshold (> 1.0)
    (tmp_path / "rules.yaml").write_text(
        """
r1:
  density_threshold_0_1: 1.5
  severity_min: high
monitoring_text:
  operator: op
  tourist: tr
  citizen: ct
""",
        encoding="utf-8",
    )
    with pytest.raises(ConfigInvalidError) as exc_range:
        load_config(tmp_path)
    assert exc_range.value.code == "config_invalid"
    assert exc_range.value.field == "rules.yaml"

    # Invalid environment variable with valid YAML dir
    monkeypatch.setenv("APP_PROFILE", "invalid_profile")
    with pytest.raises(ConfigInvalidError) as exc_env:
        load_config()
    assert exc_env.value.code == "config_invalid"
    assert exc_env.value.field == "env"

