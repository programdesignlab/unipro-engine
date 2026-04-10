# MomentumEdge v7 Enhancement Plan

> **Status:** For review before implementation
> **Scope:** Migrate from v1 scoring (CANSLIM hard filters, delivery-based accumulation) to v7 (evidence-based momentum, volatility scaling, bonus scores)
> **Existing data:** Preserved — no re-pull of OHLCV (1M rows) or delivery (340K rows)

---

## 1. What Changes and What Doesn't

### Unchanged (keep as-is)
- `nse_bulk.py` — NSE bulk CSV downloader
- `stock_universe.py` — Nifty 500 universe sync
- `prices.py` — OHLCV ingestion (add adj_close column)
- `delivery.py` — delivery ingestion (data stored, not scored)
- `nse_indices.py` — Nifty 50 index fetch
- `parquet_store.py` — local parquet layer
- DB session, Alembic framework, CLI framework
- All existing price/delivery data in DB and parquet

### Needs Rework
- Scoring logic (M4–M9): near-complete rewrite
- Indicator calculation: expanded significantly
- Market regime (M2): 3 signals → 6 signals + crash indicator
- Trend template (M7): 6 conditions → 8 conditions
- Breakout patterns (M8): add VCP math, OBV, circuit exclusion
- Watchlist generation (M10): add tiers, signals workflow, position sizing

### New Modules
- Corporate actions ingestion + adj_close backfill
- Screener.in CSV fundamentals import
- FII/DII daily aggregate ingestion
- Bulk/block deals ingestion
- ASM/ESM surveillance ingestion
- Shareholding pattern ingestion (from Screener)
- Signals engine (Pending → Confirmed/Failed)
- Entry rules engine (7 conditions)
- Exit engine (9 exit rules)
- Position sizing engine
- Backtesting framework
- Walk-forward validation

---

## 2. Schema Changes

### 2.1 Existing Tables — Column Additions

**`stocks` — add 12 columns:**
```sql
ALTER TABLE stocks ADD COLUMN free_float_pct        FLOAT;
ALTER TABLE stocks ADD COLUMN avg_daily_tv_cr       FLOAT;
ALTER TABLE stocks ADD COLUMN is_asm                BOOLEAN DEFAULT FALSE;
ALTER TABLE stocks ADD COLUMN is_esm                BOOLEAN DEFAULT FALSE;
ALTER TABLE stocks ADD COLUMN is_financial          BOOLEAN DEFAULT FALSE;
ALTER TABLE stocks ADD COLUMN is_fii_capped_sector  BOOLEAN DEFAULT FALSE;
ALTER TABLE stocks ADD COLUMN promoter_holding_pct  FLOAT;
ALTER TABLE stocks ADD COLUMN fii_holding_pct       FLOAT;
ALTER TABLE stocks ADD COLUMN dii_holding_pct       FLOAT;
ALTER TABLE stocks ADD COLUMN fii_headroom_pct      FLOAT;
ALTER TABLE stocks ADD COLUMN is_fii_breached       BOOLEAN DEFAULT FALSE;
ALTER TABLE stocks ADD COLUMN is_fii_cautioned      BOOLEAN DEFAULT FALSE;
ALTER TABLE stocks ADD COLUMN shareholding_date     DATE;
ALTER TABLE stocks ADD COLUMN listing_date          DATE;
ALTER TABLE stocks ADD COLUMN delisted_date         DATE;
```

**`eod_prices` — add 5 columns:**
```sql
ALTER TABLE eod_prices ADD COLUMN adj_close           FLOAT;
ALTER TABLE eod_prices ADD COLUMN adj_factor          FLOAT DEFAULT 1.0;
ALTER TABLE eod_prices ADD COLUMN traded_value_cr     FLOAT;
ALTER TABLE eod_prices ADD COLUMN hit_upper_circuit   BOOLEAN DEFAULT FALSE;
ALTER TABLE eod_prices ADD COLUMN hit_lower_circuit   BOOLEAN DEFAULT FALSE;
```
Note: delivery_qty and delivery_pct stay in `delivery_data` table (not merged).
The `adj_close` column will be backfilled from existing `close` + corporate actions.

**`fundamentals` — add 4 columns:**
```sql
ALTER TABLE fundamentals ADD COLUMN reporting_date        DATE;
ALTER TABLE fundamentals ADD COLUMN expected_result_date  DATE;
ALTER TABLE fundamentals ADD COLUMN analyst_revision      FLOAT;
ALTER TABLE fundamentals ADD COLUMN is_financial          BOOLEAN DEFAULT FALSE;
```

**`indicators` — add 15 columns:**
```sql
ALTER TABLE indicators ADD COLUMN ma200_slope    FLOAT;
ALTER TABLE indicators ADD COLUMN mom_3m         FLOAT;
ALTER TABLE indicators ADD COLUMN mom_6m         FLOAT;
ALTER TABLE indicators ADD COLUMN mom_12_1       FLOAT;
ALTER TABLE indicators ADD COLUMN raw_score      FLOAT;
ALTER TABLE indicators ADD COLUMN scaled_score   FLOAT;
ALTER TABLE indicators ADD COLUMN vol_scalar     FLOAT;
ALTER TABLE indicators ADD COLUMN mom_vol_20d    FLOAT;
ALTER TABLE indicators ADD COLUMN mom_quality    FLOAT;
ALTER TABLE indicators ADD COLUMN obv            FLOAT;
ALTER TABLE indicators ADD COLUMN adl_ratio      FLOAT;
ALTER TABLE indicators ADD COLUMN vol_ratio_20   FLOAT;
ALTER TABLE indicators ADD COLUMN vol_ratio_50   FLOAT;
ALTER TABLE indicators ADD COLUMN pct_from_high  FLOAT;
ALTER TABLE indicators ADD COLUMN delivery_trend FLOAT;  -- display only
```

**`watchlist` — add columns:**
```sql
ALTER TABLE watchlist ADD COLUMN tier               INTEGER;
ALTER TABLE watchlist ADD COLUMN signal_id           INTEGER;
ALTER TABLE watchlist ADD COLUMN momentum_score      FLOAT;
ALTER TABLE watchlist ADD COLUMN fundamental_bonus   INTEGER;
ALTER TABLE watchlist ADD COLUMN obv_bonus           INTEGER;
ALTER TABLE watchlist ADD COLUMN adl_ratio           FLOAT;
ALTER TABLE watchlist ADD COLUMN delivery_trend      FLOAT;
ALTER TABLE watchlist ADD COLUMN inst_flow_signal    VARCHAR(20);
ALTER TABLE watchlist ADD COLUMN inst_flow_positive  BOOLEAN;
ALTER TABLE watchlist ADD COLUMN entry_zone_low      FLOAT;
ALTER TABLE watchlist ADD COLUMN entry_zone_high     FLOAT;
ALTER TABLE watchlist ADD COLUMN suggested_size_pct  FLOAT;
ALTER TABLE watchlist ADD COLUMN vol_scalar          FLOAT;
ALTER TABLE watchlist ADD COLUMN earnings_date       DATE;
ALTER TABLE watchlist ADD COLUMN earnings_flag       BOOLEAN;
```

### 2.2 New Tables

```sql
-- Daily FII/DII aggregate activity
CREATE TABLE fii_dii_data (
    date              DATE PRIMARY KEY,
    fii_buy_cr        FLOAT,
    fii_sell_cr       FLOAT,
    fii_net_cr        FLOAT,
    dii_buy_cr        FLOAT,
    dii_sell_cr       FLOAT,
    dii_net_cr        FLOAT
);

-- Quarterly shareholding pattern (from Screener)
CREATE TABLE shareholding_pattern (
    id                SERIAL PRIMARY KEY,
    stock_id          INTEGER REFERENCES stocks(id),
    quarter_end_date  DATE,
    promoter_pct      FLOAT,
    fii_pct           FLOAT,
    dii_pct           FLOAT,
    public_pct        FLOAT,
    UNIQUE (stock_id, quarter_end_date)
);

-- Corporate actions (splits, bonuses, rights)
CREATE TABLE corporate_actions (
    id                SERIAL PRIMARY KEY,
    stock_id          INTEGER REFERENCES stocks(id),
    ex_date           DATE NOT NULL,
    action_type       VARCHAR(20),   -- split, bonus, rights
    ratio_from        INTEGER,       -- e.g. 1 (in 1:5 split)
    ratio_to          INTEGER,       -- e.g. 5
    adj_factor        FLOAT,         -- multiplier (e.g. 0.2 for 1:5 split)
    raw_data          TEXT,          -- original NSE description
    UNIQUE (stock_id, ex_date, action_type)
);

-- Bulk and block deals
CREATE TABLE bulk_deals (
    id                SERIAL PRIMARY KEY,
    date              DATE NOT NULL,
    stock_id          INTEGER REFERENCES stocks(id),
    client_name       VARCHAR(200),
    deal_type         VARCHAR(10),   -- buy / sell
    quantity          BIGINT,
    price             FLOAT,
    is_institution    BOOLEAN DEFAULT FALSE,
    source            VARCHAR(10)    -- bulk / block
);

-- Trading signals (Pending → Confirmed/Failed workflow)
CREATE TABLE signals (
    id                SERIAL PRIMARY KEY,
    signal_date       DATE NOT NULL,
    stock_id          INTEGER REFERENCES stocks(id),
    pattern_type      VARCHAR(20),
    status            VARCHAR(20) DEFAULT 'Pending',  -- Pending/Confirmed/Failed/Expired
    pivot_price       FLOAT,
    stop_loss         FLOAT,
    entry_zone_low    FLOAT,
    entry_zone_high   FLOAT,
    volume_ratio      FLOAT,
    obv_slope         FLOAT,
    obv_bonus         INTEGER DEFAULT 0,
    obv_divergence    BOOLEAN DEFAULT FALSE,
    adl_ratio         FLOAT,
    inst_flow_signal  VARCHAR(20),
    inst_flow_positive BOOLEAN,
    base_length_days  INTEGER,
    base_depth_pct    FLOAT,
    regime            VARCHAR(20),
    crash_warning     BOOLEAN DEFAULT FALSE,
    earnings_date     DATE,
    days_to_earnings  INTEGER,
    earnings_flag     BOOLEAN DEFAULT FALSE,
    tier              INTEGER,
    composite_score   FLOAT,
    vol_scalar        FLOAT,
    fundamental_bonus INTEGER,
    confirmed_date    DATE,
    failed_date       DATE,
    created_at        TIMESTAMP DEFAULT NOW()
);

-- Trade performance log
CREATE TABLE performance_log (
    id                    SERIAL PRIMARY KEY,
    stock_id              INTEGER REFERENCES stocks(id),
    entry_date            DATE,
    exit_date             DATE,
    entry_price           FLOAT,
    actual_fill           FLOAT,
    exit_price            FLOAT,
    pnl_pct               FLOAT,
    pnl_inr               FLOAT,
    exit_reason           VARCHAR(30),
    holding_days          INTEGER,
    max_gain_pct          FLOAT,   -- MFE
    max_loss_pct          FLOAT,   -- MAE
    pattern_type          VARCHAR(20),
    regime_at_entry       VARCHAR(20),
    vol_scalar_at_entry   FLOAT,
    obv_bonus_at_entry    INTEGER,
    earnings_flagged      BOOLEAN,
    days_to_earnings      INTEGER
);

-- Backtest results storage
CREATE TABLE backtest_results (
    id              SERIAL PRIMARY KEY,
    test_name       VARCHAR(50),
    run_date        TIMESTAMP DEFAULT NOW(),
    period_start    DATE,
    period_end      DATE,
    parameters      JSONB,
    cagr            FLOAT,
    nifty_alpha     FLOAT,
    win_rate        FLOAT,
    avg_win         FLOAT,
    avg_loss        FLOAT,
    expectancy_pct  FLOAT,
    max_drawdown    FLOAT,
    sharpe_ratio    FLOAT,
    calmar_ratio    FLOAT,
    total_trades    INTEGER,
    avg_holding_days FLOAT,
    annual_returns  JSONB,
    passed_gate     BOOLEAN,
    notes           TEXT
);

-- Walk-forward validation results
CREATE TABLE walkforward_results (
    id              SERIAL PRIMARY KEY,
    window_type     VARCHAR(20),   -- expanding / rolling
    fold            INTEGER,
    train_start     DATE,
    train_end       DATE,
    test_start      DATE,
    test_end        DATE,
    is_sharpe       FLOAT,
    oos_sharpe      FLOAT,
    oos_is_ratio    FLOAT,
    is_cagr         FLOAT,
    oos_cagr        FLOAT,
    passed_gate     BOOLEAN
);
```

---

## 3. New Data Sources — Ingestion Plan

### 3.1 Corporate Actions (NSE API) — CRITICAL for adj_close

**Source:** `https://www.nseindia.com/api/corporates-corporateActions?index=equities`
**Status:** ✅ Tested, working
**Returns:** symbol, exDate, purpose (split/bonus/rights description)
**File:** `src/momentum_edge/data/corporate_actions.py`

**Bootstrap:**
- Fetch all corporate actions from 2015–2026 from NSE
- Parse split ratios from description text (e.g. "Stock Split From Rs.10/- To Rs.2/-" → 5:1)
- Calculate cumulative adj_factor per stock
- Backfill `adj_close = close * adj_factor` for all 1M existing price rows
- No re-download of price data needed — just multiply existing close by adj_factor

**Daily:**
- Check for new corporate actions after market close
- If new action found, update adj_factor and recompute adj_close for affected stock

### 3.2 Fundamentals (Screener.in CSV) — requires subscription

**Source:** Screener.in company page CSV export
**Status:** ⏳ Pending subscription
**File:** `src/momentum_edge/data/screener.py`

**Data available from Screener CSV:**
- Quarterly: EPS, revenue, net profit, OPM, ROE, D/E ratio
- reporting_date (when results were announced)
- Industry classification (→ is_financial flag)
- Shareholding: promoter %, FII %, DII %, public % (quarterly)

**Bootstrap:**
- Export CSV for each of the 500 stocks from Screener
- Parse quarterly financials + shareholding into DB
- Can be semi-automated: Screener allows bulk export by watchlist

**Daily:**
- Not daily — re-export quarterly after each earnings season
- Check for new quarterly results weekly

### 3.3 FII/DII Daily Aggregate (NSE API)

**Source:** `https://www.nseindia.com/api/fiidiiTradeReact`
**Status:** ✅ Tested, working
**Returns:** FII buy/sell/net, DII buy/sell/net (aggregate, not per-sector)
**File:** `src/momentum_edge/data/fii_dii.py`

**Bootstrap:**
- NSE API gives current day only
- Historical FII/DII data available from NSDL/SEBI monthly reports (limited)
- For backtesting: can approximate from bulk deal data

**Daily:**
- Single API call after market close → insert into `fii_dii_data`

**Note:** v7 wants per-sector FII flow, but NSE API only gives aggregate.
The smart institutional flow logic will use: aggregate FII/DII + promoter holding from Screener + bulk deal data. No per-sector FII flow.

### 3.4 Bulk/Block Deals (NSE API)

**Source:** `https://www.nseindia.com/api/snapshot-capital-market-largedeal`
**Status:** ✅ Tested, working
**Returns:** date, symbol, clientName, buySell, qty, price
**File:** `src/momentum_edge/data/bulk_deals.py`

**Bootstrap:**
- NSE API gives current day only
- Historical bulk deal data: NSE archives may have CSV files (to investigate)

**Daily:**
- Single API call → parse BULK_DEALS_DATA + BLOCK_DEALS_DATA
- Flag `is_institution` based on known MF/insurance/FII name patterns

### 3.5 ASM/ESM Surveillance (NSE API)

**Source:** `https://www.nseindia.com/api/reportASM`
**Status:** ✅ Tested, working
**Returns:** shortterm and longterm ASM lists with symbols
**File:** `src/momentum_edge/data/surveillance.py`

**Daily:**
- Single API call → update `is_asm` / `is_esm` flags on `stocks` table
- Used as hard filter: ASM/ESM stocks excluded from universe

### 3.6 Shareholding Pattern (Screener.in)

**Source:** Screener.in CSV export (shareholding tab)
**Status:** ⏳ Available with subscription
**Alternative:** NSE API gives promoter+public totals (no FII/DII split)

**Data:**
- promoter_pct, fii_pct, dii_pct, public_pct per quarter
- Feeds the smart institutional flow logic (promoter > 65% → use DII only)

**Bootstrap:**
- Export from Screener for all 500 stocks → `shareholding_pattern` table

**Quarterly refresh:**
- Re-export after each quarter's shareholding filings

---

## 4. Scoring Logic Changes

### 4.1 Universe Filtering (replaces CANSLIM hard filters)

**Current:** CANSLIM hard filters (EPS 25%+, Revenue 20%+, ROE 15%+)
**v7:** 4 junk filters only

```
Filter 1: Market cap 2,000–30,000 crore
Filter 2: Avg daily traded value >= Rs.15 crore
Filter 3: Not under ASM/ESM surveillance
Filter 4: Positive EPS in 2 of last 4 reported quarters (by reporting_date)
```

**Impact:** Rewrite `ranking/canslim_score.py` → `ranking/universe_filter.py`

### 4.2 Momentum Score (replaces current absolute scoring)

**Current:** Absolute momentum score (max 40 pts)
**v7:** Percentile-ranked momentum with volatility scaling

```
1. Calculate 12-1m, 6m, 3m momentum returns on adj_close
2. Percentile-rank each factor within universe (0-100)
3. Weighted composite: 12-1m (40%) + 6m (35%) + 3m (25%)
4. Volatility scaling: score * min(20% / annualized_vol, 2.0)
5. Filter: RS rank top 30% vs Nifty 50, momentum quality >= 0.55
```

**Impact:** Rewrite `ranking/momentum_score.py`

### 4.3 Fundamental Bonus (replaces CANSLIM score)

**Current:** CANSLIM score (max 25 pts) as hard filter
**v7:** Bonus scores only (max +20, min -5), never eliminates

```
+8  EPS acceleration (3 quarters accelerating growth)
+5  EPS growth >= 15%
+2  EPS growth >= 0% (but < 15%)
+4  Analyst upward revision (if available)
+3  D/E < 1.0 (skip financials)
-2  D/E > 3.0 (penalty, not elimination)
```

**Impact:** Rewrite `ranking/canslim_score.py` → `ranking/fundamental_bonus.py`

### 4.4 Accumulation Signals (replaces delivery-based scoring)

**Current:** Delivery % based accumulation (max 15 pts)
**v7:** OBV + A/D ratio + smart institutional flow

```
+5  OBV slope rising during base period (calculated from base_start only)
+4  A/D ratio >= 0.60 (up-volume / total-volume over 20 days)
+2  Smart institutional flow positive (FII/DII/bulk deal per stock)
```

Delivery % stored and displayed but **ZERO scoring weight**.

**Impact:** Rewrite `ranking/accumulation_score.py`

### 4.5 Sector Bonus (simplified)

**Current:** Sector score (max 20 pts)
**v7:** Simple bonus/penalty

```
+10  Stock in top 3 sectors
 -5  Stock in bottom 3 sectors
  0  Everything else
```

**Impact:** Simplify `scanner/sector_rotation.py`

### 4.6 Market Regime (expanded)

**Current:** 3 signals (Nifty vs 200MA, breadth, highs/lows)
**v7:** 6 signals + crash indicator + stability rule

```
S1: Nifty close > MA200                               (0 or 1)
S2: MA200 slope rising (vs 20 days ago)                (0 or 1)
S3: Breadth (% stocks above 50MA)                      (0, 0.5, or 1)
S4: New highs vs lows ratio                            (0, 0.5, or 1)
S5: Nifty extension from 200MA (0-15%=1, >25%=0)      (0, 0.5, or 1)
S6: Nifty 12-1m return positive                        (0 or 1)

Crash indicator: 2yr return < -20% AND 1m return > +10% → force Bear
Stability rule: regime changes only after 3 consecutive days at new level
```

**Impact:** Rewrite `scanner/market_regime.py`

### 4.7 Trend Template (expanded)

**Current:** 6 conditions
**v7:** 8 conditions

```
1-5: Same as current (price > MAs, MA ordering)
6:   MA200 slope rising (NEW)
7:   Within 20% of 52W high (was 25%)
8:   20+ consecutive days above MA200 (NEW — stage 2 established)
```

**Impact:** Modify `scanner/trend_template.py` — add 2 conditions

### 4.8 Pattern Detection (expanded)

**Current:** Basic VCP, base, breakout detection
**v7:** Full VCP math + OBV + entry rules

```
- VCP: 3+ contractions, getting shallower, volume declining
- OBV slope during base (from base_start only, not full history)
- OBV divergence detection (price lower low + OBV higher low)
- Circuit breaker exclusion
- False breakout filter (2-day confirmation: Pending → Confirmed/Failed)
- Entry rules: vol 1.5x, strong close, max 3% above pivot, earnings safety
```

**Impact:** Rewrite `scanner/breakout_patterns.py`

---

## 5. New Engines

### 5.1 Signals Engine
- Track signal lifecycle: Pending → Confirmed → Watchlist (or Failed/Expired)
- Day 1: breakout detected → status=Pending
- Day 2: price holds above pivot → Confirmed; falls below → Failed
- Earnings within 10 days → auto-downgrade to Tier 3
- Next-day open > pivot + 3% → Expired

**File:** `src/momentum_edge/engine/signals.py`

### 5.2 Exit Engine
- 9 exit rules checked daily for every open position
- Initial stop, breakeven, tiered trailing (40%/100% gain levels)
- Time stop (20 days, < 5% gain), climax exit, regime exit
- MA200 breach mandatory exit, RS rank rebalance

**File:** `src/momentum_edge/engine/exits.py`

### 5.3 Position Sizing Engine
- 2% risk per trade based on entry-to-stop distance
- Portfolio heat monitor (max 6% total risk)
- Sector concentration cap (30%)
- Position floor 2%, ceiling 20% of portfolio
- Adjusted by regime (risk_pct varies by regime level)

**File:** `src/momentum_edge/engine/position_sizing.py`

### 5.4 Backtesting Framework
- 10 structured tests (momentum weights, market cap, regime, etc.)
- Walk-forward validation (expanding + rolling windows)
- Realistic execution: next-day open, 0.5% slippage, full transaction costs
- Survivorship bias: include delisted stocks
- Results stored in `backtest_results` and `walkforward_results` tables

**File:** `src/momentum_edge/backtest/` (new package)

---

## 6. Implementation Phases

### Phase A — Schema + Data Foundation (no scoring changes yet)
1. Alembic migration: add columns to existing tables + create new tables
2. Backfill `adj_close` from corporate actions (NSE API)
3. Build Screener.in CSV importer (fundamentals + shareholding)
4. Build FII/DII daily ingester (NSE API)
5. Build bulk/block deals ingester (NSE API)
6. Build ASM/ESM surveillance checker (NSE API)
7. Update `stocks` table with new fields from Screener data

**Existing data untouched.** Only adds new columns/tables.

### Phase B — Scoring Rewrite
1. Universe filter (4 junk filters, replaces CANSLIM hard gates)
2. Momentum score (percentile ranking + vol scaling)
3. Fundamental bonus scores
4. Accumulation signals (OBV + A/D + smart institutional)
5. Expanded market regime (6 signals + crash indicator)
6. Expanded trend template (8 conditions)
7. Pattern detection (VCP math + OBV slope + entry rules)
8. Composite score assembly

### Phase C — New Engines
1. Signals engine (Pending → Confirmed workflow)
2. Exit engine (9 rules)
3. Position sizing engine
4. Updated pipeline runner (integrates all engines)
5. Updated watchlist generation (tiers, sizing)

### Phase D — Backtesting
1. Backtesting framework core
2. Tests 1-5 (momentum, market cap, regime, trend, fundamentals)
3. Tests 6-9 (VCP, exits, rebalancing, volume signals)
4. Test 10 (full system) + walk-forward validation

### Phase E — Production
1. Paper trading mode (3 months)
2. Performance tracking
3. Railway deployment with updated pipeline

---

## 7. Data Re-pull Assessment

| Data | Re-pull? | Reason |
|------|----------|--------|
| OHLCV (1M rows) | **No** | Existing data stays. Add `adj_close` column via backfill |
| Delivery (340K rows) | **No** | Keep as-is. Still stored, just not scored |
| Nifty 50 index (2.5K rows) | **No** | Already complete |
| Stock universe (500 stocks) | **No** | Already synced. Add new columns via ALTER |
| Corporate actions | **Yes (new)** | Fetch from NSE API, needed for adj_close backfill |
| Fundamentals | **Yes (replace)** | Current yfinance data is sparse. Replace with Screener CSV |
| Shareholding | **Yes (new)** | New data from Screener |
| FII/DII daily | **Yes (new)** | New data from NSE API (current day only, no backfill) |
| Bulk/block deals | **Yes (new)** | New data from NSE API (current day only) |
| ASM/ESM | **Yes (new)** | New data from NSE API (current day only) |

**Total new data to pull:** ~6 new data sources, but existing 1.35M rows of price+delivery data are fully preserved.

---

## 8. Settings / Configuration

All tunable parameters from v7 use case doc section 6 will go into `src/momentum_edge/config.py` as Settings fields with defaults from the document. These can be overridden via `.env` and are updated after each backtest test confirms optimal values.

Key settings groups:
- Universe filters (market cap band, liquidity threshold)
- Momentum weights (12-1m/6m/3m split)
- Volatility scaling (target, max scalar)
- Fundamental bonus points
- Accumulation bonus points
- Regime thresholds (6 signal scores → regime classification)
- Trend template parameters
- VCP parameters
- Entry rules (max entry above pivot, earnings safety days)
- Position sizing (risk per trade, heat limit, sector cap)
- Exit rules (stop %, trailing params, time stop)
- Watchlist (max stocks, pipeline trigger time)

---

_MomentumEdge v7 Enhancement Plan — March 2026_
_Review before implementation — no code changes until approved_
