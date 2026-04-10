"""Strategy YAML loader — Pydantic models for the full strategy configuration."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml
from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Meta
# ---------------------------------------------------------------------------


class MetaConfig(BaseModel):
    name: str
    version: str
    description: str = ""


# ---------------------------------------------------------------------------
# Universe / Hard Blocks
# ---------------------------------------------------------------------------


class HardBlockConfig(BaseModel):
    name: str
    enabled: bool = True
    function: str
    params: dict = Field(default_factory=dict)


class UniverseConfig(BaseModel):
    hard_blocks: list[HardBlockConfig] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Indicators
# ---------------------------------------------------------------------------


class MomentumLookbackConfig(BaseModel):
    lookback_3m: int = 63
    lookback_6m: int = 126
    lookback_12m: int = 252
    skip_1m: int = 21


class VolatilityConfig(BaseModel):
    vol_target_pct: float = 20.0
    vol_scalar_max: float = 2.0
    vol_lookback: int = 20


class MomentumQualityConfig(BaseModel):
    weekly_lookback: int = 26


class RSConfig(BaseModel):
    lookback_days: int = 126


class ADRatioConfig(BaseModel):
    lookback_days: int = 20


class VolumeRatiosConfig(BaseModel):
    short_period: int = 20
    long_period: int = 50


class Week52Config(BaseModel):
    lookback_days: int = 252


class IndicatorsConfig(BaseModel):
    ma_periods: list[int] = Field(default_factory=lambda: [50, 150, 200])
    ma_slope_lookback: int = 20
    atr_period: int = 14
    momentum: MomentumLookbackConfig = Field(default_factory=MomentumLookbackConfig)
    volatility: VolatilityConfig = Field(default_factory=VolatilityConfig)
    momentum_quality: MomentumQualityConfig = Field(default_factory=MomentumQualityConfig)
    rs: RSConfig = Field(default_factory=RSConfig)
    ad_ratio: ADRatioConfig = Field(default_factory=ADRatioConfig)
    volume_ratios: VolumeRatiosConfig = Field(default_factory=VolumeRatiosConfig)
    week_52: Week52Config = Field(default_factory=Week52Config)
    factor_weights: dict[str, float] = Field(default_factory=lambda: {
        "mom_3m": 0.20, "mom_6m": 0.30, "mom_12_1": 0.25,
        "mom_quality": 0.15, "rs_score": 0.10,
    })


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------


class ScoringModuleConfig(BaseModel):
    name: str
    enabled: bool = True
    weight: float = 0.0
    description: str = ""
    params: dict = Field(default_factory=dict)


class ScoringConfig(BaseModel):
    composite_method: str = "weighted_sum"
    modules: list[ScoringModuleConfig] = Field(default_factory=list)

    def get_module(self, name: str) -> ScoringModuleConfig | None:
        """Get a scoring module config by name."""
        for m in self.modules:
            if m.name == name:
                return m
        return None


# ---------------------------------------------------------------------------
# Regime
# ---------------------------------------------------------------------------


class RegimeSignalConfig(BaseModel):
    name: str
    description: str = ""
    weight: float = 1.0
    thresholds: dict = Field(default_factory=dict)


class CrashIndicatorConfig(BaseModel):
    return_2yr_threshold: float = -0.20
    rally_1m_threshold: float = 0.10


class RegimeClassificationConfig(BaseModel):
    name: str
    score_range: list[float]
    equity_pct: float
    max_positions: int
    risk_per_trade: float
    portfolio_heat: float
    exposure_label: str = ""


class FastCrashConfig(BaseModel):
    enabled: bool = True
    rolling_window_days: int = 5
    decline_threshold: float = -0.08
    response: str = "sell_50_pct_all"
    reset_lookback_days: int = 10
    overrides_monster: bool = True


class BullEntryPhaseConfig(BaseModel):
    name: str
    trigger: str = ""
    capital_deploy: float | None = None


class BullEntryProtocolConfig(BaseModel):
    enabled: bool = True
    phases: list[BullEntryPhaseConfig] = Field(default_factory=list)


class RegimeConfig(BaseModel):
    signals: list[RegimeSignalConfig] = Field(default_factory=list)
    crash_indicator: CrashIndicatorConfig = Field(default_factory=CrashIndicatorConfig)
    stability_days: int = 3
    classifications: list[RegimeClassificationConfig] = Field(default_factory=list)
    fast_crash: FastCrashConfig = Field(default_factory=FastCrashConfig)
    bull_entry_protocol: BullEntryProtocolConfig = Field(default_factory=BullEntryProtocolConfig)

    def get_classification(self, name: str) -> RegimeClassificationConfig | None:
        for c in self.classifications:
            if c.name == name:
                return c
        return None

    def classify_score(self, score: float) -> RegimeClassificationConfig | None:
        """Find the classification that matches a given regime score."""
        for c in self.classifications:
            if c.score_range[0] <= score <= c.score_range[1]:
                return c
        return None


# ---------------------------------------------------------------------------
# Exit Engine
# ---------------------------------------------------------------------------


class ExitRuleConfig(BaseModel):
    type: str
    description: str = ""
    # All other fields are rule-specific params
    model_config = {"extra": "allow"}


class ExitPhaseConfig(BaseModel):
    name: str
    gain_range: list[float | None]
    rules: list[ExitRuleConfig] = Field(default_factory=list)


class ValidationLayerConfig(BaseModel):
    name: str
    enabled: bool = True
    description: str = ""
    params: dict = Field(default_factory=dict)


class CascadeLayerConfig(BaseModel):
    name: str
    priority: int
    trigger: dict | str = ""
    response: dict | str = ""


class CascadeConfig(BaseModel):
    enabled: bool = True
    layers: list[CascadeLayerConfig] = Field(default_factory=list)


class ExitConfig(BaseModel):
    framework: str = "phase_based"
    phases: list[ExitPhaseConfig] = Field(default_factory=list)
    validation_layers: list[ValidationLayerConfig] = Field(default_factory=list)
    cascade: CascadeConfig = Field(default_factory=CascadeConfig)

    def get_phase(self, name: str) -> ExitPhaseConfig | None:
        for p in self.phases:
            if p.name == name:
                return p
        return None


# ---------------------------------------------------------------------------
# Monster Detection
# ---------------------------------------------------------------------------


class MonsterCriterionConfig(BaseModel):
    signal: str
    points: int
    condition: str = ""


class MonsterConfig(BaseModel):
    enabled: bool = True
    score_threshold: int = 80
    gain_gate: float = 0.40
    criteria: list[MonsterCriterionConfig] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Turnaround Watch
# ---------------------------------------------------------------------------


class TurnaroundConditionsConfig(BaseModel):
    min_negative_quarters: int = 2
    lookback_quarters: int = 8
    monotonic_improvement_quarters: int = 4
    latest_eps_positive: bool = True
    min_revenue_growth_yoy: float = 0.10


class TurnaroundWatchConfig(BaseModel):
    enabled: bool = True
    conditions: TurnaroundConditionsConfig = Field(default_factory=TurnaroundConditionsConfig)
    suppression: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Position Sizing
# ---------------------------------------------------------------------------


class PositionAdjustmentConfig(BaseModel):
    name: str
    enabled: bool = True
    condition: str = ""
    reduction: float = 0.0
    additional: str = ""
    # Correlation-specific
    threshold_high: float | None = None
    threshold_moderate: float | None = None
    reduction_high: float | None = None
    reduction_moderate: float | None = None
    lookback_days: int | None = None
    min_overlap_days: int | None = None


class PositionSizingConfig(BaseModel):
    base_risk_pct: float = 1.0
    position_floor_pct: float = 2.0
    position_ceiling_pct: float = 20.0
    max_sector_concentration: float = 0.30
    adjustments: list[PositionAdjustmentConfig] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Signal Lifecycle
# ---------------------------------------------------------------------------


class TierConfig(BaseModel):
    score_min: float = 0.0
    regimes: list[str] = Field(default_factory=list)
    breakout_required: bool = False
    or_earnings_within_days: int | None = None


class SignalTieringConfig(BaseModel):
    tier_1: TierConfig = Field(default_factory=TierConfig)
    tier_2: TierConfig = Field(default_factory=TierConfig)
    tier_3: TierConfig = Field(default_factory=TierConfig)


class SignalConfirmationConfig(BaseModel):
    method: str = "close_above_pivot"
    max_gap_pct: float = 0.03


class SignalConfig(BaseModel):
    confirmation: SignalConfirmationConfig = Field(default_factory=SignalConfirmationConfig)
    tiering: SignalTieringConfig = Field(default_factory=SignalTieringConfig)
    earnings_window_days: int = 10


# ---------------------------------------------------------------------------
# Backtest
# ---------------------------------------------------------------------------


class TransactionCostsConfig(BaseModel):
    entry_slippage: float = 0.005
    exit_slippage: float = 0.005
    brokerage_per_side: float = 0.001
    stt_sell: float = 0.001
    exchange_per_side: float = 0.0005


class BacktestConfig(BaseModel):
    transaction_costs: TransactionCostsConfig = Field(default_factory=TransactionCostsConfig)
    periods: dict = Field(default_factory=dict)
    initial_capital: int = 10_000_000
    rebalance_frequency: str = "monthly"


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


class DataQualityConfig(BaseModel):
    max_missing_stocks_pct: int = 5


class PipelineConfig(BaseModel):
    schedule: str = "0 11 * * 1-5"
    timeout_minutes: int = 60
    data_quality: DataQualityConfig = Field(default_factory=DataQualityConfig)
    notifications: dict = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Root strategy config
# ---------------------------------------------------------------------------


class StrategyConfig(BaseModel):
    meta: MetaConfig
    universe: UniverseConfig = Field(default_factory=UniverseConfig)
    indicators: IndicatorsConfig = Field(default_factory=IndicatorsConfig)
    scoring: ScoringConfig = Field(default_factory=ScoringConfig)
    regime: RegimeConfig = Field(default_factory=RegimeConfig)
    exits: ExitConfig = Field(default_factory=ExitConfig)
    monster: MonsterConfig = Field(default_factory=MonsterConfig)
    turnaround_watch: TurnaroundWatchConfig = Field(default_factory=TurnaroundWatchConfig)
    position_sizing: PositionSizingConfig = Field(default_factory=PositionSizingConfig)
    signals: SignalConfig = Field(default_factory=SignalConfig)
    backtest: BacktestConfig = Field(default_factory=BacktestConfig)
    pipeline: PipelineConfig = Field(default_factory=PipelineConfig)

    @property
    def strategy_hash(self) -> str:
        """Deterministic SHA-256 hash of the strategy config (excluding meta)."""
        config_dict = self.model_dump(exclude={"meta"})
        canonical = json.dumps(config_dict, sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode()).hexdigest()[:12]


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------


def load_strategy(path: str | Path) -> StrategyConfig:
    """Load and validate a strategy YAML file."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Strategy file not found: {path}")

    with open(path) as f:
        raw = yaml.safe_load(f)

    return StrategyConfig.model_validate(raw)
