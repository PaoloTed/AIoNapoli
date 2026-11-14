"""Pure domain configuration schemas for rules, relevance, and app settings."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.models.decision import PlanTarget, RuleId
from app.domain.models.finding import Severity


class R1Config(BaseModel):
    model_config = ConfigDict(extra="forbid")

    density_threshold_0_1: float = Field(default=0.85, ge=0.0, le=1.0)
    severity_min: Severity = Severity.HIGH


class R2Config(BaseModel):
    model_config = ConfigDict(extra="forbid")

    density_threshold_0_1: float = Field(default=0.85, ge=0.0, le=1.0)


class R3Config(BaseModel):
    model_config = ConfigDict(extra="forbid")

    density_threshold_0_1: float = Field(default=0.70, ge=0.0, le=1.0)
    requires_heavy_rain: bool = True


class R4Config(BaseModel):
    model_config = ConfigDict(extra="forbid")

    attendance_threshold: int = Field(default=10000, gt=0)
    congestion_threshold_0_1: float = Field(default=0.70, ge=0.0, le=1.0)


class ConfidenceWeightsConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mobility: float = Field(default=0.35, ge=0.0)
    crowding: float = Field(default=0.40, ge=0.0)
    context: float = Field(default=0.25, ge=0.0)

    @model_validator(mode="after")
    def _positive_total(self) -> ConfidenceWeightsConfig:
        if (self.mobility + self.crowding + self.context) <= 0.0:
            raise ValueError("confidence_weights deve avere somma strettamente positiva")
        return self


class MonitoringTextConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    operator: str = Field(min_length=1)
    tourist: str = Field(min_length=1)
    citizen: str = Field(min_length=1)


class RulesConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    r1: R1Config = Field(default_factory=R1Config)
    r2: R2Config = Field(default_factory=R2Config)
    r3: R3Config = Field(default_factory=R3Config)
    r4: R4Config = Field(default_factory=R4Config)
    rule_precedence: list[RuleId] = Field(
        default_factory=lambda: [
            RuleId.R1_LINE2_CROWDING,
            RuleId.R2_CONFLICT_ROUTE_VS_DENSITY,
            RuleId.R3_WEATHER_CAPACITY,
            RuleId.R4_EVENT_SURGE,
        ],
        min_length=4,
        max_length=4,
    )
    confidence_weights: ConfidenceWeightsConfig = Field(default_factory=ConfidenceWeightsConfig)
    monitoring_text: MonitoringTextConfig
    alert_level_heavy_rain: dict[str, bool] = Field(
        default_factory=lambda: {
            "verde": False,
            "gialla": False,
            "arancione": True,
            "rossa": True,
        }
    )

    @model_validator(mode="after")
    def _unique_precedence(self) -> RulesConfig:
        if len(set(self.rule_precedence)) != 4:
            raise ValueError("rule_precedence deve contenere tutte e quattro le regole distinte")
        return self


class FeatureDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    type: Literal["float", "binary"] = "float"


class RelevanceConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rounding: int = Field(default=4, ge=0, le=8)
    filter_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    features: list[FeatureDefinition] = Field(min_length=1)
    weights: dict[PlanTarget, dict[str, float]]

    @model_validator(mode="after")
    def _validate_weights(self) -> RelevanceConfig:
        allowed_features = {f.name for f in self.features}
        for target in PlanTarget:
            if target not in self.weights:
                raise ValueError(f"pesi mancanti per il target '{target.value}'")
            target_weights = self.weights[target]
            if not target_weights:
                raise ValueError(f"pesi vuoti per il target '{target.value}'")
            total = 0.0
            for feat, w in target_weights.items():
                if feat not in allowed_features:
                    raise ValueError(
                        f"feature '{feat}' nei pesi di '{target.value}' non dichiarata in features"
                    )
                if w < 0.0:
                    raise ValueError(f"peso negativo per '{feat}' in '{target.value}'")
                total += w
            if total <= 0.0 or total > 1.0001:
                raise ValueError(f"somma dei pesi per '{target.value}' fuori da (0, 1]: {total}")
        return self


class AppConfig(BaseModel):
    """Combined validated application configuration."""

    model_config = ConfigDict(extra="forbid")

    rules: RulesConfig
    relevance: RelevanceConfig
    app_profile: Literal["memory", "sqlite", "postgres"] = "memory"
    demo_scenario: str = "bagnoli"
    llm_mode: Literal["replay", "live", "off"] = "replay"
    llm_cache_dir: str = ".cache/llm"
    otp_base_url: str = "http://localhost:8080"
    otp_timeout_s: float = Field(default=5.0, gt=0.0)
    rt_base_url: str = "https://proxy.busone.app/anm"
    rt_client_header: str = ""
    rt_use_header: str = "nonprofit"
    rt_timeout_s: float = Field(default=10.0, gt=0.0)
    rt_max_age_s: int = Field(default=90, gt=0)
    http_timeout_s: float = Field(default=10.0, gt=0.0)
    sqlite_path: str = ".data/app.db"
    database_url: str = ""
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    log_level: str = "info"
