"""Registry parser, validator, and loader for multi-agent topology.

Defined in implementations/01_agenti_negoziazione/02_architettura_agentica.md §4.
"""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field

DEFAULT_REGISTRY_PATH = Path(__file__).parent / "registry.yaml"


class AgentEntryConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    supervisor: str = Field(min_length=1)
    workers: list[str] = Field(default_factory=list)
    emits_finding: str = Field(min_length=1)
    priority: str = Field(min_length=2)


class RegistryConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = Field(ge=1)
    order: list[str] = Field(min_length=1)
    agents: dict[str, AgentEntryConfig] = Field(min_length=1)


def load_registry(path: Path | None = None) -> RegistryConfig:
    """Load and validate registry.yaml against Pydantic schema."""
    target_path = path or DEFAULT_REGISTRY_PATH
    if not target_path.exists():
        raise FileNotFoundError(f"Registry file not found at {target_path}")

    raw = yaml.safe_load(target_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("Invalid registry.yaml: expected mapping at root")

    return RegistryConfig.model_validate(raw)


def resolve_symbol(import_spec: str) -> Any:
    """Resolve 'module.submodule:ClassName' into the Python class/symbol."""
    if ":" in import_spec:
        module_path, class_name = import_spec.split(":", 1)
    else:
        module_path, class_name = import_spec.rsplit(".", 1)

    module = importlib.import_module(module_path)
    if not hasattr(module, class_name):
        raise AttributeError(f"Module '{module_path}' has no attribute '{class_name}'")
    return getattr(module, class_name)
