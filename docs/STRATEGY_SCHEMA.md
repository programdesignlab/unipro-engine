# MomentumEdge — Strategy YAML Schema Reference

File: `strategies/momentum_edge.yaml`

This is the single source of truth for all engine parameters. The file is validated at load time by 36 Pydantic models in `core/strategy.py`. A deterministic SHA-256 hash of the config (excluding `meta`) is computed and tagged on every pipeline output row for reproducibility.

Parameters marked **LOCKED** are research-backed and should not be swept without justification. Parameters marked **FREE** are tunable via backtesting parameter sweeps.

---

## `meta`

Strategy metadata. Not included in the strategy hash.

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Strategy display name |
| `version` | string | Semver version, bump on any param change |
| `description` | string | Human-readable summary |

---

## `universe`

Universe filtering configuration. Stocks that fail any enabled hard block are excluded from scoring entirely.

### `universe.hard_blocks[]`

Array of filter definitions. Each filter is dispatched by its `function` name to a handler in `ranking/universe_filter.py`.

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Unique filter identifier |
| `enabled` | bool | Set `false` to skip this filter |
| `function` | string | Handler function name in `_FILTER_FUNCTIONS` registry |
| `params` | object | Filter-specific parameters (passed as dict) |

### Hard Block Params

**market_cap_band:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `min_cr` | float | 1000 | Minimum market cap in crores. **FREE** |
| `max_cr` | float | 30000 | Maximum market cap in crores |

**liquidity:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `min_daily_traded_value_cr` | float | 15 | Min avg daily traded value (crores). **FREE** |

**surveillance:** No params. Checks `is_asm` / `is_esm` flags on the stock.

**eps_junk:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `min_positive_quarters` | int | 2 | Min quarters with EPS > 0 to pass |
| `lookback_quarters` | int | 4 | How many recent quarters to check |

**ocf_quality:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `max_negative_quarters` | int | 3 | Max negative OCF quarters allowed |
| `lookback_quarters` | int | 4 | Quarters to check |

Behavior: passes through if no OCF data ingested yet. Once OCF data exists for a stock, fail-closed applies.

**promoter_pledge:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `threshold_operational` | float | 0.20 | Max pledge % for operational companies |
| `threshold_infra` | float | 0.50 | Max pledge % for infra/power/construction |
| `infra_exception.de_falling` | bool | true | Allow infra if D/E is declining |
| `infra_exception.revenue_growth_min` | float | 0.30 | Min revenue growth for infra exception |

**sebi_fine:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `lookback_months` | int | 24 | Lookback window for SEBI fines |

**ipo_age:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `min_trading_days` | int | 200 | Min days since listing |

**business_pivot:** Currently disabled (data source TBD).

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `max_pivots` | int | 3 | Max business pivots in lookback |
| `lookback_years` | int | 5 | Years to check |

---

## `indicators`

Technical indicator computation parameters. Used by `scanner/indicators.py`.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `ma_periods` | int[] | [50, 150, 200] | Moving average periods |
| `ma_slope_lookback` | int | 20 | Days for MA200 slope calculation |
| `atr_period` | int | 14 | ATR lookback period |

### `indicators.momentum`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `lookback_3m` | int | 63 | 3-month momentum lookback (trading days) |
| `lookback_6m` | int | 126 | 6-month momentum lookback |
| `lookback_12m` | int | 252 | 12-month momentum lookback |
| `skip_1m` | int | 21 | Days to skip for 12-1m calculation |

### `indicators.volatility`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `vol_target_pct` | float | 20.0 | Target annualized volatility %. **LOCKED** (Barroso 2015) |
| `vol_scalar_max` | float | 2.0 | Maximum volatility scalar. **LOCKED** |
| `vol_lookback` | int | 20 | Days for 20-day rolling std dev |

### `indicators.momentum_quality`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `weekly_lookback` | int | 26 | Weeks for positive-close ratio |

### `indicators.rs`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `lookback_days` | int | 126 | RS vs Nifty 50 lookback |

### `indicators.ad_ratio`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `lookback_days` | int | 20 | A/D ratio lookback |

### `indicators.volume_ratios`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `short_period` | int | 20 | Short-term volume MA |
| `long_period` | int | 50 | Long-term volume MA |

### `indicators.week_52`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `lookback_days` | int | 252 | 52-week high/low lookback |

### `indicators.factor_weights`

Weights for cross-sectional momentum factor ranking. Must sum to 1.0.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `mom_3m` | float | 0.20 | 3-month momentum weight |
| `mom_6m` | float | 0.30 | 6-month momentum weight |
| `mom_12_1` | float | 0.25 | 12-minus-1 month weight |
| `mom_quality` | float | 0.15 | Momentum quality (weekly positive %) weight |
| `rs_score` | float | 0.10 | Relative strength vs Nifty weight |

---

## `scoring`

Composite scoring configuration.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `composite_method` | string | "weighted_sum" | Scoring method (only weighted_sum implemented) |

### `scoring.modules[]`

Array of scoring module definitions. Each module has a weight used for composite calculation.

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Module identifier (matches code lookup) |
| `enabled` | bool | Set `false` to exclude from scoring |
| `weight` | float | Relative weight in composite (should sum to ~1.0 across enabled modules) |
| `description` | string | Human-readable description |
| `params` | object | Module-specific parameters |

### Module: `momentum` (weight: 0.35)

No separate params. Score comes from `indicators.scaled_score` which is driven by `indicators.factor_weights` and `indicators.volatility` config above.

### Module: `fundamental_bonus` (weight: 0.20)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `score_range` | [int, int] | [-20, 30] | Min/max clamp range |
| `bonuses` | array | 14 entries | Positive scoring signals |
| `penalties` | array | 7 entries | Negative scoring signals |

Each bonus/penalty entry:

| Field | Type | Description |
|-------|------|-------------|
| `signal` | string | Signal identifier |
| `points` | int | Points awarded (positive for bonus, negative for penalty) |
| `condition` | string | Human-readable trigger condition |

**Bonuses (14):** eps_acceleration (+8), eps_growth_high (+5), eps_positive (+2), analyst_revision (+4), revenue_opm_simultaneous (+12), revenue_acceleration (+10), opm_expansion (+8), promoter_buying (+8), pead_sue_strong (+10), pead_sue_moderate (+6), market_cap_crossing (+6), low_de_strong (+3), low_de (+2), low_de_moderate (+1)

**Penalties (7):** high_de (-2), promoter_selling (-8), sebi_investigation (-10), lodr_fine (-3), debtors_critical (-5), debtors_warning (-3), ocf_quality_poor (-5)

### Module: `accumulation` (weight: 0.15)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `obv_bonus` | int | 5 | Points for rising OBV slope during base |
| `ad_ratio_threshold` | float | 0.60 | Min A/D ratio for bonus |
| `ad_ratio_bonus` | int | 4 | Points for A/D ratio above threshold |
| `inst_flow_bonus` | int | 1 | Points for positive institutional flow |
| `inst_flow_routing.low_promoter_threshold` | float | 0.65 | Below this: use FII+DII combined |
| `inst_flow_routing.high_promoter_threshold` | float | 0.75 | Above this: use bulk deals only |

### Module: `sector` (weight: 0.10)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `top_n` | int | 3 | Number of top sectors for bonus |
| `top_n_bonus` | float | 10 | Points for stocks in top sectors |
| `bottom_n` | int | 3 | Number of bottom sectors for penalty |
| `bottom_n_penalty` | float | -5 | Points for stocks in bottom sectors |
| `ranking_method` | string | "median_3m_momentum" | Method for sector ranking |

### Module: `technical` (weight: 0.12)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `conditions.price_above_ma50` | bool | true | Check adj_close > MA50 |
| `conditions.price_above_ma150` | bool | true | Check adj_close > MA150 |
| `conditions.price_above_ma200` | bool | true | Check adj_close > MA200 |
| `conditions.ma50_above_ma150` | bool | true | Check MA50 > MA150 |
| `conditions.ma150_above_ma200` | bool | true | Check MA150 > MA200 |
| `conditions.ma200_slope_rising` | bool | true | Check MA200 slope > 0 |
| `conditions.near_52w_high_pct` | float | 0.80 | Min proximity to 52-week high |
| `conditions.stage2_min_days` | int | 20 | Min consecutive days above MA200 |
| `base_score_max` | float | 12.0 | Max points from conditions (8 conditions) |
| `proximity_bonus_max` | float | 3.0 | Max proximity-to-high bonus |
| `technical_score_max` | float | 15.0 | Overall technical score cap |

### Module: `breakout` (weight: 0.08)

**`params.vcp`** — VCP (Volatility Contraction Pattern) detection:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `min_contractions` | int | 3 | Min contraction count. **FREE** |
| `max_depth_pct` | float | 40.0 | Max base depth %. **FREE** |
| `min_base_days` | int | 25 | Min base length (~5 weeks). **LOCKED** |
| `max_base_days` | int | 260 | Max base length (~52 weeks). **LOCKED** |
| `breakout_vol_ratio` | float | 1.5 | Min volume ratio for breakout. **FREE** |

**`params.entry_rules`** — 7 conditions for valid entry:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `max_gap_above_pivot` | float | 0.03 | Max next-day open gap above pivot (3%) |
| `min_close_strength` | float | 0.75 | Min (close-low)/(high-low) ratio |
| `max_extension_above_pivot` | float | 0.05 | Max close extension above pivot (5%) |
| `volume_confirmation` | bool | true | Require volume >= breakout_vol_ratio |
| `false_breakout_days` | int | 2 | Days to check for false breakout |
| `earnings_window_days` | int | 10 | Reject if earnings within N days |

---

## `regime`

Market regime detection and classification.

### `regime.signals[]`

Array of 6 regime signals. Each contributes 0-1 to the total score (max 6).

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Signal identifier |
| `description` | string | What it measures |
| `weight` | float | Contribution to score (typically 1.0) |
| `thresholds` | object | Signal-specific thresholds |

**Signals:** nifty_above_200ma, ma200_slope, breadth_50ma (bull: 60%, bear: 40%), highs_vs_lows, nifty_extension (sweet_spot: 15%, danger: 25%), momentum_12_1

### `regime.crash_indicator`

Dierkes & Krupski 2022 crash detection. Forces Full Bear when triggered.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `return_2yr_threshold` | float | -0.20 | 2-year return below this AND... |
| `rally_1m_threshold` | float | 0.10 | ...1-month return above this = crash |

### `regime.stability_days`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| (value) | int | 3 | Regime changes only after N consecutive days at new level |

### `regime.classifications[]`

Maps regime score ranges to allocation parameters.

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Regime name (strong_bull, bull, weak, bear, full_bear) |
| `score_range` | [float, float] | Min/max regime score for this classification |
| `equity_pct` | float | Max portfolio equity allocation (0-100) |
| `max_positions` | int | Max simultaneous positions |
| `risk_per_trade` | float | Risk % per trade |
| `portfolio_heat` | float | Max total open risk % |
| `exposure_label` | string | Human-readable label |

### `regime.fast_crash`

Independent crash detector (faster than 3-day regime stability rule).

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | bool | true | Enable/disable fast crash |
| `rolling_window_days` | int | 5 | Rolling window for decline check |
| `decline_threshold` | float | -0.08 | Nifty decline threshold (8%) |
| `response` | string | "sell_50_pct_all" | Action on trigger |
| `reset_lookback_days` | int | 10 | Days to check for reset |
| `overrides_monster` | bool | true | Also halves monster positions |

### `regime.bull_entry_protocol`

Structured 4-phase re-entry after Bear regime.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | bool | true | Enable/disable protocol |

**`phases[]`:**

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Phase name (capitulation, breadth_thrust, ad_confirmation, new_highs_expand) |
| `trigger` | string | Human-readable trigger condition |
| `capital_deploy` | float/null | Capital deployment fraction (0.0, 0.25, null = regime allocation) |

---

## `exits`

4-phase gain-based exit engine.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `framework` | string | "phase_based" | Exit framework type |

### `exits.phases[]`

Array of exit phases. Position enters a phase based on unrealised gain %.

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Phase name (prove_it, let_it_run, working_compounder, monster_run) |
| `gain_range` | [float, float/null] | Gain range [min, max]. null = unlimited |
| `rules` | array | Exit rules evaluated in priority order (first match wins) |

### Exit Rule Types

Each rule in `phases[].rules[]` has a `type` field plus type-specific params:

**`fixed_stop`** — Fixed percentage stop from entry.

| Field | Type | Description |
|-------|------|-------------|
| `stop_pct` | float | Stop distance as fraction (0.08 = 8%). **FREE** |

**`trailing_stop`** — Trail from recent high.

| Field | Type | Description |
|-------|------|-------------|
| `trail_pct` | float | Trail distance as fraction. **FREE** |
| `reference` | string | High reference period ("10_week_high") |
| `applies_to` | string | Optional: "core_50pct" for monster partial |

**`rs_decay`** — Exit on sustained RS weakness.

| Field | Type | Description |
|-------|------|-------------|
| `floor_pct` | int | RS percentile floor (30 = bottom 30%) |
| `persist_weeks` | int | Consecutive weeks below floor to trigger. **LOCKED** |

**`ma_weakness`** — Close below moving average.

| Field | Type | Description |
|-------|------|-------------|
| `ma_period` | int | MA period (21 for 21DMA) |
| `confirm_days` | int | Consecutive days below MA to trigger |
| `volume_check` | bool | Require heavy volume confirmation |
| `trend_integrity_override` | bool | Allow trend integrity layer to suppress |

**`climax_run`** — Rapid gain = partial exit.

| Field | Type | Description |
|-------|------|-------------|
| `gain_threshold` | float | Min gain in window (0.20 = 20%) |
| `time_window_days` | int | Window for gain check |
| `sell_pct` | float | Fraction to sell (0.50 = 50%) |

**`regime_exit`** — Bear/crash regime response.

| Field | Type | Description |
|-------|------|-------------|
| `trigger` | string | "bear_or_crash" |
| `action` | string | "sell_20pct_per_day" |
| `days` | int | Days to fully exit |

**`ma_breach`** — Monster phase: close below key MA.

| Field | Type | Description |
|-------|------|-------------|
| `ma_period` | int | MA period (50 = 10-week). **LOCKED** |
| `primary` | bool | Is this the primary exit signal |

**`partial_exit`** — Staged selling at new highs.

| Field | Type | Description |
|-------|------|-------------|
| `at_new_highs` | bool | Trigger at new highs |
| `sell_pct` | float | Fraction per partial (0.25 = 25%) |
| `max_partials` | int | Max number of partial exits |

### `exits.validation_layers[]`

Layers that can suppress or override exit signals.

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Layer name |
| `enabled` | bool | Enable/disable |
| `description` | string | What it does |
| `params` | object | Layer-specific params |

**`volume_direction` params:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `hold_threshold` | float | 0.75 | Vol ratio below this on down day = hold |
| `distribution_threshold` | float | 1.50 | Vol ratio above this on down day = instant exit |
| `distribution_exit_pct` | float | 0.25 | Fraction to exit on distribution |

**`atr_compression` params:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `compression_ratio` | float | 0.70 | ATR now < ATR at entry * this = suppress time stop |

### `exits.cascade`

5-layer portfolio-level exit cascade. Operates on all open positions daily.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | bool | true | Enable/disable cascade |

**`layers[]`:**

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Layer identifier |
| `priority` | int | Lower = higher priority |
| `trigger` | object/string | Trigger conditions |
| `response` | object/string | Actions to take |

**Layers:** climax_detection (P1), distribution_days (P2), ad_divergence (P3), new_highs_collapse (P4), tiered_trailing (P5)

---

## `monster`

Monster stock detection (Bessembinder 2018).

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | bool | true | Enable/disable |
| `score_threshold` | int | 80 | Min score for monster status. **LOCKED** |
| `gain_gate` | float | 0.40 | Min unrealised gain for exit override. **LOCKED** |

### `monster.criteria[]`

7 scoring criteria, max total 110 points (threshold is 80).

| Field | Type | Description |
|-------|------|-------------|
| `signal` | string | Criterion identifier |
| `points` | int | Points if met |
| `condition` | string | Human-readable condition |

---

## `turnaround_watch`

Early detection of business turnarounds.

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `enabled` | bool | true | Enable/disable |

### `turnaround_watch.conditions`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `min_negative_quarters` | int | 2 | Min quarters with negative EPS |
| `lookback_quarters` | int | 8 | Quarters to check for loss phase |
| `monotonic_improvement_quarters` | int | 4 | Consecutive quarters of EPS improvement |
| `latest_eps_positive` | bool | true | Most recent EPS must be > 0 |
| `min_revenue_growth_yoy` | float | 0.10 | Min revenue growth (10%) |

### `turnaround_watch.suppression`

Array of string conditions. If any is true, the candidate is suppressed from the dashboard.

---

## `position_sizing`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `base_risk_pct` | float | 1.0 | Base risk per trade %. **FREE** |
| `position_floor_pct` | float | 2.0 | Min position size (% of portfolio) |
| `position_ceiling_pct` | float | 20.0 | Max position size (% of portfolio) |
| `max_sector_concentration` | float | 0.30 | Max single-sector exposure (30%) |

### `position_sizing.adjustments[]`

Multiplicative size adjustments. Applied after base sizing.

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Adjustment identifier |
| `enabled` | bool | Enable/disable |
| `condition` | string | Human-readable trigger |
| `reduction` | float | Size reduction fraction (0.40 = reduce by 40%) |

**`correlation` adjustment (additional fields):**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `threshold_high` | float | 0.85 | Correlation above this = high reduction |
| `threshold_moderate` | float | 0.70 | Correlation above this = moderate reduction |
| `reduction_high` | float | 0.50 | Size reduction for high correlation |
| `reduction_moderate` | float | 0.25 | Size reduction for moderate correlation |
| `lookback_days` | int | 60 | Days for correlation calculation |
| `min_overlap_days` | int | 30 | Min overlapping data points |

---

## `signals`

Signal lifecycle configuration.

### `signals.confirmation`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `method` | string | "close_above_pivot" | Confirmation method |
| `max_gap_pct` | float | 0.03 | Max next-day gap (3%) before expiry |

### `signals.tiering`

**`tier_1`:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `score_min` | float | 75.0 | Min composite score |
| `regimes` | string[] | ["Strong Bull", "Bull"] | Required regimes |
| `breakout_required` | bool | true | Must have confirmed breakout |

**`tier_2`:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `score_min` | float | 65.0 | Min composite score |

**`tier_3`:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `score_min` | float | 55.0 | Min composite score |
| `or_earnings_within_days` | int | 10 | Auto-tier-3 if earnings within N days |

### `signals.earnings_window_days`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| (value) | int | 10 | Earnings proximity window |

---

## `backtest`

### `backtest.transaction_costs`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `entry_slippage` | float | 0.005 | Entry slippage (0.5%) |
| `exit_slippage` | float | 0.005 | Exit slippage (0.5%) |
| `brokerage_per_side` | float | 0.001 | Brokerage (0.1%) |
| `stt_sell` | float | 0.001 | Securities Transaction Tax on sell (0.1%) |
| `exchange_per_side` | float | 0.0005 | Exchange charges (0.05%) |

Total round-trip cost: ~0.4%

### `backtest.periods`

| Field | Type | Description |
|-------|------|-------------|
| `in_sample` | [date, date] | Training period |
| `out_of_sample` | [date, date] | Validation period (locked before code) |

### Other

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `initial_capital` | int | 10000000 | Starting capital (Rs 1 crore) |
| `rebalance_frequency` | string | "monthly" | Rebalance cadence |

---

## `pipeline`

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `schedule` | string | "0 11 * * 1-5" | Cron expression (UTC) |
| `timeout_minutes` | int | 60 | Max pipeline runtime |
| `data_quality.max_missing_stocks_pct` | int | 5 | Alert if > N% stocks missing data |
| `notifications.on_success` | string[] | ["email"] | Notification channels on success |
| `notifications.on_failure` | string[] | ["email"] | Notification channels on failure |
