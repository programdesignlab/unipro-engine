# MomentumEdge

Automated Indian stock scanning and ranking system for NSE equities.
Applies Mark Minervini's Trend Template + CANSLIM methodology to generate a daily ranked watchlist of momentum breakout candidates.

**Phase 1 (current):** Local MVP — Python backend + Rich CLI
**Phase 2+:** Cloud deployment, subscription SaaS, React frontend (separate repo)

---

## Setup

```bash
# Install dependencies
uv sync

# Copy and fill in environment variables
cp .env.example .env

# Run migrations
PYTHONPATH=src uv run alembic upgrade head
```

### Environment Variables

| Variable | Required | Example |
|---|---|---|
| `DATABASE_URL` | Yes | `postgresql://user@localhost:5432/momentum_edge` |
| `DB_TARGET` | No | `local` or `railway` |
| `APP_ENV` | No | `development` |
| `LOG_LEVEL` | No | `INFO` |

---

## CLI Reference

All commands run as:
```bash
PYTHONPATH=src uv run python main.py <command> [options]
```

---

### Data Management (M1)

#### `status`
Show DB connection status and row counts for all tables + parquet files.
```bash
PYTHONPATH=src uv run python main.py status
```

#### `sync-universe`
Sync the Nifty 50 stock master list from yfinance metadata into the `stocks` table.
```bash
PYTHONPATH=src uv run python main.py sync-universe
PYTHONPATH=src uv run python main.py sync-universe -s RELIANCE -s INFY  # specific symbols
```

#### `bootstrap`
One-time download of full 10-year OHLCV history from yfinance into `eod_prices` + parquet.
```bash
PYTHONPATH=src uv run python main.py bootstrap
PYTHONPATH=src uv run python main.py bootstrap --period 2y
PYTHONPATH=src uv run python main.py bootstrap -s RELIANCE -s TCS  # specific symbols
```

#### `bootstrap-delivery`
One-time download of full 10-year NSE delivery data via jugaad-data into `delivery_data` + parquet.
```bash
PYTHONPATH=src uv run python main.py bootstrap-delivery
PYTHONPATH=src uv run python main.py bootstrap-delivery --years 5
PYTHONPATH=src uv run python main.py bootstrap-delivery -s RELIANCE  # specific symbols
```

#### `sync-fundamentals`
Sync quarterly fundamentals (EPS, revenue, ROE, PE, D/E) from yfinance into `fundamentals`.
```bash
PYTHONPATH=src uv run python main.py sync-fundamentals
PYTHONPATH=src uv run python main.py sync-fundamentals -s RELIANCE -s INFY
```

#### `ingest`
Daily incremental data ingestion — prices + delivery + Nifty index for a single trading day.
```bash
PYTHONPATH=src uv run python main.py ingest                   # last trading day
PYTHONPATH=src uv run python main.py ingest --date 2026-03-17
```

---

### Scanning & Scoring (M2–M9)

#### `scan`
Run the full scan pipeline (indicators + market regime + sector rotation + all scoring modules) without data ingestion. Populates `indicators`, `scores`, and `watchlist` tables.
```bash
PYTHONPATH=src uv run python main.py scan                     # last trading day
PYTHONPATH=src uv run python main.py scan --date 2026-03-17
```

Output:
- Market regime (Bull / Neutral / Bear) + exposure level
- Top 3 sectors by momentum
- Count of stocks passing Minervini Trend Template
- Count of stocks in final watchlist

#### `run`
Full pipeline — M1 data ingestion followed immediately by M2–M10 scanning/scoring. Equivalent to `ingest` + `scan` in one command.
```bash
PYTHONPATH=src uv run python main.py run                      # last trading day
PYTHONPATH=src uv run python main.py run --date 2026-03-17
```

---

### Results

#### `watchlist`
Display the ranked watchlist for a given date with composite scores and score breakdown.
```bash
PYTHONPATH=src uv run python main.py watchlist                # last trading day
PYTHONPATH=src uv run python main.py watchlist --date 2026-03-17
PYTHONPATH=src uv run python main.py watchlist --top 10       # show top N (default: 20)
```

Output columns: Rank, Symbol, Composite Score, Pattern Type, Stop Loss, Sector, Sector Rank.
Also shows score breakdown (Momentum/Fundamental/Sector/Technical/Accumulation/Breakout) for top 5.

---

## Pipeline Modules

| Module | File | Purpose | Max Pts |
|---|---|---|---|
| M1 | `data/` | Data ingestion (prices, delivery, fundamentals, indices) | — |
| M2 | `scanner/market_regime.py` | Bull/Neutral/Bear classification | — |
| M3 | `scanner/sector_rotation.py` | Sector momentum ranking | 20 |
| M4 | `ranking/momentum_score.py` | Multi-timeframe momentum | 40 |
| M5 | `ranking/canslim_score.py` | CANSLIM fundamental filter | 25 |
| M6 | `ranking/accumulation_score.py` | Institutional accumulation | 15 |
| M7 | `scanner/trend_template.py` | Minervini 6-condition hard filter | 15 |
| M8 | `scanner/breakout_patterns.py` | VCP, base, resistance, volume breakout | 10 |
| M9 | `ranking/composite_score.py` | Composite score aggregation | **125** |
| M10 | `ranking/watchlist.py` | Generate + persist ranked watchlist | — |
| M11 | `pipeline/runner.py` | Master pipeline orchestrator | — |

---

## Regime-Based Filtering

| Regime | Conditions | Watchlist |
|---|---|---|
| Bull | Nifty > 200MA + >60% stocks above 50MA + highs > lows | Full list |
| Neutral | 2 of 3 signals positive | Top 50% of scores |
| Bear | All signals negative | Top 5 only |

---

## Typical Daily Workflow

```bash
# 1. After market close (~4 PM IST), ingest fresh data
PYTHONPATH=src uv run python main.py ingest

# 2. Run scan to score all stocks and generate watchlist
PYTHONPATH=src uv run python main.py scan

# 3. View results
PYTHONPATH=src uv run python main.py watchlist

# Or do all three in one command:
PYTHONPATH=src uv run python main.py run
```
