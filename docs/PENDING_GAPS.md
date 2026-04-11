# MomentumEdge — Pending Gaps, Enhancements & Missing Data

Last updated: 2026-04-10

---

## Critical: Pipeline Wiring

5 engine modules are **built and tested but not called from the daily pipeline**. They exist as standalone functions but the orchestrator (`pipeline/runner.py`) does not invoke them.

| Module | File | Function | Status |
|--------|------|----------|--------|
| Fast Crash Detector | `engine/fast_crash.py` | `detect_fast_crash()` | Built, not wired |
| Monster Detection | `engine/monster.py` | `calculate_monster_score()` | Built, only used in stock detail API |
| Bull Entry Protocol | `engine/bull_entry.py` | `evaluate_bull_entry_phase()` | Built, not wired |
| Turnaround Scan | `engine/turnaround.py` | `scan_turnarounds()` | Built, not wired |
| Exit Cascade | `engine/exit_cascade.py` | `evaluate_cascade()` | Built, not wired |

**What needs to happen:** Add calls to `runner.py` in the pipeline flow:
1. After M2 regime detection → call `detect_fast_crash()`, if active → short-circuit
2. After scoring → call `calculate_monster_score()` for open positions, store on `OpenPosition`
3. After regime detection → call `evaluate_bull_entry_phase()` if recovering from Bear
4. After watchlist generation → call `scan_turnarounds()` and persist results
5. After exit checks → call `evaluate_cascade()` for portfolio-level actions

**Dependency:** Requires open position tracking to be active (pipeline currently doesn't manage the `open_positions` table — see "Position Lifecycle" below).

---

## Critical: Data Ingestion Gaps

3 database columns exist but **no data is ingested** for them. This blocks multiple scoring signals and hard block filters.

| Column | Table | Used By | Ingestion Status |
|--------|-------|---------|-----------------|
| `ocf_cr` | fundamentals | OCF hard block filter, turnaround suppression, OCF quality penalty | **Not ingested** — Screener.in Excel doesn't have a mapped row for this yet |
| `opm` | fundamentals | Revenue+OPM simultaneous bonus (+12), OPM expansion bonus (+8) | **Not stored** — operating profit IS parsed from Screener Excel (row 49) but never written to DB |
| `trade_receivables_days` | fundamentals | Debtors critical (-5) and debtors warning (-3) penalties | **Not ingested** — needs Screener.in row mapping |

**What needs to happen:**
1. Map OCF from Screener.in annual/quarterly Excel (typically "Cash from Operating Activity" row)
2. Calculate `opm = (operating_profit / sales) * 100` and write to `opm` column (operating_profit is already parsed)
3. Map trade receivables from Screener.in balance sheet and calculate receivable days

**Impact without fix:** 5 scoring signals produce 0 points always (OPM simultaneous, OPM expansion, debtors critical, debtors warning, OCF quality). OCF hard block passes everything through (graceful degradation — not blocking, just not filtering).

---

## High: Position Lifecycle Not Active

The `open_positions` table exists with full v16 schema (gain_phase, monster_score, rs_below_floor_weeks, etc.) but **the pipeline does not create, update, or close positions**. Currently positions are only tracked:
- In the backtest engine (in-memory dicts)
- In `performance_log` (after trade close, for reporting)

**What needs to happen:**
1. When a signal is Confirmed → create an `OpenPosition` row
2. Daily pipeline → update current_price, gain_pct, gain_phase, holding_days for all active positions
3. When exit engine fires → mark position as closed (is_active=false, exit_reason, exit_phase)
4. Monster score → update on open positions daily
5. RS below floor weeks → increment/reset weekly counter

**Impact without fix:** Exit engine (4-phase), monster override, gain phase display in UI, and cascade layer all have no positions to operate on. The watchlist and signals work fine — it's the execution/tracking layer that's missing.

---

## Medium: Cron Job Strategy Path

`pipeline/cron.py` line 28 calls `run_pipeline(db, target)` without passing `strategy_path`. It uses the default path from `runner.py`, which works, but should be explicit.

**Fix:** Update cron.py to pass `strategy_path="strategies/momentum_edge.yaml"` explicitly.

---

## Medium: Screener OPM Storage

Operating profit IS extracted from Screener.in Excel (line 307 in `screener.py`) but the `_upsert_fundamentals` function does not include `opm` in the INSERT/UPDATE SQL.

**Fix:** Calculate OPM from existing operating_profit and sales values, add to upsert SQL.

---

## Low: Infra Exception in Pledge Filter

`ranking/universe_filter.py` line 185 has a TODO:
```python
# TODO: implement infra exception (D/E falling + revenue growth > 30%)
```

The pledge filter identifies infra stocks and applies a higher threshold (50% vs 20%) but doesn't implement the exception where infra with falling D/E AND revenue growth > 30% should be allowed through.

---

## Low: Business Pivot Filter (Data Source TBD)

`check_business_pivot` in `universe_filter.py` is intentionally disabled (`enabled: false` in YAML). The filter checks `Stock.business_pivot_count` but no data source exists to populate this field.

**Options:**
1. Manual curation (Screener.in doesn't provide this)
2. MCA (Ministry of Corporate Affairs) filings — object clause changes
3. Skip entirely — low-frequency event, manual override when needed

---

## UI Gaps

| Gap | Page | Status | Notes |
|-----|------|--------|-------|
| Gain phase indicator | Stock Detail | **Blocked** | Needs position lifecycle active to know which phase a stock is in |
| Bull entry protocol phase | Market Regime | **Blocked** | Needs pipeline to track and persist B1-B4 phase state |
| Open positions view | New page needed | **Blocked** | Needs position lifecycle active |
| Portfolio heat visualization | Dashboard or new page | Nice-to-have | Show current portfolio risk vs regime heat cap |
| Signal history chart | Stock Detail | Nice-to-have | Timeline of past signals for a stock |
| Backtest results page | New page | Nice-to-have | Show backtest metrics, equity curve, trade log |

---

## Data Quality Gaps

| Gap | Impact | Fix |
|-----|--------|-----|
| SEBI fine data not populated | `sebi_fine_last_24m` flag is always false | Need data source — SEBI website scraping or manual |
| SEBI investigation data not populated | `sebi_investigation_active` flag always false | Same as above |
| LODR fine data not populated | `lodr_fine_last_12m` flag always false | NSE penalty data |
| Beta not calculated | `Stock.beta` is always NULL | Calculate from 1yr daily returns vs Nifty |
| `is_psu` not populated | Flag always false | Can infer from promoter name containing "Government" or manual list |
| `listing_date` partially populated | Some stocks missing listing date | Fill from NSE master data |
| BSE cross-validation not built | `bse_code` column exists but unused | Need BSE bhav copy ingestion |

---

## Backtest Gaps

| Gap | Impact | Fix |
|-----|--------|-----|
| test_runner.py uses old param names | Tests reference `mom_weight_12m` etc. | Update to use `BacktestConfig.from_strategy()` |
| walkforward.py doesn't use strategy YAML | Uses hardcoded fold windows | Pass strategy config through |
| Parameter sweep only sweeps 3 params | `DEFAULT_SWEEP_PARAMS` has 3 entries | Add more FREE params from YAML |
| No adversarial fold (Fold 8) | v16 spec defines non-bull training fold | Implement in walkforward.py |

---

## Production Deployment Gaps

| Gap | Impact | Fix |
|-----|--------|-----|
| `notes.md` in root (not in docs) | Clutter | Move to docs/archive or delete |
| Old root-level MD files deleted from git but `UniProAI_MomentumEdge_v16 (3).md` still in docs/archive | Large file (284KB) in repo | Consider .gitignore or remove |
| No health check for pipeline cron | If pipeline fails, only loguru logs | Add Resend alert on pipeline failure (partially exists in cron.py) |
| `ranking/composite_score.py` is legacy wrapper | Still importable, `core/composite.py` is the real one | Delete or redirect import |

---

## Medium: `market_regime_log` Table Not Created

`scanner/market_regime.py` line 264 queries `market_regime_log` for the stability rule (3-day regime persistence). This table was never created via migration — the code has a try/except that silently skips the stability rule when the table doesn't exist.

**Fix:** Either create the table via Alembic migration, or store regime history in an existing table (e.g., `pipeline_log` or a new `regime_history` table).

---

## Low: `main.py scan` Command Not Updated

The `scan` CLI command (line ~253 in main.py) imports `run_indicators` and `classify_regime` directly and runs a partial pipeline. It does not accept `--strategy` or load strategy YAML.

**Fix:** Update `scan` command to accept `--strategy` and pass through to module calls.

---

## Low: Legacy `ScanResult` Model

`db/models.py` still defines `ScanResult` (table `scan_results`) — marked as "Legacy scaffold table — superseded by scores + watchlist". Safe to remove.

---

## Low: Parquet Noop Stubs

3 files have noop stub functions replacing the deleted `parquet_store` imports:
- `data/prices.py` → `append_prices()`
- `data/delivery.py` → `append_delivery()`
- `data/nse_indices.py` → `append_nifty_index()`

These are harmless but add dead code. Can be removed once all callers are cleaned up (the functions are called after DB writes, so removing them means removing those call sites too).

---

## Low: `.env.example` May Need v16 Vars

`.env.example` exists but may not include `NEON_AUTH_BASE_URL` or document the strategy YAML path.

**Fix:** Review and update `.env.example` with all current env vars.

---

## Low: 277KB v16 Spec in Archive

`docs/archive/UniProAI_MomentumEdge_v16 (3).md` is 277KB. Consider adding to `.gitignore` or removing from git history if repo size matters.

---

## Priority Order

1. **Data ingestion (OCF, OPM storage, trade receivables)** — blocks 5 scoring signals
2. **Wire 5 engine modules to pipeline** — blocks fast crash, monster, turnaround, cascade
3. **Position lifecycle in pipeline** — blocks exit engine, gain phase display, monster override
4. **Create `market_regime_log` table** — stability rule silently skipped without it
5. **Beta/PSU/SEBI data population** — blocks position sizing adjustments and filter accuracy
6. **Cron strategy path fix** — trivial, do anytime
7. **UI: gain phase + bull entry display** — after position lifecycle is active
8. **Backtest updates (test_runner, walkforward, sweep params)** — after pipeline is fully wired
9. **Cleanup** — composite_score.py, ScanResult model, parquet stubs, notes.md, .env.example update
10. **`main.py scan` command update** — accept --strategy flag
