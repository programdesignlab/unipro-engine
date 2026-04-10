# MomentumEdge — Implementation Guide

## Strategy Configuration

All engine parameters are defined in `strategies/momentum_edge.yaml` and validated by Pydantic models in `core/strategy.py`.

```python
from momentum_edge.core.strategy import load_strategy

strategy = load_strategy("strategies/momentum_edge.yaml")
print(strategy.meta.version)          # "16.0.0"
print(strategy.strategy_hash)         # deterministic SHA-256 hash
print(strategy.scoring.get_module("fundamental_bonus").params["score_range"])  # [-20, 30]
print(strategy.regime.fast_crash.decline_threshold)  # -0.08
```

To change a parameter: edit the YAML, bump `meta.version`. Git history is your version control.

## Pipeline Flow

`pipeline/runner.py` orchestrates the daily pipeline. Each step is wrapped in a `_log_step` context manager that records timing to the `pipeline_log` table.

```
run_pipeline(db, target_date, strategy_path)
  │
  ├─ M1: Data ingestion (prices, delivery, FII/DII, deals, surveillance)
  ├─ Indicators: compute_and_store_indicators(db, date, strategy)
  ├─ M2: classify_regime(db, date, strategy)
  ├─ M3: rank_sectors(db, date, params)
  ├─ Universe filter: passes_hard_filters(db, stock, date, strategy)
  │   └─ Dispatches to 8 filter functions via strategy config
  │   └─ Logs exclusions to exclusion_log table
  ├─ Per eligible stock:
  │   ├─ Fundamental bonus (14 bonuses + 7 penalties)
  │   ├─ Sector bonus (top N / bottom N from strategy)
  │   ├─ Trend template (8 conditions, params from strategy)
  │   ├─ Breakout detection (VCP/base/breakout)
  │   ├─ Accumulation score (OBV + A/D + institutional)
  │   └─ Composite score (weighted sum, tagged with strategy_hash)
  └─ M10: generate_watchlist(db, date, regime, sector_ranks, strategy)
```

## Adding a New Scoring Module

1. Write the scoring function (reads params from dict)
2. Add an entry in `strategies/momentum_edge.yaml` under `scoring.modules`
3. Wire it in `pipeline/runner.py` — get params via `strategy.scoring.get_module("name").params`
4. Done. No framework classes or registries to implement.

## Adding a New Hard Block Filter

1. Write a function matching signature: `def _check_xyz(db, stock, as_of_date, params) -> FilterResult`
2. Register it in `_FILTER_FUNCTIONS` dict in `ranking/universe_filter.py`
3. Add the block to `strategies/momentum_edge.yaml` under `universe.hard_blocks`
4. Filter will be called automatically when `enabled: true`

## Exit Engine

`engine/exits.py` implements a 4-phase gain-based exit system:

```python
from momentum_edge.engine.exits import determine_phase, GainPhase

phase = determine_phase(gain_pct=0.35, monster_override=False)
# → GainPhase.LET_IT_RUN

phase = determine_phase(gain_pct=0.35, monster_override=True)
# → GainPhase.MONSTER_RUN (override)
```

Each phase has rules defined in `strategy.exits.phases[n].rules`. Rules are evaluated in priority order (first match wins). Three validation layers can suppress or override exits.

The cascade (`engine/exit_cascade.py`) operates at portfolio level — it checks market-wide signals and returns actions affecting multiple positions.

## Position Sizing

`engine/position_sizing.py` accepts strategy config:

```python
pos = calculate_position_size(
    portfolio_value=10_000_000,
    entry_price=500,
    stop_loss=460,
    regime="Bull",
    stock=stock_obj,        # for beta/thin-float checks
    db=db,
    target_date=date.today(),
    open_positions=positions, # for correlation check
    strategy=strategy,
)
# pos.adjustments_applied → ["corr_0.87_high_reduction"]
```

## Backtesting

```python
from momentum_edge.backtest.engine import BacktestConfig, Backtester

# Create config from strategy YAML
config = BacktestConfig.from_strategy(
    start_date=date(2015, 1, 1),
    end_date=date(2024, 12, 31),
    strategy_path="strategies/momentum_edge.yaml",
)

bt = Backtester(db, config)
bt.prepare_data()   # loads all prices into memory
bt.run()            # day-by-day simulation
metrics = bt.compute_metrics()  # 14 performance metrics + gate checks
```

### Parameter Sweep

```python
from momentum_edge.backtest.sweep import run_sweep

results_df = run_sweep(
    db,
    strategy_path="strategies/momentum_edge.yaml",
    start_date=date(2015, 1, 1),
    end_date=date(2024, 12, 31),
    sweep_params={
        "exits.phases.0.rules.0.stop_pct": [0.06, 0.08, 0.10],
        "exits.phases.1.rules.0.trail_pct": [0.15, 0.20, 0.25],
    },
)
# results_df sorted by Sharpe ratio
```

## Database Migrations

```bash
# Generate migration after model changes
PYTHONPATH=src uv run python -m alembic revision --autogenerate -m "description"

# Apply migrations
PYTHONPATH=src uv run python -m alembic upgrade head

# Check current revision
PYTHONPATH=src uv run python -m alembic current
```

**Important:** Boolean columns on existing tables need `server_default` in migrations since existing rows can't be NOT NULL without defaults.

## CLI Commands

```bash
# Pipeline
PYTHONPATH=src uv run python main.py run                              # full pipeline (latest date)
PYTHONPATH=src uv run python main.py run --date 2026-04-10            # specific date
PYTHONPATH=src uv run python main.py run --strategy path/to/custom.yaml  # custom strategy

# Data
PYTHONPATH=src uv run python main.py sync-universe --index nifty500
PYTHONPATH=src uv run python main.py bootstrap
PYTHONPATH=src uv run python main.py sync-screener

# View
PYTHONPATH=src uv run python main.py watchlist
PYTHONPATH=src uv run python main.py status

# Backtest
PYTHONPATH=src uv run python main.py backtest
PYTHONPATH=src uv run python main.py backtest-tests

# API
PYTHONPATH=src uv run uvicorn momentum_edge.api.app:app --reload --port 8000
```

## Environment Variables

| Variable | Required | Notes |
|----------|----------|-------|
| `DATABASE_URL` | Yes | PostgreSQL connection URL |
| `DB_TARGET` | No | `local` or `neon` |
| `APP_ENV` | No | `development` enables SQL echo |
| `SCREENER_USERID` | Yes | Screener.in login |
| `SCREENER_PASSWORD` | Yes | Screener.in password |
| `CORS_ORIGINS` | No | Comma-separated origins |
| `NEON_AUTH_BASE_URL` | Prod | JWT verification endpoint |
| `AWS_ACCESS_KEY_ID` | Prod | S3 credentials |
| `AWS_SECRET_ACCESS_KEY` | Prod | S3 credentials |
| `S3_BUCKET` | Prod | Parquet archive bucket |
| `RESEND_API_KEY` | Prod | Email API |
| `RESEND_FROM_EMAIL` | Prod | Sender address |
| `ALERT_EMAIL` | Prod | Recipient for alerts |

## Key Design Decisions

1. **Single YAML** — One strategy file, not multiple. Git history tracks versions.
2. **No generic rule engine** — Exit phases are direct code, not a DSL. Easier to debug.
3. **Fail-closed on hard blocks** — Missing data on critical filters = exclude. Once data is ingested, the filter activates automatically.
4. **Fail-open on bonuses** — Missing bonus data = 0 points (no penalty for missing data).
5. **Strategy hash on outputs** — Every score, watchlist entry, and signal is tagged with the SHA-256 hash of the strategy config for reproducibility.
6. **In-place rewrite** — No new directory structure. Existing files modified to accept strategy params.
7. **Protocol-based plugins** — Python Protocols (structural typing), not ABC registries. Pipeline explicitly imports and wires modules.
