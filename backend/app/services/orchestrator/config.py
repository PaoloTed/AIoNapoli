"""Configuration loading and fail-fast Pydantic validation (NFR-05)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from app.domain.models.config import AppConfig, RelevanceConfig, RulesConfig


class ConfigInvalidError(Exception):
    """Raised when configuration YAML or environment values fail validation."""

    def __init__(self, detail: str, field: str | None = None) -> None:
        self.code = "config_invalid"
        self.field = field
        self.detail = detail
        super().__init__(detail)


def resolve_config_dir(config_dir: str | Path | None = None) -> Path:
    """Resolve configuration directory from explicit path, env var, or package directory."""
    if config_dir is not None:
        return Path(config_dir)
    env_dir = os.environ.get("APP_CONFIG_DIR", "").strip()
    if env_dir:
        candidate = Path(env_dir)
        if candidate.exists():
            return candidate
        # Fallback relative to repo root if cwd is backend/
        repo_root = Path(__file__).resolve().parents[4]
        rel = repo_root / env_dir
        if rel.exists():
            return rel
        return candidate
    return Path(__file__).resolve().parent


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise ConfigInvalidError(f"file di configurazione mancante: {path}", field=path.name)
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigInvalidError(f"YAML malformato in {path.name}: {exc}", field=path.name) from exc
    if not isinstance(raw, dict):
        raise ConfigInvalidError(
            f"il file {path.name} deve contenere una mappa YAML",
            field=path.name,
        )
    return raw


def load_rules_config(config_dir: str | Path | None = None) -> RulesConfig:
    """Load and validate rules.yaml."""
    base = resolve_config_dir(config_dir)
    data = _load_yaml(base / "rules.yaml")
    try:
        return RulesConfig.model_validate(data)
    except ValidationError as exc:
        raise ConfigInvalidError(
            f"rules.yaml non valido: {exc}",
            field="rules.yaml",
        ) from exc


def load_relevance_config(config_dir: str | Path | None = None) -> RelevanceConfig:
    """Load and validate relevance.yaml."""
    base = resolve_config_dir(config_dir)
    data = _load_yaml(base / "relevance.yaml")
    try:
        return RelevanceConfig.model_validate(data)
    except ValidationError as exc:
        raise ConfigInvalidError(
            f"relevance.yaml non valido: {exc}",
            field="relevance.yaml",
        ) from exc


def load_config(config_dir: str | Path | None = None) -> AppConfig:
    """Load and validate full application configuration from YAML + env."""
    rules = load_rules_config(config_dir)
    relevance = load_relevance_config(config_dir)

    cors_raw = os.environ.get("CORS_ORIGINS", "http://localhost:3000")
    cors_origins = [origin.strip() for origin in cors_raw.split(",") if origin.strip()]
    if not cors_origins:
        cors_origins = ["http://localhost:3000"]

    try:
        return AppConfig(
            rules=rules,
            relevance=relevance,
            app_profile=os.environ.get("APP_PROFILE", "memory"),  # type: ignore[arg-type]
            demo_scenario=os.environ.get("DEMO_SCENARIO", "bagnoli"),
            llm_mode=os.environ.get("LLM_MODE", "replay"),  # type: ignore[arg-type]
            llm_cache_dir=os.environ.get("LLM_CACHE_DIR", ".cache/llm"),
            otp_base_url=os.environ.get("OTP_BASE_URL", "http://localhost:8080"),
            otp_timeout_s=float(os.environ.get("OTP_TIMEOUT_S", "5")),
            rt_base_url=os.environ.get("RT_BASE_URL", "https://proxy.busone.app/anm"),
            rt_client_header=os.environ.get("RT_CLIENT_HEADER", ""),
            rt_use_header=os.environ.get("RT_USE_HEADER", "nonprofit"),
            rt_timeout_s=float(os.environ.get("RT_TIMEOUT_S", "10")),
            rt_max_age_s=int(os.environ.get("RT_MAX_AGE_S", "90")),
            http_timeout_s=float(os.environ.get("HTTP_TIMEOUT_S", "10")),
            sqlite_path=os.environ.get("SQLITE_PATH", ".data/app.db"),
            database_url=os.environ.get("DATABASE_URL", ""),
            cors_origins=cors_origins,
            log_level=os.environ.get("LOG_LEVEL", "info"),
            enable_negotiation=os.environ.get("ENABLE_NEGOTIATION", "true").lower()
            in ("true", "1", "yes"),
            findings_source=os.environ.get("FINDINGS_SOURCE", "fixtures").lower(),  # type: ignore[arg-type]
        )
    except (ValidationError, ValueError) as exc:
        raise ConfigInvalidError(
            f"variabili d'ambiente non valide: {exc}",
            field="env",
        ) from exc
