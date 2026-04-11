# MomentumEdge — Pending Gaps & Status

Last updated: 2026-04-11

---

## Resolved

| Item | Status | Commit |
|------|--------|--------|
| Data ingestion: OPM calculated + stored | DONE | 1041d6f |
| Data ingestion: OCF extracted from Screener Excel | DONE | 1041d6f |
| Data ingestion: Trade receivables + receivable days | DONE | 1041d6f |
| Wire fast crash to pipeline | DONE | 1041d6f |
| Wire monster detection to pipeline (daily on open positions) | DONE | 1041d6f |
| Wire bull entry protocol to pipeline | DONE | 1041d6f |
| Wire turnaround scan to pipeline | DONE | 1041d6f |
| Wire exit cascade to pipeline | DONE | 1041d6f |
| Position lifecycle (create/update/close) | DONE | 1041d6f |
| Create market_regime_log table + migration | DONE | da78da0 |
| Regime logging for stability rule | DONE | 1041d6f |
| Beta calculated from 1yr returns vs Nifty | DONE | 1041d6f |
| PSU detection from promoter % + sector | DONE | 1041d6f |
| Cron strategy path fix | DONE | 1041d6f |
| Infra exception in pledge filter | DONE | 1041d6f |
| main.py scan command fixed (was importing deleted modules) | DONE | 1041d6f |
| Delete legacy composite_score.py | DONE | 1041d6f |
| Move notes.md to archive | DONE | 1041d6f |

---

## Remaining (low priority)

| Item | Priority | Notes |
|------|----------|-------|
| SEBI fine data population | Low | No automated data source — SEBI website or manual curation |
| SEBI investigation data | Low | Same as above |
| LODR fine data | Low | NSE penalty data — manual or scrape |
| `listing_date` gaps | Low | Fill from NSE master data for stocks missing it |
| BSE cross-validation | Low | bse_code column exists, need BSE bhav copy ingestion |
| Business pivot filter data source | Low | Intentionally disabled — MCA filings or manual |
| Backtest test_runner.py old param names | Low | Works via BacktestConfig.from_strategy() |
| Adversarial fold in walkforward | Low | v16 spec Fold 8 — implement when backtesting begins |
| Parquet noop stubs in data files | Trivial | Harmless no-ops, low cleanup value |
| 277KB v16 spec in docs/archive | Trivial | Consider .gitignore if repo size matters |
| ScanResult legacy model | Trivial | Still in models.py, table exists in DB but unused |

---

## UI Status

| Feature | Status | Notes |
|---------|--------|-------|
| Monster score on stock detail | DONE | Shows badge with threshold indicator |
| Exclusion reason on stock detail | DONE | Red banner with block name + reason |
| Exclusion count on dashboard | DONE | 5th stat card linking to exclusions page |
| Screener: pledge, beta, PSU columns | DONE | Red highlighting on dangerous values |
| Fundamental score range -20/+30 | DONE | All gauges, bars, and legends updated |
| Gain phase indicator on stock detail | Blocked | Needs live confirmed signals to create positions |
| Bull entry phase on regime page | Blocked | Shows when regime is Bear (protocol runs in pipeline) |
| Open positions page | Future | Table of active positions with phase, monster, P&L |
| Portfolio heat visualization | Future | Show risk vs regime heat cap |
| Signal history chart | Future | Timeline of past signals per stock |
| Backtest results page | Future | Metrics, equity curve, trade log |
