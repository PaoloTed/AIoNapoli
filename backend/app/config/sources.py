"""Reproducible registry of every RSS/Atom source and the ANM scraper.

The registry is configuration, not a second disruption store. Duplicate URLs
are collapsed into one acquisition entry while every original identity is kept
in ``provenance`` for auditing.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

SourceKind = Literal["rss", "atom", "google_news", "anm_scraper", "non_rss"]
SourceClass = Literal[
    "official_transport",
    "civil_protection",
    "local_government",
    "local_news",
    "tourism_culture",
    "national_context",
    "aggregator",
    "unsupported",
]
LocalRelevance = Literal["required", "optional", "not_required"]


class SourceDefinition(BaseModel):
    """One configured acquisition target with explicit operational policy."""

    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(min_length=1, pattern=r"^[a-z0-9_]+$")
    name: str = Field(min_length=1)
    url: str = Field(min_length=8)
    kind: SourceKind
    source_class: SourceClass
    operator: str | None = None
    language: str = "it"
    timezone: str = "Europe/Rome"
    local_relevance: LocalRelevance = "required"
    enabled: bool = True
    polling_interval_s: int = Field(default=900, gt=0)
    timeout_s: int = Field(default=20, gt=0)
    max_retries: int = Field(default=3, ge=0, le=8)
    notes: str = ""
    provenance: list[str] = Field(default_factory=list)

    @field_validator("source_id", "name", "url")
    @classmethod
    def _strip(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("campo vuoto")
        return value

    @field_validator("provenance")
    @classmethod
    def _unique_provenance(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(item for item in value if item.strip()))

    def registry_hash(self) -> str:
        payload = self.model_dump(mode="json", exclude={"provenance"})
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class SourceRegistry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int
    generated_from: list[str] = Field(default_factory=list)
    sources: list[SourceDefinition] = Field(min_length=1)

    def by_id(self) -> dict[str, SourceDefinition]:
        return {source.source_id: source for source in self.sources}

    def enabled(self) -> list[SourceDefinition]:
        return [source for source in self.sources if source.enabled]


def default_registry_path() -> Path:
    return Path(__file__).resolve().parent / "sources.yaml"


def load_source_registry(path: str | Path | None = None) -> SourceRegistry:
    """Load and validate the registry, collapsing duplicate URLs."""
    target = Path(path) if path else default_registry_path()
    if not target.exists():
        raise FileNotFoundError(f"registro fonti non trovato: {target}")
    try:
        raw = yaml.safe_load(target.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ValueError(f"registro fonti YAML malformato: {exc}") from exc
    if not isinstance(raw, dict):
        raise ValueError("il registro fonti deve essere una mappa YAML")

    defaults = raw.get("defaults") or {}
    if not isinstance(defaults, dict):
        raise ValueError("defaults del registro fonti non valido")
    raw_sources = raw.get("sources")
    if not isinstance(raw_sources, list) or not raw_sources:
        raise ValueError("registro fonti senza sources")

    merged: dict[str, dict[str, object]] = {}
    for item in raw_sources:
        if not isinstance(item, dict):
            raise ValueError("voce del registro fonti non valida")
        candidate = {**defaults, **item}
        url = str(candidate.get("url") or "").strip()
        if not url:
            raise ValueError("voce del registro fonti senza url")
        if url not in merged:
            merged[url] = dict(candidate)
            merged[url]["provenance"] = list(candidate.get("provenance") or [])
        else:
            existing = merged[url]
            for alias in candidate.get("provenance") or [candidate.get("source_id")]:
                alias_text = str(alias).strip()
                if alias_text and alias_text not in existing["provenance"]:
                    existing["provenance"].append(alias_text)
    return SourceRegistry(
        version=int(raw.get("version") or 1),
        generated_from=[str(item) for item in (raw.get("generated_from") or [])],
        sources=[SourceDefinition.model_validate(item) for item in merged.values()],
    )


__all__ = [
    "SourceClass",
    "SourceDefinition",
    "SourceKind",
    "SourceRegistry",
    "default_registry_path",
    "load_source_registry",
]
