# MomentumEdge — Claude Code Instructions

## Project Overview

**MomentumEdge** is an automated Indian stock scanning and ranking system for NSE equities. It applies Mark Minervini's Trend Template + CANSLIM methodology to generate a daily ranked watchlist of momentum breakout candidates.

- **Phase 1 (current):** Local MVP — Python backend + Rich CLI
- **Phase 2+:** Cloud deployment, subscription SaaS, React frontend (separate repo)

## Architecture

- **Language:** Python 3.12 via `uv`
- **Package manager:** `uv` — always use `uv run` and `uv add`, never `pip`
- **Database:** Neon PostgreSQL (prod), local PostgreSQL 16 via Homebrew (dev)
- **ORM:** SQLAlchemy 2.0 + Alembic migrations
- **API:** FastAPI + Uvicorn (REST API for watchlist, scores, regime)
- **Config:** pydantic-settings loading from `.env`
- **Logging:** loguru
- **Email:** Resend (daily digest + alerts)
- **Storage:** AWS S3 (parquet archive), local fallback
- **Source root:** `src/momentum_edge/` — always run with `PYTHONPATH=src`

## UI / Frontend

**No Streamlit or web UI in this project.** UI will be a separate React project with Neon Auth. All user interaction in this repo is via **Rich CLI** (terminal interface) and **FastAPI** (REST API).

## Commands

```bash
# Run migrations
PYTHONPATH=src uv run alembic upgrade head

# Run CLI entry point
PYTHONPATH=src uv run python main.py

# Run FastAPI dev server
PYTHONPATH=src uv run uvicorn momentum_edge.api.app:app --reload --port 8000

# Run tests
PYTHONPATH=src uv run pytest

# Lint/format
uv run ruff check src/
uv run ruff format src/
```

## Module Map (M1–M11 pipeline)

| Module | File | Purpose |
|--------|------|---------|
| M1 | `data/nse_bhav.py`, `nse_delivery.py`, `nse_indices.py`, `fundamentals.py` | Data ingestion |
| M2 | `scanner/market_regime.py` | Bull/Neutral/Bear classification |
| M3 | `scanner/sector_rotation.py` | Sector momentum ranking |
| M4 | `ranking/momentum_score.py` | Multi-timeframe momentum (max 40 pts) |
| M5 | `ranking/canslim_score.py` | CANSLIM fundamental filter (max 25 pts) |
| M6 | `ranking/accumulation_score.py` | Institutional accumulation (max 15 pts) |
| M7 | `scanner/trend_template.py` | Minervini 6-condition hard filter |
| M8 | `scanner/breakout_patterns.py` | VCP, base, resistance, volume breakout |
| M9 | `ranking/composite_score.py` | Composite score (max 125 pts) |
| M10 | `ranking/watchlist.py` | Generate + persist watchlist |
| M11 | `pipeline/runner.py` | Master pipeline orchestrator |
| API | `api/app.py`, `api/routes/` | FastAPI REST endpoints |
| Notify | `notifications/sender.py` | Resend email digest + alerts |

## Database Tables

`stocks`, `price_data`, `delivery_data`, `fundamentals`, `sector_data`, `indicators`, `scores`, `watchlist`, `users`, `orders`

All migrations in `migrations/versions/`. Run `alembic upgrade head` after any model change.

## Current State (as of March 2026)

**Done:** uv init, PostgreSQL local + Neon, core DB session + models, Alembic migrations, pydantic-settings config, full 10-table schema, M1–M11 pipeline modules, Rich CLI, Nifty 500 universe (500 stocks), OHLCV 10yr bootstrap (1M rows), delivery 2yr bootstrap (340K rows), NSE bulk CSV ingestion, data migrated to Neon + S3

**To build:** FastAPI API, Resend email, Railway deployment, Screener.in fundamentals, tests

## Key Conventions

- All modules use dependency-injected SQLAlchemy `Session` (never create sessions inside domain logic)
- Repositories in `db/repositories/` handle all DB access — domain code calls repos, not ORM directly
- Retry logic via `utils/retry.py` decorator for all HTTP/NSE calls
- `utils/date_utils.py` for NSE trading calendar (skip weekends/holidays)
- Raw NSE files (zip/csv) are discarded after parsing — not persisted
- Parquet archive on S3 (prod) or `data/parquet/` (local) — gitignored
- `.env` is gitignored; `.env.example` is committed

## Environment Variables

| Variable | Required | Notes |
|----------|----------|-------|
| `DATABASE_URL` | Yes | Neon pooled URL for prod, `postgresql://arvbsnt@localhost:5432/momentum_edge` for local |
| `DB_TARGET` | No | `local` or `neon` — controls SSL + pool settings |
| `APP_ENV` | No | `development` enables SQLAlchemy echo |
| `LOG_LEVEL` | No | loguru level, default INFO |
| `CORS_ORIGINS` | No | Comma-separated allowed origins for FastAPI CORS |
| `AWS_ACCESS_KEY_ID` | Prod | AWS credentials for S3 |
| `AWS_SECRET_ACCESS_KEY` | Prod | AWS credentials for S3 |
| `AWS_REGION` | Prod | AWS region for S3 bucket |
| `S3_BUCKET` | Prod | S3 bucket name for parquet archive |
| `STORAGE_BACKEND` | No | `local` or `s3` — parquet storage target |
| `RESEND_API_KEY` | Prod | Resend email API key |
| `RESEND_FROM_EMAIL` | Prod | Sender email address |
| `ALERT_EMAIL` | Prod | Recipient for digest + alerts |
| `FUNDAMENTALS_API_KEY` | Phase 2 | Not used yet — Screener.in uses CSV export, no API |
