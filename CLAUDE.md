# MomentumEdge — Claude Code Instructions

## Project Overview

**MomentumEdge** is an automated Indian stock scanning and ranking system for NSE equities. Uses evidence-based momentum methodology (v7) with volatility scaling, OBV accumulation, and smart institutional flow signals.

- **Current:** Production on Railway + Neon + S3
- **Frontend:** Separate React project (see `UI_GUIDE.md` for API integration)

## Architecture

- **Language:** Python 3.12 via `uv`
- **Package manager:** `uv` — always use `uv run` and `uv add`, never `pip`
- **Database:** Neon PostgreSQL (prod), local PostgreSQL 16 (dev)
- **ORM:** SQLAlchemy 2.0 + Alembic migrations
- **API:** FastAPI + Uvicorn on Railway
- **Config:** pydantic-settings loading from `.env`
- **Logging:** loguru
- **Email:** Resend (daily digest + alerts)
- **Storage:** AWS S3 (parquet archive)
- **Source root:** `src/momentum_edge/` — always run with `PYTHONPATH=src`

## Production

- **API:** `https://unipro-engine-production.up.railway.app`
- **Cron:** Railway cron service, `30 10 * * 1-5` UTC (4:00 PM IST)
- **DB:** Neon PostgreSQL (20 tables, 1M+ price rows)

## Commands

```bash
PYTHONPATH=src uv run alembic upgrade head          # migrations
PYTHONPATH=src uv run python main.py run             # full pipeline
PYTHONPATH=src uv run python main.py watchlist        # view watchlist
PYTHONPATH=src uv run python main.py status           # DB status
PYTHONPATH=src uv run python main.py sync-screener    # Screener.in sync
PYTHONPATH=src uv run python main.py backtest         # run backtest
PYTHONPATH=src uv run uvicorn momentum_edge.api.app:app --reload --port 8000  # dev API
```

## v7 Scoring (current)

- **Universe:** 4 junk filters (market cap, liquidity, ASM, EPS) — NOT CANSLIM hard filters
- **Momentum:** Percentile-ranked 12-1m/6m/3m with volatility scaling (Barroso 2015)
- **Fundamentals:** Bonus scores only (-5 to +20), EPS acceleration +8
- **Accumulation:** OBV slope +5, A/D ratio +4, smart institutional +2. Delivery % NOT scored
- **Regime:** 6 signals + crash indicator → 5 levels (Strong Bull to Full Bear)
- **Trend:** 8-condition Minervini template (adj_close, MA200 slope, stage 2)
- **Breakout:** Full VCP math + OBV during base + circuit exclusion + 7 entry rules

## Module Map

| Module | File | Purpose |
|--------|------|---------|
| M1 | `data/nse_bulk.py`, `prices.py`, `delivery.py` | NSE bulk CSV ingestion |
| M1 | `data/screener.py`, `corporate_actions.py` | Screener + corp actions |
| M1 | `data/fii_dii.py`, `bulk_deals.py`, `surveillance.py` | Institutional data |
| M2 | `scanner/market_regime.py` | 6-signal regime + crash indicator |
| M3 | `scanner/sector_rotation.py` | Sector momentum ranking |
| Ind | `scanner/indicators.py` | 25+ indicators on adj_close |
| Flt | `ranking/universe_filter.py` | 4 hard junk filters |
| M4 | `ranking/fundamental_bonus.py` | Bonus scores (not CANSLIM) |
| M6 | `ranking/accumulation_score.py` | OBV + A/D + institutional flow |
| M7 | `scanner/trend_template.py` | 8-condition Minervini filter |
| M8 | `scanner/breakout_patterns.py` | VCP + OBV + entry rules |
| M9 | `ranking/composite_score.py` | Uncapped composite |
| M10 | `ranking/watchlist.py` | Ranked watchlist generation |
| M11 | `pipeline/runner.py` | Pipeline orchestrator |
| | `engine/signals.py` | Signal lifecycle engine |
| | `engine/exits.py` | 9 exit rules |
| | `engine/position_sizing.py` | 2% risk + portfolio constraints |
| BT | `backtest/engine.py` | Backtesting simulation |
| API | `api/app.py`, `api/routes/` | FastAPI REST endpoints |

## Database (20 tables)

`stocks`, `eod_prices`, `delivery_data`, `fundamentals`, `sector_data`, `indicators`, `scores`, `watchlist`, `signals`, `corporate_actions`, `fii_dii_data`, `shareholding_pattern`, `bulk_deals`, `performance_log`, `backtest_results`, `walkforward_results`, `users`, `orders`, `scan_results` (legacy)

## Key Conventions

- All price calculations use `adj_close` (never raw close)
- All modules use dependency-injected SQLAlchemy `Session`
- `utils/date_utils.py` for NSE trading calendar (skip weekends/holidays)
- Screener export IDs cached in `stocks.screener_export_id`
- Raw Screener Excel files saved to `data/screener_exports/` (gitignored)
- Parquet archive on S3 (prod) or `data/parquet/` (local)
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
| `AWS_ACCESS_KEY_ID` | Prod | S3 credentials |
| `AWS_SECRET_ACCESS_KEY` | Prod | S3 credentials |
| `S3_BUCKET` | Prod | Parquet archive bucket |
| `RESEND_API_KEY` | Prod | Email API |
| `RESEND_FROM_EMAIL` | Prod | Sender address |
| `ALERT_EMAIL` | Prod | Recipient for alerts |
