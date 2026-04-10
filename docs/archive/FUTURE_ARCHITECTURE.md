# MomentumEdge — Future Architecture: Configurable Strategy Engine

**Version:** 1.0
**Date:** March 2026
**Status:** Proposal
**Scope:** Production-grade redesign for parameter flexibility, rule composability, and multi-strategy support

---

## 1. Problem Statement

MomentumEdge has evolved through three specification iterations (Use Case v1 → v7 → v16). Each iteration changed:

- Scoring weights and bonus values (14+ parameters shifted between v7 and v16)
- Exit rules (from 9 flat rules to a 4-phase gain-based framework)
- Hard blocks (from 4 to 8 filters)
- Position sizing logic (flat heat → regime-tiered heat + correlation adjustment)
- Entirely new subsystems (monster detection, fast crash, turnaround watch, bull entry protocol)

**The current architecture cannot absorb these changes without rewriting core modules.** Every threshold is a Python constant. Every rule is an `if` statement. Every scoring formula is inline code. The v16 gap analysis estimates 18–27 developer days — most of that effort is refactoring hardcoded logic, not building new capabilities.

**Goal:** Design an architecture where:

1. Parameters are data, not code — change a YAML value, not a Python file
2. Rules are composable — add, remove, reorder, or disable without touching the pipeline
3. Strategies are versioned — reproduce any historical watchlist with exact parameters
4. Backtesting sweeps parameter space — not just a single configuration
5. New modules plug in — without modifying `runner.py` or `composite_score.py`

---

## 2. Architecture Overview

```
                    ┌─────────────────────────────────┐
                    │       Strategy Registry          │
                    │  strategies/momentum_edge_v7.yaml│
                    │  strategies/momentum_edge_v16.yaml│
                    │  strategies/experimental_01.yaml │
                    └────────────┬────────────────────┘
                                 │ loads
                                 ▼
┌──────────┐    ┌──────────────────────────────┐    ┌──────────────┐
│ CLI/API  │───▶│     Strategy Engine Core      │───▶│  Results DB  │
│ main.py  │    │                                │    │  (versioned) │
└──────────┘    │  ┌────────────────────────┐   │    └──────────────┘
                │  │   Pipeline Orchestrator │   │
                │  │   (phase-aware runner)  │   │
                │  └───────────┬────────────┘   │
                │              │                 │
                │  ┌───────────▼────────────┐   │
                │  │    Module Registry      │   │
                │  │  (pluggable scorers,    │   │
                │  │   filters, exits)       │   │
                │  └───────────┬────────────┘   │
                │              │                 │
                │  ┌───────────▼────────────┐   │
                │  │   Rule Engine           │   │
                │  │  (declarative rules,    │   │
                │  │   priority chains)      │   │
                │  └────────────────────────┘   │
                └──────────────────────────────┘
```

### 2.1 Core Principles

| Principle | Implementation |
|-----------|---------------|
| **Parameters as data** | YAML strategy files define all thresholds, weights, toggles |
| **Rules as declarations** | Exit rules, hard blocks, and filters are declarative rule objects — not inline `if` chains |
| **Modules as plugins** | Each scorer/filter implements a standard interface; registry auto-discovers them |
| **Strategies as versions** | Every pipeline run tags its output with a strategy hash; results are reproducible |
| **Backtest as parameter sweep** | Backtester accepts parameter grids and runs combinatorial sweeps |
| **Fail-open for bonuses, fail-closed for blocks** | Missing data on a bonus = 0 points; missing data on a hard block = exclude stock |

---

## 3. Strategy Definition System

### 3.1 Strategy File Format

Every configurable parameter lives in a versioned YAML file. The strategy file is the single source of truth for a pipeline run.

```yaml
# strategies/momentum_edge_v16.yaml
meta:
  name: "MomentumEdge v16"
  version: "16.0.0"
  description: "4-phase exit engine, 8 hard blocks, monster detection"
  author: "Mohit"
  locked_until: "2026-09-01"  # Cannot modify LOCKED params before this date
  base_strategy: null           # Or inherit from another strategy file

# ─── Universe Filters (Hard Blocks) ───────────────────────────
universe:
  hard_blocks:
    - name: eps_junk
      enabled: true
      lock: LOCKED
      description: "Negative earnings 3+ consecutive quarters"
      module: universe_filter
      function: check_eps_junk
      params:
        min_positive_quarters: 2
        lookback_quarters: 4

    - name: market_cap_band
      enabled: true
      lock: FREE    # Test 1000/1500/2000 in Test 2
      module: universe_filter
      function: check_market_cap
      params:
        min_cr: 1000
        max_cr: 30000
        test_range: [1000, 1500, 2000]

    - name: liquidity
      enabled: true
      lock: FREE
      module: universe_filter
      function: check_liquidity
      params:
        min_daily_traded_value_cr: 15
        test_range: [10, 15, 20]

    - name: surveillance
      enabled: true
      lock: LOCKED
      module: universe_filter
      function: check_asm_esm

    - name: ocf_quality
      enabled: true
      lock: LOCKED
      module: universe_filter
      function: check_ocf
      params:
        max_negative_quarters: 3
        lookback_quarters: 4

    - name: promoter_pledge
      enabled: true
      lock: LOCKED
      module: universe_filter
      function: check_pledge
      params:
        threshold_operational: 0.20
        threshold_infra: 0.50
        infra_exception:
          de_falling: true
          revenue_growth_min: 0.30

    - name: sebi_fine
      enabled: true
      lock: LOCKED
      module: universe_filter
      function: check_sebi_fine
      params:
        lookback_months: 24

    - name: ipo_age
      enabled: true
      lock: LOCKED
      module: universe_filter
      function: check_ipo_age
      params:
        min_trading_days: 200

    - name: business_pivot
      enabled: true
      lock: LOCKED
      module: universe_filter
      function: check_business_pivot
      params:
        max_pivots: 3
        lookback_years: 5

# ─── Scoring Modules ──────────────────────────────────────────
scoring:
  composite_method: weighted_sum  # or "rank_average", "z_score_sum"

  modules:
    - name: momentum
      enabled: true
      weight: 0.35
      module: momentum_score
      function: score_momentum
      params:
        weights:
          mom_12_1m: 0.40   # FREE: test 0.30-0.50
          mom_6m: 0.35      # FREE: test 0.25-0.45
          mom_3m: 0.25      # FREE: test 0.15-0.30
        vol_target_pct: 20.0
        vol_scalar_max: 2.0  # LOCKED (Barroso 2015)
        rs_rank_min_pct: 30  # FREE: test 20/30/40
        mom_quality_min: 0.55  # FREE: test 0.50/0.55/0.60/null

    - name: fundamental_bonus
      enabled: true
      weight: 0.20
      module: fundamental_bonus
      function: score_fundamentals
      params:
        score_range: [-20, 30]  # v16 expanded from [-5, 20]
        bonuses:
          - signal: eps_acceleration
            points: 8
            lock: LOCKED
            condition: "3 quarters of rising YoY EPS growth"
          - signal: eps_growth_high
            points: 5
            lock: LOCKED
            condition: "latest quarter EPS growth >= 15%"
          - signal: eps_positive
            points: 2
            lock: LOCKED
            condition: "latest quarter EPS > 0"
          - signal: revenue_opm_simultaneous
            points: 12
            lock: ESTIMATE
            condition: "revenue growth > 20% AND OPM expanding > 300bp"
          - signal: revenue_acceleration
            points: 10
            lock: ESTIMATE
            condition: "revenue growth > 30% YoY"
          - signal: opm_expansion
            points: 8
            lock: ESTIMATE
            condition: "OPM expanding > 300bp over 3 quarters"
          - signal: promoter_buying
            points: 8
            lock: ESTIMATE
            condition: "promoter open market purchases in last 2 quarters"
          - signal: pead_sue_strong
            points: 10
            lock: ESTIMATE
            condition: "eps_growth_yoy > 50% reported within last 60 days"
          - signal: pead_sue_moderate
            points: 6
            lock: ESTIMATE
            condition: "eps_growth_yoy > 25% reported within last 60 days"
          - signal: market_cap_crossing
            points: 6
            lock: ESTIMATE
            condition: "entered 1k-30k band within last 60 days"
          - signal: low_de
            points: 2
            lock: LOCKED
            condition: "D/E < 1.5 and not financial sector"
          - signal: analyst_revision
            points: 4
            lock: LOCKED
            condition: "upward EPS revision in last quarter"
        penalties:
          - signal: promoter_selling
            points: -8
            lock: LOCKED
            condition: "promoter selling in last 2 quarters"
          - signal: sebi_investigation
            points: -10
            lock: LOCKED
            condition: "active SEBI price investigation"
          - signal: lodr_fine
            points: -3
            lock: LOCKED
            condition: "LODR fine in last 12 months"
          - signal: debtors_critical
            points: -5
            lock: LOCKED
            condition: "trade receivable days > 180"
          - signal: debtors_warning
            points: -3
            lock: LOCKED
            condition: "trade receivable days > 120"
          - signal: ocf_quality_poor
            points: -5
            lock: LOCKED
            condition: "OCF/net profit < 0.4 for 2 consecutive quarters"
          - signal: high_de
            points: -2
            lock: LOCKED
            condition: "D/E > 3.0"

    - name: accumulation
      enabled: true
      weight: 0.15
      module: accumulation_score
      function: score_accumulation
      params:
        obv_bonus: 5
        ad_ratio_threshold: 0.60
        ad_ratio_bonus: 4
        inst_flow_bonus: 1  # Reduced from 2 in v16
        inst_flow_routing:
          low_promoter_threshold: 0.65
          high_promoter_threshold: 0.75

    - name: sector
      enabled: true
      weight: 0.10
      module: sector_rotation
      function: score_sector
      params:
        top_n_bonus: 10
        top_n: 3
        bottom_n_penalty: -5
        bottom_n: 3
        ranking_method: median_3m_momentum

    - name: technical
      enabled: true
      weight: 0.12
      module: trend_template
      function: score_technical
      params:
        conditions:
          - price_above_ma50: true
          - price_above_ma150: true
          - price_above_ma200: true
          - ma50_above_ma150: true
          - ma150_above_ma200: true
          - ma200_slope_rising: true
          - near_52w_high_pct: 0.80
          - stage2_min_days: 20

    - name: breakout
      enabled: true
      weight: 0.08
      module: breakout_patterns
      function: score_breakout
      params:
        vcp:
          min_contractions: 3    # FREE: test 2/3/4
          max_depth: 0.40        # FREE: test 0.30/0.40/0.50
          min_weeks: 5           # LOCKED
          max_weeks: 52          # LOCKED
          breakout_vol_ratio: 1.5  # FREE: test 1.25/1.5/2.0
        entry_rules:
          max_gap_above_pivot: 0.03
          min_close_strength: 0.75
          max_extension_above_pivot: 0.05
          volume_confirmation: true
          false_breakout_days: 2

# ─── Market Regime ────────────────────────────────────────────
regime:
  signals:
    - name: breadth_200ma
      description: "% stocks above 200MA"
      thresholds: { bull: 0.60, bear: 0.40 }
    - name: leadership
      description: "top 10% vs Nifty 50"
      thresholds: { bull: 0.10 }
    - name: breadth_50ma
      description: "% stocks above 50MA"
      thresholds: { bull: 0.60, bear: 0.40 }
    - name: highs_vs_lows
      description: "new highs/lows ratio"
      thresholds: { bull: 1.0 }
    - name: nifty_extension
      description: "Nifty distance from 200MA"
      thresholds: { bull: 0.0 }
    - name: crash_warning
      description: "2yr return < threshold AND 1m rally > threshold"
      thresholds: { return_2yr: -0.20, rally_1m: 0.10 }

  classifications:
    - name: strong_bull
      score_range: [5.0, 6.0]
      equity_pct: 100
      max_positions: 15
      risk_per_trade: 2.0
      portfolio_heat: 6.0
    - name: bull
      score_range: [4.0, 5.0]
      equity_pct: 80
      max_positions: 12
      risk_per_trade: 1.5
      portfolio_heat: 5.0
    - name: weak
      score_range: [2.5, 4.0]
      equity_pct: 50
      max_positions: 8
      risk_per_trade: 1.0
      portfolio_heat: 4.0
    - name: bear
      score_range: [1.0, 2.5]
      equity_pct: 25
      max_positions: 4
      risk_per_trade: 0.5
      portfolio_heat: 2.0
    - name: full_bear
      score_range: [0.0, 1.0]
      equity_pct: 0
      max_positions: 0
      risk_per_trade: 0.0
      portfolio_heat: 0.0

  fast_crash:
    enabled: true
    rolling_window_days: 5
    decline_threshold: -0.08
    response: sell_50_pct_all
    reset_lookback_days: 10
    overrides_monster: true  # Halves monster positions too

  bull_entry_protocol:
    enabled: true
    phases:
      - name: capitulation
        trigger: "panic volume > 2x 20d avg on Nifty500 AND A/D higher low while price lower low"
        action: watch_only
        capital_deploy: 0.0
      - name: breadth_thrust
        trigger: "single day 90%+ advancing volume"
        action: deploy
        capital_deploy: 0.25
      - name: ad_confirmation
        trigger: "A/D line higher high than capitulation"
        action: deploy
        capital_deploy: 0.25
      - name: new_highs_expand
        trigger: "52w highs > 100/week for 2+ weeks"
        action: full_deploy
        capital_deploy: null  # Uses regime allocation

# ─── Exit Engine ──────────────────────────────────────────────
exits:
  framework: phase_based  # "phase_based" (v16) or "flat_rules" (v7)

  phases:
    - name: prove_it
      gain_range: [0.0, 0.25]
      rules:
        - type: fixed_stop
          stop_pct: 0.08       # FREE: test 0.06/0.08/0.10
          description: "8% stop from entry"
        - type: regime_exit
          trigger: bear_or_crash
          action: sell_20pct_per_day
          days: 5

    - name: let_it_run
      gain_range: [0.25, 1.0]
      rules:
        - type: trailing_stop
          trail_pct: 0.20      # FREE: test 0.15/0.20/0.25
          reference: 10_week_high
        - type: rs_decay
          floor_pct: 30
          persist_weeks: 4     # LOCKED
          description: "4 consecutive weeks below RS floor"
        - type: ma_weakness
          ma_period: 21
          confirm_days: 3
          volume_check: true
          trend_integrity_override: true
        - type: climax_run
          gain_threshold: 0.20
          time_window_days: 15
          sell_pct: 0.50
        - type: regime_exit
          trigger: bear_or_crash
          action: sell_20pct_per_day
          days: 5

    - name: working_compounder
      gain_range: [1.0, 2.0]
      rules:
        - type: trailing_stop
          trail_pct: 0.15      # FREE: test 0.12/0.15/0.18
          reference: 10_week_high
        - type: rs_decay
          floor_pct: 30
          persist_weeks: 4
        - type: ma_weakness
          ma_period: 21
          confirm_days: 3
          volume_check: true
          trend_integrity_override: true
        - type: climax_run
          gain_threshold: 1.00
          time_window_days: 15
          sell_pct: 0.50
        - type: regime_exit
          trigger: bear_or_crash
          action: sell_20pct_per_day
          days: 5

    - name: monster_run
      gain_range: [2.0, null]  # 200%+ or monster override
      rules:
        - type: ma_breach
          ma_period: 50        # 10-week MA (LOCKED)
          primary: true
        - type: trailing_stop
          trail_pct: 0.12      # FREE
          reference: 10_week_high
          applies_to: core_50pct
        - type: partial_exit
          at_new_highs: true
          sell_pct: 0.25
          max_partials: 2
        - type: rs_decay
          floor_pct: 30
          persist_weeks: 4
        - type: climax_run
          gain_threshold: 1.00
          time_window_days: 15
          sell_pct: 0.50

  validation_layers:
    - name: trend_integrity
      description: "Higher highs + higher lows intact -> suppress 21DMA warning"
      enabled: true
    - name: volume_direction
      description: "vol < 0.75x on down days = hold; vol > 1.5x on down days = instant 25% exit"
      enabled: true
      params:
        hold_threshold: 0.75
        distribution_threshold: 1.50
        distribution_exit_pct: 0.25
    - name: atr_compression
      description: "Suppress time stop if ATR compressed"
      enabled: true
      params:
        compression_ratio: 0.70

  cascade:
    enabled: true
    layers:
      - name: climax_detection
        priority: 1
        trigger: "80%+ gain AND up >30% in any 15-day window"
        response:
          sell_25_pct_immediate: true
          sell_25_pct_next_high: true
          sell_rest_below_10dma: true
      - name: distribution_days
        priority: 2
        trigger: "index down >0.2% on higher volume, count in last 25 days"
        response:
          count_3_4: tighten_stops
          count_5: reduce_25_pct
          count_6: reduce_to_50_pct
      - name: ad_divergence
        priority: 3
        trigger: "index new high AND A/D lower high"
        response: reduce_all_25_pct
      - name: new_highs_collapse
        priority: 4
        trigger: "Nifty500 new 52w highs count"
        response:
          below_50: trail_15_pct
          below_20: reduce_to_50_pct
      - name: tiered_trailing
        priority: 5
        trigger: "per-position gain-based trailing"
        response: phase_dependent_trail

# ─── Monster Stock Detection ─────────────────────────────────
monster:
  enabled: true
  score_threshold: 80       # LOCKED
  gain_gate: 0.40           # LOCKED (must have 40% gain to activate override)
  criteria:
    - signal: rs_rank_elite
      points: 25
      condition: "RS rank >= 90th percentile"
    - signal: consolidation_count
      points: 20
      condition: "3+ prior institutional accumulation bases"
    - signal: momentum_quality
      points: 20
      condition: "70%+ of weekly closes positive"
    - signal: sector_leader
      points: 15
      condition: "sector rank = #1"
    - signal: eps_acceleration_sustained
      points: 10
      condition: "EPS acceleration 4+ consecutive quarters"
    - signal: base_depth_contracting
      points: 10
      condition: "each successive base shallower than prior"
    - signal: sector_outperformance
      points: 10
      condition: "sector outperformance >= 2x over 6 months"
      lock: ESTIMATE

# ─── Turnaround Watch ────────────────────────────────────────
turnaround_watch:
  enabled: true
  conditions:
    - "EPS negative in >= 2 of last 8 quarters"
    - "EPS improving monotonically for last 4 quarters"
    - "Most recent quarter EPS > 0"
    - "Revenue growing > 10% YoY"
    - "EPS hard block still active (< 2 of 4 quarters positive)"
  suppression:
    - "pledge > threshold"
    - "SEBI fine active"
    - "business pivots >= 3 in 5 years"
    - "OCF negative 3+ of 4 quarters"

# ─── Position Sizing ─────────────────────────────────────────
position_sizing:
  base_risk_pct: 1.0         # FREE: update after Test 10
  position_floor_pct: 2.0
  position_ceiling_pct: 20.0
  max_sector_concentration: 0.30

  adjustments:
    - name: beta_reduction
      enabled: true
      condition: "beta > 2.5"
      reduction: 0.40
    - name: thin_float
      enabled: true
      condition: "promoter > 75% AND not PSU"
      reduction: 0.40
      additional: "require confirmed bulk deal"
    - name: correlation
      enabled: true
      threshold_high: 0.85
      threshold_moderate: 0.70
      reduction_high: 0.50
      reduction_moderate: 0.25
      lookback_days: 60
      min_overlap_days: 30

# ─── Signal Lifecycle ────────────────────────────────────────
signals:
  states: [pending, confirmed, failed, expired]
  confirmation:
    method: close_above_pivot  # Day 2+ close > pivot
    max_gap_pct: 0.03          # Expire if next-day open gaps > 3%
  tiering:
    tier_1:
      conditions:
        - breakout_confirmed: true
        - regime: [strong_bull, bull]
        - composite_score_min: 75
    tier_2:
      conditions:
        - composite_score_min: 65
    tier_3:
      conditions:
        - composite_score_min: 55
        - or_earnings_within_days: 10

# ─── Backtest Configuration ──────────────────────────────────
backtest:
  transaction_costs:
    entry_slippage: 0.005
    exit_slippage: 0.005
    brokerage_per_side: 0.001
    stt_sell: 0.001
    exchange_per_side: 0.0005
  periods:
    in_sample: ["2010-01-01", "2022-12-31"]
    out_of_sample: ["2023-01-01", "2024-12-31"]  # LOCKED before code
  initial_capital: 10000000   # Rs 1 crore
  rebalance_frequency: monthly

# ─── Pipeline Configuration ──────────────────────────────────
pipeline:
  schedule: "0 11 * * 1-5"   # 4:30 PM IST (UTC)
  timeout_minutes: 60
  retry:
    max_attempts: 3
    delay_minutes: 15
  data_quality:
    max_missing_stocks_pct: 5
    bse_divergence_threshold: 0.005
  notifications:
    on_success: [email]
    on_failure: [email, whatsapp]
```

### 3.2 Strategy Inheritance

Strategies can extend a base strategy, overriding only what changes:

```yaml
# strategies/v16_aggressive.yaml
meta:
  name: "MomentumEdge v16 — Aggressive"
  base_strategy: "strategies/momentum_edge_v16.yaml"

# Only override what differs
position_sizing:
  base_risk_pct: 2.0

exits:
  phases:
    - name: prove_it
      gain_range: [0.0, 0.25]
      rules:
        - type: fixed_stop
          stop_pct: 0.10  # Wider stop
```

### 3.3 Parameter Lock Enforcement

```
LOCKED    — Cannot be changed without explicit unlock + justification log
FREE      — Open for backtesting sweep
ESTIMATE  — Initial value, must be validated by specific backtest gate
```

The engine enforces this: attempting to sweep a LOCKED parameter raises an error unless `--override-locks` is passed with a reason that gets logged.

---

## 4. Module Plugin System

### 4.1 Scorer Interface

Every scoring module implements the same abstract interface:

```python
# src/momentum_edge/core/interfaces.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from sqlalchemy.orm import Session

@dataclass
class ScoreResult:
    """Output from any scoring module."""
    symbol: str
    score: float
    max_possible: float
    components: dict[str, float]   # Breakdown for audit
    metadata: dict | None = None   # Optional debug info

class ScorerPlugin(ABC):
    """Base class for all scoring modules."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier matching strategy YAML key."""

    @abstractmethod
    def score(
        self,
        symbol: str,
        date: date,
        session: Session,
        params: dict,
    ) -> ScoreResult:
        """Compute score for a single stock on a given date."""

    def validate_params(self, params: dict) -> list[str]:
        """Return list of validation errors. Empty = valid."""
        return []
```

### 4.2 Filter Interface

```python
@dataclass
class FilterResult:
    symbol: str
    passed: bool
    reason: str | None = None     # Why it was blocked
    data_missing: bool = False    # True = excluded due to missing data

class FilterPlugin(ABC):

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def check(
        self,
        symbol: str,
        date: date,
        session: Session,
        params: dict,
    ) -> FilterResult: ...
```

### 4.3 Exit Rule Interface

```python
@dataclass
class ExitDecision:
    should_exit: bool
    exit_pct: float = 1.0          # Partial exit support (0.25, 0.50, 1.0)
    new_stop: float | None = None  # Update stop without exiting
    rule_name: str = ""
    reason: str = ""

class ExitRulePlugin(ABC):

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def priority(self) -> int:
        """Lower = higher priority. First matching rule wins."""

    @abstractmethod
    def evaluate(
        self,
        position: OpenPosition,
        market_data: MarketSnapshot,
        regime: RegimeState,
        params: dict,
    ) -> ExitDecision: ...
```

### 4.4 Module Registry

```python
# src/momentum_edge/core/registry.py
class ModuleRegistry:
    """Auto-discovers and manages all plugin modules."""

    _scorers: dict[str, type[ScorerPlugin]] = {}
    _filters: dict[str, type[FilterPlugin]] = {}
    _exit_rules: dict[str, type[ExitRulePlugin]] = {}

    @classmethod
    def register_scorer(cls, scorer_cls: type[ScorerPlugin]):
        cls._scorers[scorer_cls.name] = scorer_cls

    @classmethod
    def get_scorer(cls, name: str) -> type[ScorerPlugin]:
        if name not in cls._scorers:
            raise KeyError(f"Scorer '{name}' not registered. "
                           f"Available: {list(cls._scorers.keys())}")
        return cls._scorers[name]

    # Similar for filters, exit_rules
    # Auto-discovery via entry_points or directory scanning
```

Modules self-register via decorator:

```python
# src/momentum_edge/scoring/momentum.py
from momentum_edge.core.registry import ModuleRegistry
from momentum_edge.core.interfaces import ScorerPlugin, ScoreResult

@ModuleRegistry.register_scorer
class MomentumScorer(ScorerPlugin):
    name = "momentum"

    def score(self, symbol, date, session, params) -> ScoreResult:
        weights = params["weights"]
        # ... compute using params, not hardcoded constants
        return ScoreResult(
            symbol=symbol,
            score=weighted_momentum,
            max_possible=40.0,
            components={
                "mom_12_1m": mom_12_1m * weights["mom_12_1m"],
                "mom_6m": mom_6m * weights["mom_6m"],
                "mom_3m": mom_3m * weights["mom_3m"],
            }
        )
```

### 4.5 Adding a New Module

To add a new scoring factor (e.g., "earnings_surprise"):

1. **Create the module** — `src/momentum_edge/scoring/earnings_surprise.py`
2. **Implement `ScorerPlugin`** — with `name = "earnings_surprise"`
3. **Add to strategy YAML** — under `scoring.modules`
4. **Done.** No changes to `runner.py`, `composite_score.py`, or any other file.

```yaml
# Just add to strategy YAML
scoring:
  modules:
    # ... existing modules ...
    - name: earnings_surprise
      enabled: true
      weight: 0.05
      module: earnings_surprise
      function: score_earnings_surprise
      params:
        sue_threshold_high: 50
        sue_threshold_moderate: 25
        lookback_days: 60
```

---

## 5. Rule Engine

### 5.1 Declarative Rules

Instead of `if` chains in Python, rules are declared as data structures and evaluated by a generic engine:

```python
# src/momentum_edge/core/rule_engine.py
@dataclass
class Rule:
    name: str
    enabled: bool
    priority: int
    condition: Callable[..., bool]
    action: Callable[..., Any]
    params: dict

class RuleChain:
    """Evaluates rules in priority order. First match wins (for exits)
    or all matches accumulate (for scoring)."""

    def __init__(self, rules: list[Rule], mode: str = "first_match"):
        self.rules = sorted(rules, key=lambda r: r.priority)
        self.mode = mode  # "first_match" for exits, "accumulate" for bonuses

    def evaluate(self, context: dict) -> list[tuple[Rule, Any]]:
        results = []
        for rule in self.rules:
            if not rule.enabled:
                continue
            if rule.condition(context, rule.params):
                result = rule.action(context, rule.params)
                results.append((rule, result))
                if self.mode == "first_match":
                    break
        return results
```

### 5.2 Exit Rules as Declarations

The 4-phase exit engine becomes a set of rule chains, one per phase:

```python
class PhaseBasedExitEngine:
    def __init__(self, strategy_config: dict):
        self.phases = {}
        for phase_config in strategy_config["exits"]["phases"]:
            rules = [self._build_rule(r) for r in phase_config["rules"]]
            self.phases[phase_config["name"]] = RuleChain(
                rules, mode="first_match"
            )

    def evaluate(self, position, market_data, regime):
        phase = self._determine_phase(position)
        chain = self.phases[phase]
        return chain.evaluate({
            "position": position,
            "market_data": market_data,
            "regime": regime,
        })

    def _determine_phase(self, position) -> str:
        gain = position.unrealized_gain_pct
        if position.monster_override_active and gain >= 0.40:
            return "monster_run"
        if gain >= 2.0:
            return "monster_run"
        if gain >= 1.0:
            return "working_compounder"
        if gain >= 0.25:
            return "let_it_run"
        return "prove_it"
```

### 5.3 Hard Blocks as Declarations

```python
class HardBlockEngine:
    def __init__(self, strategy_config: dict):
        self.blocks = []
        for block_config in strategy_config["universe"]["hard_blocks"]:
            if block_config["enabled"]:
                filter_cls = ModuleRegistry.get_filter(block_config["name"])
                self.blocks.append((filter_cls(), block_config.get("params", {})))

    def check_all(self, symbol, date, session) -> tuple[bool, list[str]]:
        """Returns (passed, [reasons_for_failure])."""
        failures = []
        for filter_instance, params in self.blocks:
            result = filter_instance.check(symbol, date, session, params)
            if not result.passed:
                failures.append(f"{filter_instance.name}: {result.reason}")
        return len(failures) == 0, failures
```

---

## 6. Composite Scoring

### 6.1 Weighted Composition

Replace the naive sum with explicit weighting:

```python
class CompositeScorer:
    def __init__(self, strategy_config: dict):
        self.method = strategy_config["scoring"]["composite_method"]
        self.module_configs = [
            m for m in strategy_config["scoring"]["modules"]
            if m["enabled"]
        ]

    def compute(self, symbol, date, session) -> CompositeResult:
        components = {}
        total_weight = 0

        for config in self.module_configs:
            scorer = ModuleRegistry.get_scorer(config["name"])()
            result = scorer.score(symbol, date, session, config["params"])

            if self.method == "weighted_sum":
                # Normalize to 0-1 range, then apply weight
                normalized = result.score / result.max_possible if result.max_possible > 0 else 0
                weighted = normalized * config["weight"]
                components[config["name"]] = {
                    "raw": result.score,
                    "normalized": normalized,
                    "weight": config["weight"],
                    "weighted": weighted,
                    "breakdown": result.components,
                }
                total_weight += config["weight"]

        # Final score normalized to 0-100
        composite = sum(c["weighted"] for c in components.values())
        if total_weight > 0:
            composite = (composite / total_weight) * 100

        return CompositeResult(
            symbol=symbol,
            date=date,
            composite_score=composite,
            components=components,
            strategy_hash=self.strategy_hash,
        )
```

### 6.2 Alternative Composition Methods

The `composite_method` field supports:

| Method | Description | Use Case |
|--------|-------------|----------|
| `weighted_sum` | Normalize each component to 0-1, apply weights, scale to 0-100 | Default production |
| `rank_average` | Rank all stocks on each factor, average ranks with weights | Robust to outliers |
| `z_score_sum` | Z-score each factor, weighted sum | When distributions are known |

---

## 7. Versioned Results

### 7.1 Strategy Hashing

Every pipeline run computes a deterministic hash of its strategy configuration:

```python
import hashlib, json

def compute_strategy_hash(strategy_config: dict) -> str:
    """SHA-256 of the full strategy config, excluding meta fields."""
    config_copy = {k: v for k, v in strategy_config.items() if k != "meta"}
    canonical = json.dumps(config_copy, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode()).hexdigest()[:12]
```

### 7.2 Result Tagging

Every row in `scores`, `watchlist`, and `backtest_results` includes:

```sql
ALTER TABLE scores ADD COLUMN strategy_hash VARCHAR(12);
ALTER TABLE scores ADD COLUMN strategy_version VARCHAR(20);
ALTER TABLE watchlist ADD COLUMN strategy_hash VARCHAR(12);
ALTER TABLE backtest_results ADD COLUMN strategy_hash VARCHAR(12);
ALTER TABLE backtest_results ADD COLUMN strategy_config JSONB;  -- Full snapshot
```

This enables:
- **Reproducibility** — "What watchlist did v16.0.0 produce on 2026-03-15?"
- **A/B comparison** — "How did v16 vs v7 score RELIANCE on the same date?"
- **Audit trail** — "Which parameter set produced this backtest CAGR?"

---

## 8. Pipeline Orchestrator

### 8.1 Phase-Aware Runner

```python
class PipelineOrchestrator:
    def __init__(self, strategy_path: str):
        self.config = load_strategy(strategy_path)
        self.strategy_hash = compute_strategy_hash(self.config)
        self.hard_blocks = HardBlockEngine(self.config)
        self.composite = CompositeScorer(self.config)
        self.exit_engine = PhaseBasedExitEngine(self.config)
        self.position_sizer = PositionSizer(self.config)
        self.regime_detector = RegimeDetector(self.config)

    def run(self, date: date, session: Session):
        # Phase 1: Data ingestion (unchanged)
        self._ingest_data(date, session)

        # Phase 2: Compute indicators for all stocks
        self._compute_indicators(date, session)

        # Phase 3: Detect market regime
        regime = self.regime_detector.classify(date, session)

        # Phase 4: Universe filtering
        universe = self._get_active_stocks(session)
        eligible = []
        for symbol in universe:
            passed, reasons = self.hard_blocks.check_all(symbol, date, session)
            if passed:
                eligible.append(symbol)
            else:
                self._log_exclusion(symbol, date, reasons, session)

        # Phase 5: Score all eligible stocks
        scores = []
        for symbol in eligible:
            result = self.composite.compute(symbol, date, session)
            result.regime = regime
            scores.append(result)

        # Phase 6: Rank and generate watchlist
        scores.sort(key=lambda s: s.composite_score, reverse=True)
        watchlist = self._apply_regime_filter(scores, regime)

        # Phase 7: Process exits for open positions
        self._process_exits(date, regime, session)

        # Phase 8: Generate signals for new entries
        self._generate_signals(watchlist, regime, session)

        # Phase 9: Persist results (tagged with strategy hash)
        self._persist_results(scores, watchlist, date, session)

        # Phase 10: Notifications
        self._send_notifications(watchlist, regime)
```

### 8.2 Pipeline Checkpoint Recovery

```python
class PipelineCheckpoint:
    """Enables restart from last successful phase after failure."""

    def __init__(self, date: date, session: Session):
        self.date = date
        self.session = session

    def mark_complete(self, phase: str):
        """Record phase completion in pipeline_log table."""
        self.session.execute(
            insert(PipelineLog).values(
                date=self.date,
                phase=phase,
                status="complete",
                completed_at=datetime.utcnow(),
            )
        )

    def last_completed_phase(self) -> str | None:
        """Return the last completed phase for this date."""
        result = self.session.query(PipelineLog).filter_by(
            date=self.date, status="complete"
        ).order_by(PipelineLog.completed_at.desc()).first()
        return result.phase if result else None
```

---

## 9. Backtesting with Parameter Sweeps

### 9.1 Parameter Grid

```python
class ParameterSweep:
    """Generate all combinations of FREE parameters for backtesting."""

    def __init__(self, strategy_config: dict):
        self.base_config = strategy_config
        self.free_params = self._extract_free_params()

    def _extract_free_params(self) -> dict[str, list]:
        """Walk the config tree, find all params with test_range."""
        free = {}
        # Recursively find params with test_range defined
        # e.g., {"universe.hard_blocks.market_cap_band.min_cr": [1000, 1500, 2000]}
        return free

    def generate_configs(self) -> Iterator[dict]:
        """Yield all parameter combinations."""
        keys = list(self.free_params.keys())
        values = list(self.free_params.values())
        for combo in itertools.product(*values):
            config = deep_copy(self.base_config)
            for key, val in zip(keys, combo):
                set_nested(config, key, val)
            yield config

    def count(self) -> int:
        return reduce(lambda a, b: a * b,
                       [len(v) for v in self.free_params.values()], 1)
```

### 9.2 Sweep Runner

```python
class BacktestSweepRunner:
    def __init__(self, strategy_path: str):
        self.config = load_strategy(strategy_path)
        self.sweep = ParameterSweep(self.config)

    def run_sweep(self, session: Session) -> pd.DataFrame:
        results = []
        total = self.sweep.count()
        logger.info(f"Running {total} parameter combinations")

        for i, config in enumerate(self.sweep.generate_configs()):
            logger.info(f"Sweep {i+1}/{total}: {compute_strategy_hash(config)}")
            backtester = Backtester(config)
            metrics = backtester.run(session)
            metrics["strategy_hash"] = compute_strategy_hash(config)
            metrics["params"] = config  # Store full config for reference
            results.append(metrics)

        return pd.DataFrame(results).sort_values("sharpe_ratio", ascending=False)
```

### 9.3 Walk-Forward with Adversarial Folds

```python
class WalkForwardValidator:
    def __init__(self, strategy_config: dict):
        self.config = strategy_config
        self.folds = self._build_folds()

    def _build_folds(self) -> list[dict]:
        return [
            # Standard folds
            {"train": ("2010-01-01", "2016-12-31"), "test": ("2017-01-01", "2018-12-31")},
            {"train": ("2010-01-01", "2018-12-31"), "test": ("2019-01-01", "2020-12-31")},
            {"train": ("2010-01-01", "2020-12-31"), "test": ("2021-01-01", "2022-12-31")},
            # Adversarial fold (non-bull training only)
            {
                "train": ("2015-01-01", "2016-12-31", "2018-01-01", "2018-12-31",
                          "2022-01-01", "2022-12-31"),
                "test": ("2019-01-01", "2019-12-31"),
                "adversarial": True,
                "gate": "sharpe >= 50% of folds 1-4 average"
            },
        ]
```

---

## 10. Database Schema Evolution

### 10.1 New Tables

```sql
-- Strategy parameter snapshots
CREATE TABLE strategy_snapshots (
    id SERIAL PRIMARY KEY,
    strategy_hash VARCHAR(12) NOT NULL UNIQUE,
    strategy_version VARCHAR(20),
    config JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Pipeline execution log with checkpoints
CREATE TABLE pipeline_log (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    phase VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL,  -- 'started', 'complete', 'failed'
    strategy_hash VARCHAR(12),
    duration_seconds FLOAT,
    error_message TEXT,
    completed_at TIMESTAMPTZ,
    UNIQUE(date, phase)
);

-- Exclusion audit trail
CREATE TABLE exclusion_log (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    block_name VARCHAR(50) NOT NULL,
    reason TEXT,
    data_missing BOOLEAN DEFAULT FALSE,
    strategy_hash VARCHAR(12)
);

-- Turnaround watch entries
CREATE TABLE turnaround_watch (
    id SERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    detected_date DATE NOT NULL,
    eps_trend TEXT,              -- JSON array of last 8 quarters
    suppressed BOOLEAN DEFAULT FALSE,
    suppression_reason TEXT,
    entry_trigger_date DATE,    -- When EPS block expected to clear
    status VARCHAR(20) DEFAULT 'watching',
    UNIQUE(symbol, detected_date)
);

-- Data quality alerts
CREATE TABLE data_quality_alerts (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    alert_type VARCHAR(50),     -- 'bse_divergence', 'missing_field', etc.
    symbol VARCHAR(20),
    details JSONB,
    resolved BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Blocked order attempts (immutable SEBI audit trail)
CREATE TABLE blocked_order_attempts (
    id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    user_id INTEGER,
    block_reason TEXT NOT NULL,
    strategy_hash VARCHAR(12),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

### 10.2 Schema Changes to Existing Tables

```sql
-- scores: add strategy versioning
ALTER TABLE scores ADD COLUMN strategy_hash VARCHAR(12);
ALTER TABLE scores ADD COLUMN component_breakdown JSONB;

-- watchlist: add strategy versioning
ALTER TABLE watchlist ADD COLUMN strategy_hash VARCHAR(12);

-- open_positions / performance_log: monster + exit phase tracking
ALTER TABLE performance_log ADD COLUMN monster_score FLOAT;
ALTER TABLE performance_log ADD COLUMN monster_override_active BOOLEAN DEFAULT FALSE;
ALTER TABLE performance_log ADD COLUMN rs_below_floor_weeks INTEGER DEFAULT 0;
ALTER TABLE performance_log ADD COLUMN entry_adv FLOAT;
ALTER TABLE performance_log ADD COLUMN correlation_adj_applied BOOLEAN DEFAULT FALSE;
ALTER TABLE performance_log ADD COLUMN exit_phase VARCHAR(30);
ALTER TABLE performance_log ADD COLUMN exit_rule_name VARCHAR(50);

-- regime_history: fast crash state
ALTER TABLE scores ADD COLUMN fast_crash_fired BOOLEAN DEFAULT FALSE;
ALTER TABLE scores ADD COLUMN fast_crash_active BOOLEAN DEFAULT FALSE;

-- fundamentals: new fields for expanded hard blocks
ALTER TABLE fundamentals ADD COLUMN ocf_cr FLOAT;
ALTER TABLE fundamentals ADD COLUMN other_income_cr FLOAT;
ALTER TABLE fundamentals ADD COLUMN trade_receivables_days FLOAT;
ALTER TABLE fundamentals ADD COLUMN is_financial BOOLEAN DEFAULT FALSE;

-- stocks: new fields
ALTER TABLE stocks ADD COLUMN sebi_fine_last_24m BOOLEAN DEFAULT FALSE;
ALTER TABLE stocks ADD COLUMN lodr_fine_last_12m BOOLEAN DEFAULT FALSE;
ALTER TABLE stocks ADD COLUMN sebi_investigation_active BOOLEAN DEFAULT FALSE;
ALTER TABLE stocks ADD COLUMN bse_code VARCHAR(20);
ALTER TABLE stocks ADD COLUMN industry VARCHAR(100);
ALTER TABLE stocks ADD COLUMN listing_date DATE;
ALTER TABLE stocks ADD COLUMN business_pivot_count INTEGER DEFAULT 0;
```

---

## 11. Proposed Directory Structure

```
src/momentum_edge/
├── core/                          # NEW — Framework layer
│   ├── interfaces.py              # ScorerPlugin, FilterPlugin, ExitRulePlugin
│   ├── registry.py                # ModuleRegistry (auto-discovery)
│   ├── rule_engine.py             # Rule, RuleChain (declarative evaluation)
│   ├── strategy_loader.py         # YAML loading, inheritance, validation
│   ├── strategy_hash.py           # Deterministic config hashing
│   └── composite.py               # CompositeScorer (weighted, rank-avg, z-score)
│
├── config.py                      # Pydantic env settings (unchanged)
│
├── scoring/                       # REPLACES ranking/ — all ScorerPlugin impls
│   ├── momentum.py                # MomentumScorer (was momentum_score.py)
│   ├── fundamental.py             # FundamentalScorer (was fundamental_bonus.py)
│   ├── accumulation.py            # AccumulationScorer (was accumulation_score.py)
│   ├── sector.py                  # SectorScorer (was sector_rotation.py)
│   ├── technical.py               # TechnicalScorer (was trend_template scoring)
│   ├── breakout.py                # BreakoutScorer (was breakout_patterns scoring)
│   └── monster.py                 # MonsterScorer (NEW)
│
├── filters/                       # REPLACES universe_filter.py — all FilterPlugin impls
│   ├── eps_junk.py
│   ├── market_cap.py
│   ├── liquidity.py
│   ├── surveillance.py
│   ├── ocf_quality.py             # NEW
│   ├── promoter_pledge.py         # NEW
│   ├── sebi_fine.py               # NEW
│   ├── ipo_age.py                 # NEW
│   └── business_pivot.py          # NEW
│
├── exits/                         # REPLACES engine/exits.py — all ExitRulePlugin impls
│   ├── fixed_stop.py
│   ├── trailing_stop.py
│   ├── rs_decay.py
│   ├── ma_weakness.py
│   ├── climax_run.py
│   ├── regime_exit.py
│   ├── time_stop.py
│   ├── cascade/                   # NEW — portfolio-level exit cascade
│   │   ├── climax_detection.py
│   │   ├── distribution_days.py
│   │   ├── ad_divergence.py
│   │   ├── new_highs_collapse.py
│   │   └── tiered_trailing.py
│   └── validation/                # NEW — exit validation layers
│       ├── trend_integrity.py
│       ├── volume_direction.py
│       └── atr_compression.py
│
├── regime/                        # REPLACES scanner/market_regime.py
│   ├── detector.py                # RegimeDetector (configurable signals)
│   ├── fast_crash.py              # NEW — Fast crash detector
│   └── bull_entry.py              # NEW — Bull market entry protocol
│
├── scanner/                       # Technical scanning (indicators only)
│   ├── indicators.py              # Indicator computation (unchanged)
│   └── patterns.py                # VCP/base detection logic (renamed)
│
├── engine/                        # Trading engine
│   ├── signals.py                 # Signal lifecycle (unchanged)
│   ├── position_sizing.py         # PositionSizer (reads from strategy config)
│   ├── turnaround.py              # NEW — Turnaround Watch
│   └── rebalancer.py              # NEW — Monthly rebalancing
│
├── pipeline/                      # Orchestration
│   ├── orchestrator.py            # PipelineOrchestrator (replaces runner.py)
│   ├── checkpoint.py              # NEW — Pipeline checkpoint recovery
│   └── cron.py                    # Cron scheduling (unchanged)
│
├── backtest/                      # Backtesting
│   ├── engine.py                  # Backtester (reads from strategy config)
│   ├── sweep.py                   # NEW — Parameter sweep runner
│   ├── walkforward.py             # Walk-forward (unchanged + adversarial folds)
│   └── gates.py                   # NEW — Backtest pass/fail gates
│
├── data/                          # Data ingestion (unchanged)
│   ├── prices.py
│   ├── delivery.py
│   ├── screener.py
│   ├── fii_dii.py
│   ├── bulk_deals.py
│   ├── surveillance.py
│   ├── corporate_actions.py
│   └── bse_crosscheck.py         # NEW — BSE price cross-validation
│
├── db/
│   ├── models.py                  # SQLAlchemy models (extended)
│   └── session.py                 # Engine & session (unchanged)
│
├── api/                           # REST API
│   ├── app.py
│   ├── auth.py
│   └── routes/
│       ├── watchlist.py
│       ├── scores.py
│       ├── regime.py
│       ├── sectors.py
│       ├── stocks.py
│       ├── stock_detail.py
│       ├── signals.py
│       ├── fii_dii.py
│       ├── shareholding.py
│       ├── strategy.py           # NEW — strategy info endpoint
│       └── turnaround.py         # NEW — turnaround watch endpoint
│
├── notifications/
│   └── sender.py
│
├── utils/
│   ├── logger.py
│   └── date_utils.py
│
strategies/                        # NEW — Strategy YAML files (top-level)
├── momentum_edge_v7.yaml
├── momentum_edge_v16.yaml
├── v16_aggressive.yaml
├── v16_conservative.yaml
└── experimental/
    └── test_momentum_weights.yaml
```

---

## 12. Migration Path

### Phase 1: Foundation (Week 1-2)

| Task | Description |
|------|-------------|
| Create `core/` framework | `interfaces.py`, `registry.py`, `strategy_loader.py` |
| Write v7 strategy YAML | Extract all current hardcoded params into `strategies/momentum_edge_v7.yaml` |
| Strategy loader + validation | Pydantic models for strategy YAML with type checking |
| Strategy hashing | Deterministic hash for result tagging |

**Outcome:** Strategy YAML exists but is not yet consumed. All current code still works.

### Phase 2: Plugin Migration (Week 3-4)

| Task | Description |
|------|-------------|
| Convert scorers to plugins | Wrap `momentum_score.py`, `fundamental_bonus.py`, etc. in `ScorerPlugin` interface |
| Convert filters to plugins | Split `universe_filter.py` into individual `FilterPlugin` classes |
| Build `CompositeScorer` | Weighted composition replacing naive sum |
| Update `runner.py` -> `orchestrator.py` | Use registry + strategy config instead of hardcoded module calls |

**Outcome:** Pipeline runs from strategy YAML. Changing a parameter = editing YAML, not Python.

### Phase 3: Exit Engine Redesign (Week 5-7)

| Task | Description |
|------|-------------|
| Build `ExitRulePlugin` interface | Abstract base for all exit rules |
| Implement phase-based exit engine | 4-phase gain-based framework from v16 |
| Implement exit cascade | 5-layer portfolio-level cascade (E1-E5) |
| Implement validation layers | Trend integrity, volume direction, ATR compression |
| Write v16 strategy YAML | Full v16 config in YAML |

**Outcome:** Exit engine is configurable. v7 and v16 exit behaviors selectable via YAML.

### Phase 4: New Subsystems (Week 8-10)

| Task | Description |
|------|-------------|
| Fast crash detector | `regime/fast_crash.py` |
| Monster stock detection | `scoring/monster.py` |
| Turnaround watch | `engine/turnaround.py` |
| Bull entry protocol | `regime/bull_entry.py` |
| Expanded hard blocks | OCF, pledge, SEBI, IPO age, business pivot filters |
| Correlation-aware sizing | Update `position_sizing.py` |

### Phase 5: Backtest Infrastructure (Week 11-12)

| Task | Description |
|------|-------------|
| Parameter sweep runner | `backtest/sweep.py` |
| Backtest gates | `backtest/gates.py` (pass/fail criteria) |
| Adversarial walk-forward | Fold 8 implementation |
| Result versioning | Strategy hash on all output tables |
| Pipeline checkpoints | `pipeline/checkpoint.py` |

---

## 13. CLI Integration

```bash
# Run pipeline with specific strategy
PYTHONPATH=src uv run python main.py run --strategy strategies/momentum_edge_v16.yaml

# Run with v7 for comparison
PYTHONPATH=src uv run python main.py run --strategy strategies/momentum_edge_v7.yaml

# View strategy diff
PYTHONPATH=src uv run python main.py strategy diff v7 v16

# Validate strategy file
PYTHONPATH=src uv run python main.py strategy validate strategies/momentum_edge_v16.yaml

# Parameter sweep backtest
PYTHONPATH=src uv run python main.py backtest sweep --strategy strategies/momentum_edge_v16.yaml

# Single-config backtest
PYTHONPATH=src uv run python main.py backtest run --strategy strategies/momentum_edge_v16.yaml

# List all registered modules
PYTHONPATH=src uv run python main.py modules list

# Show strategy hash for current run
PYTHONPATH=src uv run python main.py strategy hash strategies/momentum_edge_v16.yaml
```

---

## 14. API Additions

```
GET  /api/v1/strategy/current           — Active strategy metadata + hash
GET  /api/v1/strategy/params             — All configurable parameters + lock status
GET  /api/v1/scores/{symbol}/breakdown   — Full component breakdown for a stock
GET  /api/v1/exclusions/{date}           — Why stocks were excluded (audit trail)
GET  /api/v1/turnaround-watch            — Current turnaround watch entries
GET  /api/v1/pipeline/status             — Pipeline checkpoint status
GET  /api/v1/monster-scores              — Monster score leaderboard
GET  /api/v1/exits/cascade-state         — Current cascade layer states (E1-E5)
```

---

## 15. Risk Controls & Guardrails

### 15.1 Parameter Bounds

Every FREE parameter has declared bounds. The strategy loader rejects configs outside these bounds:

```yaml
# In the strategy schema definition
bounds:
  universe.hard_blocks.market_cap_band.min_cr:
    type: float
    min: 500
    max: 5000
    description: "Market cap minimum in crores"
  exits.phases.prove_it.rules.fixed_stop.stop_pct:
    type: float
    min: 0.03
    max: 0.15
    description: "Phase 1 stop loss percentage"
```

### 15.2 Lock Enforcement

```python
class LockEnforcer:
    def validate_sweep(self, base_config, sweep_params):
        for param_path in sweep_params:
            lock_status = get_lock_status(base_config, param_path)
            if lock_status == "LOCKED":
                raise LockedParameterError(
                    f"Parameter '{param_path}' is LOCKED. "
                    f"Use --override-locks with justification to proceed."
                )
```

### 15.3 Data Quality Gates

```python
class DataQualityGate:
    def check_before_scoring(self, date, session, config):
        missing_pct = self._compute_missing_data_pct(date, session)
        threshold = config["pipeline"]["data_quality"]["max_missing_stocks_pct"]
        if missing_pct > threshold:
            raise DataQualityError(
                f"{missing_pct:.1f}% of stocks missing data "
                f"(threshold: {threshold}%)"
            )
```

---

## 16. Observability

### 16.1 Pipeline Metrics

Every pipeline run emits structured logs:

```json
{
  "event": "pipeline_phase_complete",
  "date": "2026-03-26",
  "phase": "scoring",
  "strategy_hash": "a1b2c3d4e5f6",
  "duration_seconds": 45.2,
  "stocks_scored": 1847,
  "stocks_excluded": 312,
  "regime": "bull",
  "watchlist_size": 23
}
```

### 16.2 Score Drift Detection

Track composite score distributions over time to detect parameter decay:

```python
class ScoreDriftMonitor:
    def check_drift(self, date, session):
        """Alert if score distribution has shifted significantly."""
        recent_scores = self._get_scores(date, lookback_days=20, session=session)
        historical_scores = self._get_scores(date, lookback_days=252, session=session)

        ks_stat, p_value = ks_2samp(recent_scores, historical_scores)
        if p_value < 0.01:
            self._alert(f"Score distribution drift detected (KS p={p_value:.4f})")
```

---

## 17. Summary

| Dimension | Current (v7) | Future Architecture |
|-----------|-------------|---------------------|
| Parameters | Hardcoded Python constants | YAML strategy files |
| Scoring modules | Inline functions in 6 files | Plugin system with registry |
| Composite score | Naive sum, no weights | Weighted composition (configurable method) |
| Exit rules | 9 hardcoded `if` chains | Declarative rule engine, phase-based |
| Hard blocks | 4 inline checks | Plugin filters, fail-closed on missing data |
| Backtesting | Single config only | Parameter sweep with combinatorial grids |
| Result tracking | No version info | Strategy hash on every output row |
| Adding a module | Edit 3-4 files | Create 1 file + add YAML entry |
| Strategy comparison | Manual code diff | `strategy diff v7 v16` CLI command |
| Lock enforcement | None | LOCKED/FREE/ESTIMATE with bounds validation |
| Pipeline recovery | Restart from scratch | Checkpoint-based resume |
| Audit trail | Minimal logging | Exclusion log, blocked orders, data quality alerts |

**Total estimated effort for full migration: 10-12 weeks** (can be phased — each phase delivers standalone value).

---

*End of Future Architecture Document — MomentumEdge v1.0*
