# MomentumEdge — Architecture

## System Overview

MomentumEdge is a configurable stock scanning and ranking engine for NSE equities. It runs a daily pipeline that ingests market data, computes technical indicators, filters the universe, scores stocks across 6 dimensions, and produces a ranked watchlist with entry/exit signals.

All scoring parameters, exit rules, filter thresholds, and regime classifications are defined in a single YAML strategy file (`strategies/momentum_edge.yaml`). The engine reads this file at runtime — changing a parameter means editing YAML, not Python code.

```
strategies/momentum_edge.yaml    ← Single source of truth for all params
         │
         ▼
┌─────────────────────────────────────────────────────┐
│              Pipeline Orchestrator                  │
│              (pipeline/runner.py)                   │
│                                                     │
│  M1 Data ─→ Indicators ─→ M2 Regime ─→ M3 Sectors   │
│       ↓                                             │
│  Universe Filter (8 hard blocks)                    │
│       ↓                                             │
│  Per-stock scoring: momentum + fundamental +        │
│    accumulation + sector + technical + breakout     │
│       ↓                                             │
│  Composite Score ─→ Watchlist ─→ Signals            │
│       ↓                                             │
│  Exit Engine (4-phase + 5-layer cascade)            │
│  Fast Crash Detector                                │
│  Monster Detection                                  │
│  Bull Entry Protocol                                │
│  Turnaround Watch                                   │
└─────────────────────────────────────────────────────┘
         │
         ▼
    FastAPI REST API (14 endpoints)
```

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.12, `uv` package manager |
| Strategy | YAML config with Pydantic validation |
| Database | PostgreSQL — Neon (prod), local (dev) |
| ORM | SQLAlchemy 2.0 + Alembic migrations |
| API | FastAPI + Uvicorn |
| Config | pydantic-settings from `.env` |
| Logging | loguru |
| Email | Resend |
| Storage | AWS S3 (prod) |
| Compute | Railway (cron + web service) |
| Data sources | NSE bulk CSV, yfinance, Screener.in |

## Source Structure

```
src/momentum_edge/
├── core/                          # Strategy engine framework
│   ├── strategy.py                # 36 Pydantic models, YAML loader, strategy hashing
│   ├── protocols.py               # ScorerProtocol, FilterProtocol, result types
│   └── composite.py               # Weighted composite scorer
│
├── config.py                      # Pydantic env settings (.env)
│
├── pipeline/                      # Orchestration
│   ├── runner.py                  # Daily pipeline (M1→M10), step logging
│   └── cron.py                    # Railway cron scheduler
│
├── scanner/                       # Technical analysis
│   ├── indicators.py              # 25+ indicators per stock per day
│   ├── market_regime.py           # 6-signal regime + crash indicator
│   ├── sector_rotation.py         # Sector momentum ranking
│   ├── trend_template.py          # 8-condition Minervini template
│   └── breakout_patterns.py       # VCP + tight base + breakout detection
│
├── ranking/                       # Scoring & watchlist
│   ├── universe_filter.py         # 8 hard blocks (dispatch architecture)
│   ├── fundamental_bonus.py       # 14 bonuses + 7 penalties (-20 to +30)
│   ├── accumulation_score.py      # OBV + A/D + institutional flow
│   ├── composite_score.py         # Legacy wrapper (use core/composite.py)
│   └── watchlist.py               # Regime-filtered ranked output
│
├── engine/                        # Trading engine
│   ├── exits.py                   # 4-phase gain-based exit engine + 3 validation layers
│   ├── exit_cascade.py            # 5-layer portfolio-level cascade (E1-E5)
│   ├── fast_crash.py              # Rolling 5-day crash detector
│   ├── monster.py                 # 7-criteria monster stock detection
│   ├── bull_entry.py              # 4-phase bear recovery protocol
│   ├── turnaround.py              # Early turnaround detection
│   ├── signals.py                 # Signal lifecycle (Pending→Confirmed/Failed)
│   ├── position_sizing.py         # Regime-aware + 3 adjustment layers
│   └── correlation.py             # Pairwise return correlation
│
├── data/                          # Data ingestion (10 modules)
│   ├── prices.py                  # OHLCV from yfinance + NSE bulk
│   ├── delivery.py                # NSE delivery data
│   ├── screener.py                # Screener.in fundamentals
│   ├── fii_dii.py                 # Institutional flows
│   ├── bulk_deals.py              # Block/bulk deals
│   ├── surveillance.py            # ASM/ESM flags
│   ├── corporate_actions.py       # Splits, bonuses
│   ├── stock_universe.py          # Nifty 500 master
│   ├── nse_indices.py             # Nifty 50 index
│   └── nse_bulk.py                # NSE CSV downloads
│
├── db/                            # Persistence
│   ├── models.py                  # 24 SQLAlchemy tables
│   └── session.py                 # Connection + session factory
│
├── api/                           # REST API
│   ├── app.py                     # FastAPI app + CORS + route registration
│   ├── auth.py                    # JWT verification (Neon Auth / EdDSA)
│   └── routes/                    # 12 route modules
│
├── backtest/                      # Backtesting
│   ├── engine.py                  # Strategy-driven backtester
│   ├── sweep.py                   # Parameter sweep runner
│   ├── test_runner.py             # Structured tests T1-T10
│   └── walkforward.py             # Walk-forward validation
│
├── notifications/
│   └── sender.py                  # Resend email
│
└── utils/
    ├── date_utils.py              # NSE trading calendar
    └── logger.py                  # Loguru setup
```

## Database Schema (24 tables)

### Core Data
| Table | Purpose |
|-------|---------|
| `stocks` | Stock master (500+ NSE equities) with v16 fields: pledge_pct, beta, sebi flags |
| `eod_prices` | Daily OHLCV + adj_close (1M+ rows, 10yr history) |
| `delivery_data` | NSE daily delivery stats |
| `fundamentals` | Quarterly EPS, revenue, D/E, OCF, OPM, trade receivables |
| `corporate_actions` | Splits, bonuses, rights |
| `sector_data` | Sector classification |

### Market Data
| Table | Purpose |
|-------|---------|
| `fii_dii_data` | Daily FII/DII aggregate flows |
| `shareholding_pattern` | Quarterly promoter/FII/DII % |
| `bulk_deals` | Block and bulk deal records |

### Pipeline Output
| Table | Purpose |
|-------|---------|
| `indicators` | 25+ technical indicators per stock per day |
| `scores` | Component + composite scores with strategy_hash |
| `watchlist` | Daily ranked output |
| `signals` | Trading signal lifecycle |
| `open_positions` | Active positions with v16 exit state tracking |

### Audit & Logging
| Table | Purpose |
|-------|---------|
| `exclusion_log` | Why stocks were filtered out |
| `pipeline_log` | Step-by-step execution timing |
| `turnaround_watch` | Early turnaround candidates |

### Backtesting & Performance
| Table | Purpose |
|-------|---------|
| `backtest_results` | Test results + metrics |
| `walkforward_results` | Walk-forward fold results |
| `performance_log` | Individual trade records |

### Future (Phase 2+)
| Table | Purpose |
|-------|---------|
| `users` | Subscriber accounts |
| `orders` | Zerodha order log |
| `scan_results` | Legacy (superseded by scores + watchlist) |

## Strategy Configuration

All parameters live in `strategies/momentum_edge.yaml`. The engine loads this file via `core/strategy.py` which validates it against 36 Pydantic models.

Key sections:
- `universe.hard_blocks` — 8 filters with per-filter params
- `indicators` — MA periods, momentum lookbacks, factor weights
- `scoring.modules` — 6 scoring modules with weights and params
- `regime` — 6 signals, 5 classifications, fast crash config, bull entry protocol
- `exits` — 4 gain phases, per-phase rules, 3 validation layers, 5-layer cascade
- `monster` — 7 criteria, activation thresholds
- `position_sizing` — Base risk, floor/ceiling, 3 adjustment layers
- `signals` — Tier thresholds, confirmation rules
- `backtest` — Transaction costs, periods, capital

Every pipeline run is tagged with a deterministic `strategy_hash` (SHA-256 of config) for reproducibility.

## Key Conventions

- All price calculations use `adj_close` (never raw close)
- All modules accept strategy params via kwargs (no hardcoded constants)
- `utils/date_utils.py` for NSE trading calendar
- Fail-closed on hard blocks: missing data = exclude stock + log
- Fail-open on bonuses: missing data = 0 points
- Source root: `src/momentum_edge/` — run with `PYTHONPATH=src`
- Package manager: `uv` — use `uv run`, never `pip`
