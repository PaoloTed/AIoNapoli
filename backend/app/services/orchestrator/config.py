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


def _parse_gtfs_datasets(raw: str) -> dict[str, str]:
    """Parse ``key:schema,key:schema`` without hiding the legacy single feed."""
    datasets: dict[str, str] = {}
    for item in raw.split(","):
        token = item.strip()
        if not token:
            continue
        if ":" not in token:
            raise ValueError(f"GTFS_DATASETS non valido: {token!r} (atteso key:schema)")
        key, schema = (part.strip() for part in token.split(":", 1))
        if not key or not schema:
            raise ValueError(f"GTFS_DATASETS non valido: {token!r}")
        if key in datasets:
            raise ValueError(f"GTFS_DATASETS contiene la chiave duplicata: {key!r}")
        datasets[key] = schema
    return datasets


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
            llm_provider=os.environ.get("LLM_PROVIDER", "openai_compatible"),
            llm_base_url=os.environ.get("LLM_BASE_URL", ""),
            llm_api_key=os.environ.get("LLM_API_KEY", ""),
            llm_model=os.environ.get("LLM_MODEL", ""),
            llm_timeout_s=float(os.environ.get("LLM_TIMEOUT_S", "30")),
            llm_max_retries=int(os.environ.get("LLM_MAX_RETRIES", "2")),
            llm_max_output_tokens=int(os.environ.get("LLM_MAX_OUTPUT_TOKENS", "1600")),
            llm_temperature=float(os.environ.get("LLM_TEMPERATURE", "0")),
            llm_prompt_version=os.environ.get("LLM_PROMPT_VERSION", "news-extraction-1"),
            llm_schema_version=os.environ.get("LLM_SCHEMA_VERSION", "1"),
            llm_cache_dir=os.environ.get("LLM_CACHE_DIR", ".cache/llm"),
            llm_replay_dir=os.environ.get("LLM_REPLAY_DIR", ""),
            input_agent_llm_required=os.environ.get("INPUT_AGENT_LLM_REQUIRED", "false").lower()
            in {"1", "true", "yes", "on"},  # noqa: E712
            otp_base_url=os.environ.get("OTP_BASE_URL", "http://localhost:8080"),
            otp_timeout_s=float(os.environ.get("OTP_TIMEOUT_S", "5")),
            routing_mode=os.environ.get("ROUTING_MODE", "real"),  # type: ignore[arg-type]
            routing_timezone=os.environ.get("ROUTING_TIMEZONE", "Europe/Rome"),
            journey_max_plans=int(os.environ.get("JOURNEY_MAX_PLANS", "3")),
            journey_budget_s=float(os.environ.get("JOURNEY_BUDGET_S", "15")),
            journey_default_first=int(os.environ.get("JOURNEY_DEFAULT_FIRST", "10")),
            ingestion_registry_path=os.environ.get("INGESTION_REGISTRY_PATH", ""),
            ingestion_user_agent=os.environ.get(
                "INGESTION_USER_AGENT", "NapoliAgenticCity/1.0 (+backend ingestion worker)"
            ),
            ingestion_timeout_s=float(os.environ.get("INGESTION_TIMEOUT_S", "20")),
            ingestion_max_concurrency=int(os.environ.get("INGESTION_MAX_CONCURRENCY", "4")),
            ingestion_max_retries=int(os.environ.get("INGESTION_MAX_RETRIES", "3")),
            ingestion_backoff_s=float(os.environ.get("INGESTION_BACKOFF_S", "2")),
            ingestion_poll_interval_s=float(os.environ.get("INGESTION_POLL_INTERVAL_S", "30")),
            ingestion_lease_s=int(os.environ.get("INGESTION_LEASE_S", "300")),
            ingestion_unknown_expiry_ttl_s=int(
                os.environ.get("INGESTION_UNKNOWN_EXPIRY_TTL_S", "21600")
            ),
            ingestion_review_ttl_s=int(os.environ.get("INGESTION_REVIEW_TTL_S", "7200")),
            ingestion_relevance_version=os.environ.get("INGESTION_RELEVANCE_VERSION", "1"),
            geocoder_provider=os.environ.get("GEOCODER_PROVIDER", "local"),  # type: ignore[arg-type]
            geocoder_base_url=os.environ.get(
                "GEOCODER_BASE_URL", "https://nominatim.openstreetmap.org"
            ),
            geocoder_timeout_s=float(os.environ.get("GEOCODER_TIMEOUT_S", "8")),
            geocoder_max_results=int(os.environ.get("GEOCODER_MAX_RESULTS", "5")),
            rt_base_url=os.environ.get("RT_BASE_URL", "https://proxy.busone.app/anm"),
            rt_client_header=os.environ.get("RT_CLIENT_HEADER", ""),
            rt_use_header=os.environ.get("RT_USE_HEADER", "nonprofit"),
            rt_timeout_s=float(os.environ.get("RT_TIMEOUT_S", "10")),
            rt_max_age_s=int(os.environ.get("RT_MAX_AGE_S", "90")),
            http_timeout_s=float(os.environ.get("HTTP_TIMEOUT_S", "10")),
            sqlite_path=os.environ.get("SQLITE_PATH", ".data/app.db"),
            database_url=os.environ.get("DATABASE_URL", ""),
            gtfs_schema=os.environ.get("GTFS_SCHEMA", "gtfs_eav"),
            gtfs_dataset_key=os.environ.get("GTFS_DATASET_KEY", "eav"),
            gtfs_datasets=_parse_gtfs_datasets(
                os.environ.get("GTFS_DATASETS", "eav:gtfs_eav,anm:gtfs_anm")
            ),
            osm_schema=os.environ.get("OSM_SCHEMA", "osm_territory"),
            osm_dataset_key=os.environ.get("OSM_DATASET_KEY", "osm_napoli"),
            cors_origins=cors_origins,
            log_level=os.environ.get("LOG_LEVEL", "info"),
        )
    except (ValidationError, ValueError) as exc:
        raise ConfigInvalidError(
            f"variabili d'ambiente non valide: {exc}",
            field="env",
        ) from exc
