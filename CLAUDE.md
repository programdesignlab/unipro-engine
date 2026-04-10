# MomentumEdge — Claude Code Instructions

## Project Overview

**MomentumEdge** is an automated Indian stock scanning and ranking system for NSE equities. Configurable strategy engine with YAML-driven parameters, 4-phase exit system, and evidence-based momentum methodology.

- **Current:** Production on Railway + Neon + S3
- **Strategy:** `strategies/momentum_edge.yaml` (single source of truth for all params)
- **Frontend:** Separate React project (see `docs/UI_GUIDE.md` for API integration)

## Architecture

- **Language:** Python 3.12 via `uv`
- **Package manager:** `uv` — always use `uv run` and `uv add`, never `pip`
- **Database:** Neon PostgreSQL (prod), local PostgreSQL 16 (dev)
- **ORM:** SQLAlchemy 2.0 + Alembic migrations
- **API:** FastAPI + Uvicorn on Railway
- **Config:** pydantic-settings from `.env`, strategy params from YAML
- **Logging:** loguru
- **Email:** Resend (daily digest + alerts)
- **Source root:** `src/momentum_edge/` — always run with `PYTHONPATH=src`

## Production

- **API:** `https://api.uniproadvisory.com`
- **Cron:** Railway cron service, `0 11 * * 1-5` UTC (4:30 PM IST)
- **DB:** Neon PostgreSQL (24 tables, 1M+ price rows)

## Commands

```bash
PYTHONPATH=src uv run python -m alembic upgrade head    # migrations
PYTHONPATH=src uv run python main.py run                # full pipeline
PYTHONPATH=src uv run python main.py run --strategy strategies/momentum_edge.yaml  # explicit strategy
PYTHONPATH=src uv run python main.py watchlist           # view watchlist
PYTHONPATH=src uv run python main.py status              # DB status
PYTHONPATH=src uv run python main.py sync-screener       # Screener.in sync
PYTHONPATH=src uv run python main.py backtest            # run backtest
PYTHONPATH=src uv run uvicorn momentum_edge.api.app:app --reload --port 8000  # dev API
```

## Strategy Engine

All parameters live in `strategies/momentum_edge.yaml`. Validated by Pydantic models in `core/strategy.py`.

- **Universe:** 8 hard blocks (market cap, liquidity, ASM, EPS, OCF, pledge, SEBI, IPO age)
- **Scoring:** 6 weighted modules (momentum 35%, fundamental 20%, accumulation 15%, sector 10%, technical 12%, breakout 8%)
- **Fundamentals:** 14 bonuses + 7 penalties, range [-20, +30]
- **Regime:** 6 signals + crash indicator → 5 levels, fast crash detector, bull entry protocol
- **Exits:** 4-phase gain-based (prove_it → let_it_run → working_compounder → monster_run) + 5-layer cascade + 3 validation layers
- **Monster:** 7-criteria detection, score >= 80 + gain >= 40% → Phase 4 override
- **Position sizing:** Regime-dependent heat + beta/thin-float/correlation adjustments

Every pipeline run is tagged with a deterministic `strategy_hash` for reproducibility.

## Module Map

| Module | File | Purpose |
|--------|------|---------|
| Core | `core/strategy.py` | 36 Pydantic models, YAML loader, strategy hashing |
| Core | `core/protocols.py` | ScorerProtocol, FilterProtocol, result types |
| Core | `core/composite.py` | Weighted composite scorer |
| M1 | `data/prices.py`, `delivery.py`, `nse_bulk.py` | NSE data ingestion |
| M1 | `data/screener.py`, `corporate_actions.py` | Screener + corp actions |
| M1 | `data/fii_dii.py`, `bulk_deals.py`, `surveillance.py` | Institutional data |
| M2 | `scanner/market_regime.py` | 6-signal regime + crash indicator |
| M3 | `scanner/sector_rotation.py` | Sector momentum ranking |
| Ind | `scanner/indicators.py` | 25+ indicators on adj_close |
| Flt | `ranking/universe_filter.py` | 8 hard blocks (dispatch architecture) |
| M4 | `ranking/fundamental_bonus.py` | 14 bonuses + 7 penalties |
| M6 | `ranking/accumulation_score.py` | OBV + A/D + institutional flow |
| M7 | `scanner/trend_template.py` | 8-condition Minervini filter |
| M8 | `scanner/breakout_patterns.py` | VCP + OBV + entry rules |
| M9 | `core/composite.py` | Weighted composite (strategy-hash tagged) |
| M10 | `ranking/watchlist.py` | Ranked watchlist generation |
| M11 | `pipeline/runner.py` | Pipeline orchestrator (step-logged) |
| Exit | `engine/exits.py` | 4-phase gain-based + 3 validation layers |
| Exit | `engine/exit_cascade.py` | 5-layer portfolio cascade (E1-E5) |
| | `engine/fast_crash.py` | Rolling 5-day crash detector |
| | `engine/monster.py` | 7-criteria monster detection |
| | `engine/bull_entry.py` | 4-phase bear recovery protocol |
| | `engine/turnaround.py` | Turnaround watch |
| | `engine/signals.py` | Signal lifecycle engine |
| | `engine/position_sizing.py` | Regime-aware + 3 adjustments |
| | `engine/correlation.py` | Pairwise return correlation |
| BT | `backtest/engine.py` | Strategy-driven backtester |
| BT | `backtest/sweep.py` | Parameter sweep runner |
| API | `api/app.py`, `api/routes/` | 14 REST endpoints |

## Database (24 tables)

`stocks`, `eod_prices`, `delivery_data`, `fundamentals`, `sector_data`, `indicators`, `scores`, `watchlist`, `signals`, `corporate_actions`, `fii_dii_data`, `shareholding_pattern`, `bulk_deals`, `open_positions`, `exclusion_log`, `pipeline_log`, `turnaround_watch`, `performance_log`, `backtest_results`, `walkforward_results`, `users`, `orders`, `scan_results` (legacy)

## Key Conventions

- All price calculations use `adj_close` (never raw close)
- All modules accept strategy params via kwargs (no hardcoded constants)
- `utils/date_utils.py` for NSE trading calendar (skip weekends/holidays)
- Fail-closed on hard blocks: missing data = exclude + log
- Fail-open on bonuses: missing data = 0 points
- Screener export IDs cached in `stocks.screener_export_id`
- `.env` is gitignored; `.env.example` is committed

## Environment Variables

| Variable | Required | Notes |
|----------|----------|-------|
| `DATABASE_URL` | Yes | Neon URL for prod |
| `DB_TARGET` | No | `local` or `neon` |
| `APP_ENV` | No | `development` enables SQL echo |
| `SCREENER_USERID` | Yes | Screener.in login |
| `SCREENER_PASSWORD` | Yes | Screener.in password |
| `CORS_ORIGINS` | No | Comma-separated origins |
| `NEON_AUTH_BASE_URL` | Prod | JWT verification |
| `AWS_ACCESS_KEY_ID` | Prod | S3 credentials |
| `AWS_SECRET_ACCESS_KEY` | Prod | S3 credentials |
| `S3_BUCKET` | Prod | Parquet archive bucket |
| `RESEND_API_KEY` | Prod | Email API |
| `RESEND_FROM_EMAIL` | Prod | Sender address |
| `ALERT_EMAIL` | Prod | Recipient for alerts |
