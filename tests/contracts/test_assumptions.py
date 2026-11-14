"""Contract test checking every simulated source is declared in assumptions.md."""

from __future__ import annotations

import json
from pathlib import Path


def test_simulazioni_dichiarate() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    assumptions_text = (repo_root / "assumptions.md").read_text(encoding="utf-8").lower()
    scenarios = json.loads(
        (repo_root / "shared" / "mocks" / "scenarios.json").read_text(encoding="utf-8")
    )["scenarios"]

    source_keywords = {
        "ir_sensors": "occupazione",
        "open_meteo": "meteo",
        "events_dataset": "eventi",
        "otp_fixture": "opentripplanner",
        "anm": "proxy",
    }

    for scenario in scenarios.values():
        for finding in scenario.get("findings", []):
            if finding.get("is_simulated"):
                src = finding["source_id"]
                assert src in source_keywords, f"Sorgente simulata non mappata: {src}"
                assert source_keywords[src] in assumptions_text, (
                    f"Simulazione per '{src}' non dichiarata in assumptions.md"
                )

