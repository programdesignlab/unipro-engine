# MomentumEdge — Production Architecture

> **Status:** For review — transitioning from local MVP to production deployment.
> **Scope:** Neon DB + Railway compute + S3 storage + Resend email — Nifty 500 universe.

---

## 1. High-Level System Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                    RAILWAY (Python Compute Only)                     │
│                                                                     │
│  ┌─────────────────────────┐   ┌──────────────────────────────────┐ │
│  │  CRON SERVICE            │   │  API SERVICE (FastAPI)           │ │
│  │  30 10 * * 1-5 (UTC)    │   │  /api/v1/watchlist               │ │
│  │  = 4:00 PM IST Mon-Fri  │   │  /api/v1/scores/{symbol}        │ │
│  │  Runs M1→M10 pipeline   │   │  /api/v1/regime                  │ │
│  │  + Resend email digest   │   │  /api/v1/sectors                 │ │
│  └───────────┬─────────────┘   │  /api/v1/stocks                  │ │
│              │                  │  /health                          │ │
│              │                  └──────────┬───────────────────────┘ │
└──────────────┼─────────────────────────────┼───────────────────────┘
               │ SQL                         │ JSON
               ▼                             ▼
  ┌──────────────────┐          ┌──────────────────────┐
  │  NEON PostgreSQL  │◀────────│  React UI (sep repo) │
  │  Pooled endpoint  │         │  + Neon Auth          │
  │  sslmode=require  │         └──────────────────────┘
  └──────────────────┘
               ▲
  ┌────────────┴─────┐   ┌─────────────────┐
  │  AWS S3           │   │  RESEND          │
  │  Parquet archive  │   │  Email API       │
  │  Daily backups    │   │  Digest + alerts │
  └──────────────────┘   └─────────────────┘
```

---

## 1.1 Data Sources and Ingestion Map

### Stock Universe

**Nifty 500** (~500 symbols) — the tradeable universe. Constituent list sourced from NSE.

### Data Types, Sources, and Frequency

| # | Data Type | Source | Format | Frequency | Used By | Stored In |
|---|-----------|--------|--------|-----------|---------|-----------|
| 1 | **OHLCV price data** (Open, High, Low, Close, Volume) | NSE Bhav Copy | CSV (zip) | Daily after market close | M4, M7, M8 (momentum, trend, breakout) | `price_data` table |
| 2 | **Delivery data** (delivery qty, delivery %) | NSE Delivery Report | CSV (zip) | Daily after market close | M6 (institutional accumulation) | `delivery_data` table |
| 3 | **Nifty 50 index data** (daily close) | yfinance (`^NSEI`) | API (JSON) | Daily | M2 (market regime), M4 (relative strength vs index) | `price_data` (index row) |
| 4 | **Fundamental data** (EPS, revenue, ROE, margins, PE, D/E) | Screener.in | CSV export (manual) | Quarterly | M5 (CANSLIM filter) | `fundamentals` table |
| 5 | **Sector classification** (sector name per stock) | NSE / Screener.in | CSV | On universe refresh | M3 (sector rotation) | `sector_data` + `stocks.sector_id` |
| 6 | **Corporate actions** (splits, bonuses, rights) | NSE Corporate Actions page | HTML / CSV | As announced | M1 (price adjustment) | Applied to `price_data` in-place |
| 7 | **Nifty 500 constituent list** | NSE Index page | CSV | Monthly (rebalance) | Universe management | `stocks` table |

### Source Details

**1. NSE Bhav Copy (OHLCV)**
- URL pattern: `https://nsearchives.nseindia.com/content/cm/BhsecXX.csv` (or zip equivalent)
- Contains all NSE-listed stocks' daily OHLCV + previous close
- Available ~3:45 PM IST after market close
- **Bootstrap:** yfinance bulk download for 10-year history (NSE bhav archives only go back ~2 years)
- **Daily:** NSE bhav copy download via `data/nse_bhav.py`

**2. NSE Delivery Data**
- URL pattern: `https://nsearchives.nseindia.com/products/content/sec_bhavdata_full_XX.csv`
- Contains delivery quantity and delivery % for every stock
- Key signal: rising delivery % = institutional buying (used by M6)
- **Bootstrap:** Not available historically — start collecting from day 1
- **Daily:** NSE delivery report download via `data/nse_delivery.py`

**3. Nifty 50 Index (yfinance)**
- Symbol: `^NSEI` via yfinance API
- Used for: market regime (Nifty vs 200MA), relative strength calculation (stock return vs Nifty return)
- **Bootstrap:** `yfinance.download("^NSEI", period="10y")` — 10 years available
- **Daily:** `yfinance.download("^NSEI", period="1d")` or from NSE index data

**4. Fundamental Data (Screener.in)**
- Screener.in does not expose an API — data obtained via CSV export
- Premium subscription required for bulk export (not yet purchased)
- Fields needed: quarterly EPS, revenue, ROE, profit margin, debt-to-equity, PE ratio
- **Bootstrap:** Manual CSV export for Nifty 500 from Screener.in
- **Daily:** Not needed — fundamentals update quarterly. Re-export after each earnings season
- **Alternative:** Web scraping (respect ToS), or Tijori Finance API if available later

**5. Sector Classification**
- NSE publishes sector/industry classification for listed stocks
- Screener.in also has sector tags per stock
- ~20–25 sectors (IT, Pharma, Banking, Auto, FMCG, etc.)
- **Bootstrap:** One-time download from NSE or Screener
- **Refresh:** On Nifty 500 rebalance (quarterly)

**6. Corporate Actions (Splits/Bonuses)**
- Critical for price continuity — a 1:5 split makes historical prices look 5x higher
- NSE publishes corporate actions calendar
- **Bootstrap:** yfinance auto-adjusts historical prices (handled automatically)
- **Daily:** Check NSE corporate actions page; adjust `price_data` if split/bonus detected

**7. Nifty 500 Constituent List**
- NSE publishes the current Nifty 500 list as CSV
- Rebalanced semi-annually (March and September) by NSE
- **Bootstrap:** Download current list, seed `stocks` table
- **Refresh:** Check for changes monthly, add/remove symbols

### Bootstrap vs Daily — Summary

| Data | Bootstrap (local, one-time) | Daily (Railway cron) |
|------|----------------------------|---------------------|
| OHLCV 10yr history | yfinance bulk for 500 symbols | NSE bulk bhav CSV (1 file, all stocks) |
| Delivery data (2yr) | NSE bulk CSV archives (~500 daily files) | NSE bulk delivery CSV (1 file, all stocks) |
| Nifty 50 index | yfinance 10yr (`^NSEI`) | yfinance 1 day or NSE |
| Fundamentals | Screener.in CSV export (manual) | Re-export quarterly |
| Sector mapping | yfinance metadata (auto during universe sync) | Refresh on rebalance |
| Corporate actions | Auto-adjusted by yfinance | NSE corporate actions page |
| Nifty 500 list | NSE CSV download | Check monthly |

### Bootstrap Execution (completed March 2026)

All bootstrap ran locally, then migrated to Neon + S3.

```
PHASE 1 — Stock Universe ✅
  └─ Fetched Nifty 500 constituent CSV from NSE (500 symbols)
  └─ Synced to `stocks` table with yfinance metadata (name, sector, market_cap)
  └─ 2 stocks deactivated (LTIM, TATAMOTORS — no longer in Nifty 500)
  └─ Duration: ~2.5 min

PHASE 2 — OHLCV Price History (10 years) ✅
  └─ Source: yfinance (auto-adjusted prices, splits handled)
  └─ 452 new stocks bootstrapped (50 already existed from Nifty 50 phase)
  └─ Zero yfinance failures — all symbols resolved
  └─ Result: 1,008,984 rows in eod_prices
  └─ Duration: ~9 min

PHASE 3 — Delivery Data (2 years) ✅
  └─ Source: NSE bulk CSV (sec_bhavdata_full) — 1 file per day, all stocks
  └─ 493 trading days fetched, 236,652 new rows written
  └─ Combined with existing Nifty 50 data: 339,550 total rows
  └─ Delivery history limited to 2 years (NSE archive depth)
  └─ Duration: ~5 min

PHASE 4 — Nifty 50 Index ✅
  └─ 2,464 rows (2016→2026), fetched via yfinance
  └─ No re-fetch needed

PHASE 5 — Fundamentals (deferred)
  └─ Pending Screener.in premium subscription
  └─ Manual CSV export → parse → load into `fundamentals` table

PHASE 6 — Migrate to Production ✅
  └─ pg_dump local → pg_restore to Neon
  └─ Upload parquet files to S3
```

### Parquet File Strategy

Maintain **separate parquet files by data type** (not per-stock):

```
data/parquet/                    ← local cache (gitignored)
  price_data.parquet             ← all stocks, all dates, OHLCV
  delivery_data.parquet          ← all stocks, all dates, delivery
  nifty50_index.parquet          ← Nifty 50 index daily OHLCV

s3://momentum-edge-data/         ← production archive
  parquet/
    price_data.parquet
    delivery_data.parquet
    nifty50_index.parquet
```

**Why single files per data type (not per stock):**
- Parquet is columnar — scanning across all stocks for a date range is fast
- ~1M rows ≈ 35 MB per file — small enough for single-file access
- Simpler to manage, backup, and restore vs 500+ individual files
- Daily append is just concat + deduplicate + overwrite

### Current Data State (Nifty 500 bootstrap)

| Data | Rows | Stocks | Date Range | Notes |
|------|------|--------|------------|-------|
| `stocks` | 502 | 500 active, 2 inactive | — | LTIM + TATAMOTORS deactivated |
| `eod_prices` | 1,008,984 | 500 | 2016 → 2026 | 10yr via yfinance |
| `delivery_data` | 339,550 | 500 | 2024 → 2026 | 2yr via NSE bulk CSV |
| `nifty50_index` | 2,464 | — | 2016 → 2026 | Via yfinance |
| `fundamentals` | 301 | 49 (Nifty 50 only) | ~6 quarters each | Pending Screener.in re-export |
| `indicators` | 49 | — | Latest day only | Recalculated each pipeline run |
| `sector_data` | 12 | — | — | Auto-populated from yfinance |

---

## 2. Project Folder Structure

```
unipro-engine/
│
├── src/momentum_edge/
│   │
│   ├── config.py                  ← Settings loader (pydantic-settings, picks DB from env)
│   │
│   ├── db/
│   │   ├── session.py             ← SQLAlchemy engine + SessionLocal + get_db()
│   │   ├── models.py              ← All ORM table definitions
│   │   └── repositories/          ← One repo class per domain (stocks, prices, scores…)
│   │       ├── stock_repo.py
│   │       ├── price_repo.py
│   │       ├── fundamentals_repo.py
│   │       └── watchlist_repo.py
│   │
│   ├── data/                      ← M1 — External data ingestion
│   │   ├── nse_bulk.py            ← NSE bulk CSV downloader (all stocks, 1 HTTP call)
│   │   ├── stock_universe.py      ← Nifty 50/500 universe sync from NSE + yfinance
│   │   ├── prices.py              ← OHLCV bootstrap (yfinance) + daily (NSE bulk CSV)
│   │   ├── delivery.py            ← Delivery bootstrap (NSE bulk CSV) + daily
│   │   ├── nse_indices.py         ← Nifty 50 index price fetch (yfinance)
│   │   ├── fundamentals.py        ← Screener.in CSV import (no API)
│   │   ├── parquet_store.py       ← Local parquet read/write layer
│   │   └── storage.py             ← S3/local storage abstraction (to build)
│   │
│   ├── scanner/                   ← M2, M3, M7, M8 — All filtering logic
│   │   ├── market_regime.py       ← M2: Bull / Neutral / Bear classification
│   │   ├── sector_rotation.py     ← M3: Sector momentum ranking
│   │   ├── trend_template.py      ← M7: Minervini 6-condition hard filter
│   │   └── breakout_patterns.py   ← M8: VCP, base, resistance, volume breakout
│   │
│   ├── indicators/                ← Technical indicator calculations
│   │   ├── moving_averages.py     ← MA50, MA150, MA200 (pandas/pandas-ta)
│   │   ├── relative_strength.py   ← RS score vs Nifty 50
│   │   └── volume_analysis.py     ← Delivery %, accumulation signals
│   │
│   ├── ranking/                   ← M4, M5, M6, M9, M10
│   │   ├── momentum_score.py      ← M4: Multi-timeframe momentum (max 40 pts)
│   │   ├── canslim_score.py       ← M5: Fundamental hard filters + score (max 25 pts)
│   │   ├── accumulation_score.py  ← M6: Institutional accumulation score (max 15 pts)
│   │   ├── composite_score.py     ← M9: Combines all module scores (max 125 pts)
│   │   └── watchlist.py           ← M10: Generates + persists ranked watchlist
│   │
│   ├── pipeline/
│   │   ├── runner.py              ← M11: Master pipeline orchestrator (runs M1→M10)
│   │   └── cron.py                ← Railway cron entry point
│   │
│   ├── api/                       ← FastAPI application
│   │   ├── app.py                 ← FastAPI app factory + CORS
│   │   ├── routes/                ← Route modules
│   │   │   ├── watchlist.py
│   │   │   ├── scores.py
│   │   │   ├── regime.py
│   │   │   ├── sectors.py
│   │   │   └── stocks.py
│   │   └── schemas/               ← Pydantic response models
│   │       ├── watchlist.py
│   │       ├── scores.py
│   │       └── common.py
│   │
│   ├── notifications/             ← Email notifications
│   │   ├── sender.py              ← Resend email client
│   │   └── templates.py           ← Email templates (digest, alerts)
│   │
│   └── utils/
│       ├── logger.py              ← Structured logging (loguru)
│       ├── date_utils.py          ← NSE trading calendar helpers
│       └── retry.py               ← Retry decorator for HTTP calls
│
├── migrations/                    ← Alembic migration files
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── 3343baaf44f6_initial_schema.py
│
├── tests/
│   ├── conftest.py                ← Pytest fixtures (test DB session)
│   ├── test_trend_template.py
│   ├── test_momentum_score.py
│   └── test_canslim.py
│
├── scripts/
│   └── run_pipeline.sh            ← Shell wrapper for local cron
│
├── main.py                        ← CLI entry point
├── pyproject.toml
├── alembic.ini
├── Procfile                       ← Railway process definitions
├── railway.toml                   ← Railway build config
├── .env                           ← Local overrides (gitignored)
├── .env.example                   ← Template committed to repo
└── .gitignore
```

---

## 3. Database Design — All 10 Tables

Mapping directly from the Use Case Document (Section 5). Universe: Nifty 500 (~500 symbols).

```
┌──────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐
│     stocks       │    │     price_data       │    │   delivery_data     │
│──────────────────│    │─────────────────────│    │─────────────────────│
│ id (PK)          │◀───│ stock_id (FK)        │    │ stock_id (FK)       │
│ symbol (unique)  │    │ date                 │    │ date                │
│ name             │    │ open / high / low    │    │ delivery_qty        │
│ sector_id (FK)   │    │ close / volume       │    │ delivery_pct        │
│ market_cap       │    │ UNIQUE(stock_id,date)│    │ UNIQUE(stock_id,date│
│ exchange         │    └─────────────────────┘    └─────────────────────┘
│ isin             │
└──────────────────┘
         │
         ▼
┌──────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐
│   sector_data    │    │    fundamentals      │    │     indicators      │
│──────────────────│    │─────────────────────│    │─────────────────────│
│ id (PK)          │    │ stock_id (FK)        │    │ stock_id (FK)       │
│ sector_name      │    │ quarter (e.g.Q3FY25) │    │ date                │
│ parent_sector    │    │ eps / revenue        │    │ ma50 / ma150 / ma200│
└──────────────────┘    │ roe / margin / pe    │    │ rs_score / atr      │
                        │ UNIQUE(stock_id,qtr) │    │ high_52w / low_52w  │
                        └─────────────────────┘    │ UNIQUE(stock_id,date│
                                                    └─────────────────────┘

┌──────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐
│     scores       │    │      watchlist       │    │       users         │
│──────────────────│    │─────────────────────│    │─────────────────────│
│ stock_id (FK)    │    │ date                 │    │ id (PK)             │
│ date             │    │ stock_id (FK)        │    │ email (unique)      │
│ momentum_score   │    │ composite_score      │    │ tier (basic/pro/prem│
│ fundamental_score│    │ pattern_type         │    │ api_key_encrypted   │
│ sector_score     │    │ regime               │    │ created_at          │
│ technical_score  │    │ stop_loss_level      │    └─────────────────────┘
│ accumulation_scor│    │ sector_name          │
│ breakout_score   │    │ sector_rank          │    ┌─────────────────────┐
│ composite_score  │    └─────────────────────┘    │       orders        │
│ UNIQUE(stock,date│                                │─────────────────────│
└──────────────────┘                                │ id (PK)             │
                                                    │ user_id (FK)        │
                                                    │ stock_id (FK)       │
                                                    │ qty / price         │
                                                    │ status / kite_id    │
                                                    └─────────────────────┘
```

---

## 4. Database Adapter — Local vs Neon

The single `DATABASE_URL` env var controls which DB is used. No code changes needed to switch.

```
┌─────────────────────────────────────────────────────────────────────┐
│                        config.py (pydantic-settings)                │
│                                                                     │
│  DATABASE_URL=postgresql://...   ◀──── .env  (local brew postgres)  │
│                          OR      ◀────  env var set externally       │
│                               (Neon pooled URL for production)      │
│                                                                     │
│  Engine created once in db/session.py using settings.database_url   │
│  All modules, Alembic, and API use the SAME engine instance         │
└─────────────────────────────────────────────────────────────────────┘
```

**Local development `.env`:**

```
DATABASE_URL=postgresql://arvbsnt@localhost:5432/momentum_edge
DB_TARGET=local
```

**Neon production (Railway env vars):**

```
DATABASE_URL=postgresql://user:pass@ep-xxx.us-east-2.aws.neon.tech/momentum_edge?sslmode=require
DB_TARGET=neon
```

**psycopg2-binary** is used as the synchronous adapter for both targets (no code difference).

**Connection pool settings:**

| Setting        | Local | Neon (Production)        |
| -------------- | ----- | ------------------------ |
| `pool_size`    | 5     | 3                        |
| `max_overflow` | 10    | 5                        |
| `pool_timeout` | 30s   | 30s                      |
| `pool_recycle` | 1800s | 300s                     |
| `pool_pre_ping`| False | True                     |
| `connect_args` | `{}`  | `{"sslmode": "require"}` |

SSL is required for Neon. The adapter adds `sslmode=require` via `connect_args` automatically when `DB_TARGET=neon`.

---

## 5. All Required Dependencies

### 5.1 Python Dependencies (pyproject.toml)

| Package             | Version | Purpose                                       |
| ------------------- | ------- | --------------------------------------------- |
| `sqlalchemy`        | ≥2.0    | ORM + query builder for all DB access         |
| `alembic`           | ≥1.18   | Database migration management                 |
| `psycopg2-binary`   | ≥2.9    | PostgreSQL sync adapter (local + Neon)        |
| `pydantic`          | ≥2.12   | Data validation, schema models                |
| `pydantic-settings` | ≥2.13   | Settings from `.env` with auto-casting        |
| `python-dotenv`     | ≥1.2    | `.env` file loading                           |
| `pandas`            | ≥3.0    | All data manipulation, indicator calculation  |
| `numpy`             | ≥2.0    | Numerical operations                          |
| `yfinance`          | ≥0.2    | Nifty 50 (`^NSEI`) and stock OHLCV bootstrap  |
| `pyarrow`           | ≥18.0   | Parquet read/write engine for archive layer   |
| `pandas-ta`         | ≥0.4    | Technical indicators (MA, ATR, RSI)           |
| `httpx`             | ≥0.28   | Async-capable HTTP client for NSE + API calls |
| `loguru`            | ≥0.7    | Structured logging with file rotation         |
| `fastapi`           | ≥0.115  | REST API for watchlist + scores               |
| `uvicorn[standard]` | ≥0.34   | ASGI server for FastAPI                       |
| `boto3`             | ≥1.35   | AWS S3 client for parquet archive             |
| `resend`            | ≥2.0    | Email API for digest + alerts                 |
| `hatchling`         | ≥1.29   | Build backend (already present)               |

**To be added later (Phase 2+):**

| Package        | Purpose                                                |
| -------------- | ------------------------------------------------------ |
| `asyncpg`      | Async PostgreSQL adapter for FastAPI                   |
| `kiteconnect`  | Zerodha Kite API client                                |
| `cryptography` | AES-256 encryption for API keys at rest                |
| `razorpay`     | Payment integration                                    |

### 5.2 Dev/Test Dependencies (uv dev group)

| Package       | Purpose                                            |
| ------------- | -------------------------------------------------- |
| `pytest`      | Test runner                                        |
| `pytest-cov`  | Coverage reporting                                 |
| `factory-boy` | Test data factories                                |
| `freezegun`   | Freeze dates in tests                              |
| `ruff`        | Linting + formatting (replaces flake8/black/isort) |
| `mypy`        | Static type checking                               |

---

## 6. Infrastructure

### 6.1 Local Development

| Component       | Technology                 | Notes                                            |
| --------------- | -------------------------- | ------------------------------------------------ |
| Python runtime  | 3.12 via uv                | `.python-version` pinned                         |
| Package manager | uv 0.10+                   | Lockfile committed                               |
| Database        | PostgreSQL 16 via Homebrew | `brew services start postgresql@16`              |
| DB migrations   | Alembic                    | `PYTHONPATH=src uv run alembic upgrade head`     |
| Scheduler       | macOS cron (`crontab`)     | `0 16 * * 1-5 /path/scripts/run_pipeline.sh`    |
| API server      | Uvicorn (dev mode)         | `PYTHONPATH=src uv run uvicorn ...  --reload`    |
| CLI             | Rich CLI via `main.py`     | `PYTHONPATH=src uv run python main.py`           |

### 6.2 Production (Neon + Railway + S3)

| Component  | Technology                  | Notes                                           |
| ---------- | --------------------------- | ----------------------------------------------- |
| Compute    | Railway (Python)            | Two services: cron + API                        |
| Database   | Neon PostgreSQL             | Pooled endpoint, `sslmode=require`              |
| Storage    | AWS S3                      | Parquet archive + daily backups                 |
| Email      | Resend                      | Daily digest + alert notifications              |
| Scheduler  | Railway Cron                | `30 10 * * 1-5` UTC = 4:00 PM IST Mon–Fri      |
| Migrations | Alembic                     | Run once pointing at Neon URL                   |

### 6.3 FastAPI Endpoints

| Method | Path                      | Purpose                          |
| ------ | ------------------------- | -------------------------------- |
| GET    | `/health`                 | Health check                     |
| GET    | `/api/v1/watchlist`       | Today's ranked watchlist         |
| GET    | `/api/v1/scores/{symbol}` | Score breakdown for a symbol     |
| GET    | `/api/v1/regime`          | Current market regime            |
| GET    | `/api/v1/sectors`         | Sector rotation rankings         |
| GET    | `/api/v1/stocks`          | Stock universe (Nifty 500 list)  |

### 6.4 Phase 2+ (Future)

| Component     | Technology                                      |
| ------------- | ----------------------------------------------- |
| Frontend      | React (separate repo) + Neon Auth               |
| Broker API    | Zerodha Kite integration                        |
| Payments      | Razorpay                                        |
| Monitoring    | Telegram bot alerts on pipeline failure         |

---

## 6.5 Data Retention and File Strategy

### Decision

- Keep PostgreSQL as the operational source of truth for daily pipeline, scoring, and API queries.
- Keep Parquet as a historical archive/rebuild layer stored on S3 (not as the runtime source for daily pipeline).
- Do not persist raw downloaded zip/csv files from NSE after successful ingestion.

### Nifty 500 Source

- Use `yfinance` with symbol `^NSEI` for index history and daily close reference.
- Stock universe: Nifty 500 (~500 symbols), expanded from Nifty 50 MVP.

### What We Store

| Layer                          | Stored In         | Purpose                                     |
| ------------------------------ | ----------------- | ------------------------------------------- |
| Daily operational data         | Neon PostgreSQL   | Daily scoring, filtering, API, alerts       |
| Historical bootstrap archive   | S3 (Parquet)     | Fast bulk reprocessing/backtesting          |
| Raw downloaded files (zip/csv) | Not retained      | Parse then discard                          |

### Recommended Parquet Footprint (10-year horizon)

Assumption: ~500 symbols (Nifty 500) x ~2,500 trading days ≈ 1,250,000 rows per large table.

| Dataset                 | Approx Rows | Parquet Size (snappy) |
| ----------------------- | ----------- | --------------------- |
| `price_data.parquet`    | 1,250,000   | ~45 MB                |
| `delivery_data.parquet` | 1,250,000   | ~35 MB                |
| `indicators.parquet`    | 1,250,000   | ~60 MB                |
| `nifty50_index.parquet` | ~2,500      | < 1 MB                |
| **Total**               | —           | **~140 MB**           |

### S3 Bucket Structure

```
s3://momentum-edge-data/
  parquet/
    price_data.parquet
    delivery_data.parquet
    indicators.parquet
    nifty50_index.parquet
  backups/
    YYYY-MM-DD/
      ...
```

All parquet files are also cached locally at `data/parquet/` (gitignored) when `STORAGE_BACKEND=local`.

---

## 7. Module-to-File Mapping

| Use Case Module        | File                            | Key Function(s)                                           |
| ---------------------- | ------------------------------- | --------------------------------------------------------- |
| M1 — NSE Bulk CSV      | `data/nse_bulk.py`              | `fetch_bhav_csv(date)`, `fetch_bhav_csv_range(from, to)`  |
| M1 — Stock Universe    | `data/stock_universe.py`        | `sync_stock_universe(db)`, `fetch_nifty500_symbols()`     |
| M1 — Prices            | `data/prices.py`                | `bootstrap_prices(db)`, `ingest_daily_prices(db, date)`   |
| M1 — Delivery          | `data/delivery.py`              | `bootstrap_delivery_bulk(db)`, `ingest_daily_delivery()`  |
| M1 — Index data        | `data/nse_indices.py`           | `fetch_nifty50_history()`, `fetch_nifty50_close(date)`    |
| M1 — Fundamentals      | `data/fundamentals.py`          | `fetch_fundamentals(symbol)`, `sync_fundamentals(db)`     |
| M1 — Parquet store     | `data/parquet_store.py`         | `append_prices(df)`, `append_delivery(df)`                |
| M2 — Market Regime     | `scanner/market_regime.py`      | `classify_regime(db, date) -> RegimeEnum`                 |
| M3 — Sector Rotation   | `scanner/sector_rotation.py`    | `rank_sectors(db, date) -> list[SectorRank]`              |
| M4 — Momentum Ranking  | `ranking/momentum_score.py`     | `score_momentum(df) -> float`                             |
| M5 — CANSLIM Filter    | `ranking/canslim_score.py`      | `apply_canslim_filter(df) -> bool, float`                 |
| M6 — Accumulation      | `ranking/accumulation_score.py` | `score_accumulation(df) -> float`                         |
| M7 — Trend Template    | `scanner/trend_template.py`     | `passes_trend_template(df) -> bool`                       |
| M8 — Breakout Patterns | `scanner/breakout_patterns.py`  | `detect_pattern(df) -> PatternResult`                     |
| M9 — Composite Score   | `ranking/composite_score.py`    | `compute_composite(scores) -> float`                      |
| M10 — Watchlist        | `ranking/watchlist.py`          | `generate_watchlist(db, date, regime)`                    |
| M11 — Pipeline runner  | `pipeline/runner.py`            | `run_pipeline(date)`                                      |
| Cron entry point       | `pipeline/cron.py`              | `main()` — Railway cron target                            |
| API — App              | `api/app.py`                    | FastAPI application factory                               |
| API — Routes           | `api/routes/*.py`               | Endpoint handlers                                         |
| Notifications          | `notifications/sender.py`       | `send_digest(watchlist)`, `send_alert(msg)`               |

---

## 8. Environment Variables Reference

| Variable                | Required    | Example                                                                  | Notes                              |
| ----------------------- | ----------- | ------------------------------------------------------------------------ | ---------------------------------- |
| `DATABASE_URL`          | ✅          | `postgresql://user:pass@ep-xxx.us-east-2.aws.neon.tech/momentum_edge?sslmode=require` | Neon pooled URL for prod           |
| `DB_TARGET`             | optional    | `local` or `neon`                                                        | Controls SSL + pool settings       |
| `APP_ENV`               | optional    | `development`                                                            | Enables SQLAlchemy echo            |
| `LOG_LEVEL`             | optional    | `INFO`                                                                   | loguru level                       |
| `NSE_BHAV_BASE_URL`     | optional    | NSE CDN base                                                             | Override for testing               |
| `FUNDAMENTALS_API_KEY`  | Phase 2     | `sk_...`                                                                 | Screener.in or Tijori API key      |
| `CORS_ORIGINS`          | optional    | `http://localhost:3000,https://app.momentumedge.in`                      | Allowed CORS origins for API       |
| `AWS_ACCESS_KEY_ID`     | prod        | `AKIA...`                                                                | AWS credentials for S3             |
| `AWS_SECRET_ACCESS_KEY` | prod        | `...`                                                                    | AWS credentials for S3             |
| `AWS_REGION`            | prod        | `ap-south-1`                                                             | AWS region for S3 bucket           |
| `S3_BUCKET`             | prod        | `momentum-edge-data`                                                     | S3 bucket name                     |
| `STORAGE_BACKEND`       | optional    | `local` or `s3`                                                          | Parquet storage target             |
| `RESEND_API_KEY`        | prod        | `re_...`                                                                 | Resend email API key               |
| `RESEND_FROM_EMAIL`     | prod        | `alerts@momentumedge.in`                                                 | Sender email address               |
| `ALERT_EMAIL`           | prod        | `user@example.com`                                                       | Recipient for digest + alerts      |

---

## 9. Pipeline Execution Flow (Cron → watchlist in DB → email)

```
Railway Cron Service @ 10:30 UTC (4:00 PM IST) Mon-Fri
    └── pipeline/cron.py
            └── pipeline/runner.py  run_pipeline(today)

pipeline/runner.py  run_pipeline(today)
    │
    ├─ M1  data.nse_bulk.fetch_bhav_csv(today)     ← 1 HTTP call, all 500 stocks
    │      → splits into OHLCV (prices.py) + delivery (delivery.py)
    │      data.nse_indices.fetch_nifty50_close(today)
    │      → writes to: eod_prices, delivery_data
    │
    ├─ M4/M7  indicators calculated for all stocks
    │      → writes to: indicators table
    │
    ├─ M2  regime = scanner.market_regime.classify_regime(today)
    │
    ├─ M3  sector_ranks = scanner.sector_rotation.rank_sectors(today)
    │      → writes to: scores.sector_score
    │
    ├─ M5  canslim_pass = ranking.canslim_score.apply_canslim_filter(symbol)
    │      (eliminates stocks below hard thresholds)
    │
    ├─ M6  ranking.accumulation_score.score_accumulation(symbol)
    │      → writes to: scores.accumulation_score
    │
    ├─ M7  scanner.trend_template.passes_trend_template(symbol)
    │      (hard filter — non-passing stocks removed)
    │
    ├─ M8  patterns = scanner.breakout_patterns.detect_pattern(symbol)
    │      → writes to: scores.breakout_score
    │
    ├─ M9  ranking.composite_score.compute_composite(all_scores)
    │      → writes to: scores table
    │
    ├─ M10 ranking.watchlist.generate_watchlist(today, regime)
    │      → writes to: watchlist table
    │
    └─ notifications.sender.send_digest(watchlist)
           → Resend email with daily ranked watchlist
           → API serves watchlist on next request
```

---

## 10. Current State vs Still To Build

| Area                                    | Status    | Notes                                                   |
| --------------------------------------- | --------- | ------------------------------------------------------- |
| uv project init                         | ✅ Done   | Python 3.12, hatchling                                  |
| PostgreSQL local                        | ✅ Done   | Brew pg16, `momentum_edge` DB created                   |
| Core DB session + models                | ✅ Done   | Full 10-table schema + Alembic migrations               |
| pydantic-settings config                | ✅ Done   | All env vars (DB, AWS, Resend, CORS)                    |
| Nifty 500 universe                      | ✅ Done   | 500 active stocks, fetched from NSE + yfinance metadata |
| OHLCV 10yr bootstrap                    | ✅ Done   | 1,008,984 rows via yfinance (all 500 stocks)            |
| Delivery 2yr bootstrap                  | ✅ Done   | 339,550 rows via NSE bulk CSV                           |
| Nifty 50 index                          | ✅ Done   | 2,464 rows (2016→2026) via yfinance                     |
| NSE bulk CSV ingestion                  | ✅ Done   | `nse_bulk.py` — 1 HTTP call = all stocks OHLCV+delivery |
| M1–M11 pipeline modules                 | ✅ Done   | Full scanning + ranking pipeline                        |
| Rich CLI interface                      | ✅ Done   | 10 commands: status, sync, bootstrap, ingest, run, etc. |
| Neon DB migration                       | ✅ Done   | pg_dump → pg_restore to Neon                            |
| S3 parquet upload                       | ✅ Done   | Parquet files uploaded to S3                             |
| Screener.in fundamentals               | ⬜ To do  | Pending premium subscription                            |
| FastAPI API                             | ⬜ To do  | REST endpoints for watchlist, scores, regime            |
| Resend email notifications              | ⬜ To do  | Daily digest + alert emails                             |
| Railway deployment                      | ⬜ To do  | Procfile, railway.toml, cron + API services             |
| Tests                                   | ⬜ To do  | Unit + integration tests                                |

---

_MomentumEdge Architecture v2.0 — Production deployment — March 2026_
