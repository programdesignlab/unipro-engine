This is a major strategy overhaul. Here's the backend impact analysis:

  Summary: v7 is essentially a rewrite of the scoring/ranking logic

  The data pipeline (M1 ingestion) is mostly fine. Everything from M2 onwards needs significant rework.

  ---
  1. Database Schema Changes (HIGH effort)

  6 new tables needed:

  ┌──────────────────────┬────────────────────────────────────────────────────────────┐
  │        Table         │                          Purpose                           │
  ├──────────────────────┼────────────────────────────────────────────────────────────┤
  │ fii_dii_data         │ Daily FII/DII net buy/sell with sector JSONB               │
  ├──────────────────────┼────────────────────────────────────────────────────────────┤
  │ shareholding_pattern │ Quarterly promoter/FII/DII holding %                       │
  ├──────────────────────┼────────────────────────────────────────────────────────────┤
  │ fii_breach_list      │ Daily NSE FII breach/caution list                          │
  ├──────────────────────┼────────────────────────────────────────────────────────────┤
  │ bulk_deals           │ Block/bulk deal log with institution flag                  │
  ├──────────────────────┼────────────────────────────────────────────────────────────┤
  │ signals              │ Replaces simple scores — Pending/Confirmed/Failed workflow │
  ├──────────────────────┼────────────────────────────────────────────────────────────┤
  │ performance_log      │ Trade tracking (entry/exit/P&L/MFE/MAE)                    │
  ├──────────────────────┼────────────────────────────────────────────────────────────┤
  │ backtest_results     │ Test results storage                                       │
  ├──────────────────────┼────────────────────────────────────────────────────────────┤
  │ walkforward_results  │ Walk-forward fold results                                  │
  └──────────────────────┴────────────────────────────────────────────────────────────┘

  Existing tables need heavy modification:

  ┌──────────────┬─────────────────────────────────────────────────────────────────────────────────────────────────┐
  │    Table     │                                             Changes                                             │
  ├──────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────┤
  │              │ +12 fields: is_asm, is_esm, is_financial, is_fii_capped_sector, promoter_holding_pct,           │
  │ stocks       │ fii_holding_pct, dii_holding_pct, fii_headroom_pct, is_fii_breached, is_fii_cautioned,          │
  │              │ free_float_pct, avg_daily_tv_cr                                                                 │
  ├──────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ price_data   │ +5 fields: adj_close, adj_factor, hit_upper_circuit, hit_lower_circuit, traded_value_cr.        │
  │              │ Delivery fields merged in (currently separate table)                                            │
  ├──────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ fundamentals │ +4 fields: reporting_date (critical — all queries filter by this), expected_result_date,        │
  │              │ analyst_revision, is_financial                                                                  │
  ├──────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ indicators   │ Near-total redesign — +15 fields: ma200_slope, mom_3m/6m/12_1, raw_score, scaled_score,         │
  │              │ vol_scalar, mom_quality, obv, adl_ratio, vol_ratio_20/50, delivery_trend, rs_rank               │
  ├──────────────┼─────────────────────────────────────────────────────────────────────────────────────────────────┤
  │ watchlist    │ Completely different schema — adds tier, signal_id, entry zones, earnings fields, OBV fields    │
  └──────────────┴─────────────────────────────────────────────────────────────────────────────────────────────────┘

  delivery_data table: v7 merges delivery into price_data. Current separate table becomes redundant for scoring but
  still used for storage.

  ---
  2. Scoring Logic Changes (HIGH effort — near-complete rewrite)

  ┌───────────────────────────────┬────────────────────────────────────────────┬─────────────────────────────────┐
  │            Current            │                     v7                     │             Impact              │
  ├───────────────────────────────┼────────────────────────────────────────────┼─────────────────────────────────┤
  │ CANSLIM hard filters (EPS     │ 4 junk filters only (positive EPS 2/4q,    │ Rewrite canslim_score.py        │
  │ 25%, Revenue 20%, ROE 15%)    │ not ASM, market cap band, liquidity)       │                                 │
  ├───────────────────────────────┼────────────────────────────────────────────┼─────────────────────────────────┤
  │ Absolute composite score (max │ Percentile-ranked momentum + vol scaling + │ Rewrite momentum_score.py,      │
  │  125 pts)                     │  bonus scores                              │ composite_score.py              │
  ├───────────────────────────────┼────────────────────────────────────────────┼─────────────────────────────────┤
  │ Delivery % in accumulation    │ Delivery % display only, zero scoring      │ Rewrite accumulation_score.py   │
  │ score                         │                                            │                                 │
  ├───────────────────────────────┼────────────────────────────────────────────┼─────────────────────────────────┤
  │ Simple RS score               │ Multi-timeframe momentum (12-1/6m/3m) with │ Rewrite indicator calculation   │
  │                               │  volatility scaling                        │                                 │
  ├───────────────────────────────┼────────────────────────────────────────────┼─────────────────────────────────┤
  │ 6-condition trend template    │ 8-condition (adds MA200 slope, 20-day      │ Modify trend_template.py        │
  │                               │ stage 2)                                   │                                 │
  ├───────────────────────────────┼────────────────────────────────────────────┼─────────────────────────────────┤
  │ Basic breakout detection      │ Full VCP math + OBV slope during base +    │ Rewrite breakout_patterns.py    │
  │                               │ circuit exclusion                          │                                 │
  ├───────────────────────────────┼────────────────────────────────────────────┼─────────────────────────────────┤
  │ 3-signal market regime        │ 6-signal + crash indicator + stability     │ Rewrite market_regime.py        │
  │                               │ rule                                       │                                 │
  └───────────────────────────────┴────────────────────────────────────────────┴─────────────────────────────────┘

  ---
  3. New Modules Needed (HIGH effort)

  ┌──────────────────────────┬────────────────────────────────────────────────────────────────────────┬────────────┐
  │          Module          │                                Purpose                                 │ Complexity │
  ├──────────────────────────┼────────────────────────────────────────────────────────────────────────┼────────────┤
  │ Signals engine           │ Pending → Confirmed/Failed workflow, 2-day confirmation                │ Medium     │
  ├──────────────────────────┼────────────────────────────────────────────────────────────────────────┼────────────┤
  │ Entry rules              │ 7 conditions (volume, close position, circuit, earnings, max entry 3%) │ Medium     │
  ├──────────────────────────┼────────────────────────────────────────────────────────────────────────┼────────────┤
  │ Exit engine              │ 9 exit rules (trailing, time, climax, regime, MA200 breach, rebalance) │ High       │
  ├──────────────────────────┼────────────────────────────────────────────────────────────────────────┼────────────┤
  │ Position sizing          │ 2% risk rule, portfolio heat (6% max), sector cap (30%)                │ Medium     │
  ├──────────────────────────┼────────────────────────────────────────────────────────────────────────┼────────────┤
  │ Corporate actions        │ adj_close calculation, cumulative adj_factor                           │ High       │
  ├──────────────────────────┼────────────────────────────────────────────────────────────────────────┼────────────┤
  │ Smart institutional flow │ FII/DII/bulk deal per-stock logic based on promoter holding            │ High       │
  ├──────────────────────────┼────────────────────────────────────────────────────────────────────────┼────────────┤
  │ Earnings date tracker    │ expected_result_date, 10-day safety rule                               │ Medium     │
  ├──────────────────────────┼────────────────────────────────────────────────────────────────────────┼────────────┤
  │ Backtesting framework    │ 10 tests, walk-forward, survivorship bias handling                     │ Very High  │
  ├──────────────────────────┼────────────────────────────────────────────────────────────────────────┼────────────┤
  │ OBV calculation          │ Full OBV + per-base slope extraction                                   │ Medium     │
  └──────────────────────────┴────────────────────────────────────────────────────────────────────────┴────────────┘

  ---
  4. Data Ingestion Changes (MEDIUM effort)

  ┌───────────────────────┬────────────┬───────────────────────────────────────────────┐
  │        Source         │   Status   │                  Work Needed                  │
  ├───────────────────────┼────────────┼───────────────────────────────────────────────┤
  │ NSE bhav copy (OHLCV) │ ✅ Working │ Add adj_close, adj_factor, circuit detection  │
  ├───────────────────────┼────────────┼───────────────────────────────────────────────┤
  │ Delivery data         │ ✅ Working │ Keep storing, remove from scoring             │
  ├───────────────────────┼────────────┼───────────────────────────────────────────────┤
  │ Corporate actions     │ ❌ New     │ NSE API scraper + adj_factor backfill         │
  ├───────────────────────┼────────────┼───────────────────────────────────────────────┤
  │ FII/DII daily         │ ❌ New     │ NSE API scraper → fii_dii_data                │
  ├───────────────────────┼────────────┼───────────────────────────────────────────────┤
  │ Shareholding pattern  │ ❌ New     │ Screener/BSE quarterly → shareholding_pattern │
  ├───────────────────────┼────────────┼───────────────────────────────────────────────┤
  │ FII breach list       │ ❌ New     │ NSE daily scraper → fii_breach_list           │
  ├───────────────────────┼────────────┼───────────────────────────────────────────────┤
  │ Bulk/block deals      │ ❌ New     │ NSE daily scraper → bulk_deals                │
  ├───────────────────────┼────────────┼───────────────────────────────────────────────┤
  │ ASM/ESM list          │ ❌ New     │ NSE surveillance page scraper                 │
  ├───────────────────────┼────────────┼───────────────────────────────────────────────┤
  │ Earnings dates        │ ❌ New     │ Screener.in → expected_result_date            │
  └───────────────────────┴────────────┴───────────────────────────────────────────────┘

  ---
  5. What's Unchanged (can keep as-is)

  - nse_bulk.py — bulk CSV downloader
  - stock_universe.py — Nifty 500 fetch (universe filtering happens separately)
  - prices.py / delivery.py — ingestion logic (add adj_close field)
  - nse_indices.py — Nifty 50 index fetch
  - parquet_store.py — storage layer
  - config.py — settings (will need new fields)
  - DB session, Alembic, CLI framework

  ---
  Effort Estimate

  ┌──────────────────────────────────────────────┬────────────┐
  │                   Category                   │   Effort   │
  ├──────────────────────────────────────────────┼────────────┤
  │ Schema migration (8 new tables, 5 altered)   │ Large      │
  ├──────────────────────────────────────────────┼────────────┤
  │ 4 new data source scrapers                   │ Large      │
  ├──────────────────────────────────────────────┼────────────┤
  │ Scoring/ranking rewrite (5 modules)          │ Large      │
  ├──────────────────────────────────────────────┼────────────┤
  │ New engines (signals, exit, position sizing) │ Large      │
  ├──────────────────────────────────────────────┼────────────┤
  │ Corporate actions + adj_close backfill       │ Medium     │
  ├──────────────────────────────────────────────┼────────────┤
  │ Backtesting framework                        │ Very Large │
  ├──────────────────────────────────────────────┼────────────┤
  │ Trend template + pattern detection updates   │ Medium     │
  └──────────────────────────────────────────────┴────────────┘

  Bottom line: ~70% of the backend scoring/ranking logic needs rewriting. The data ingestion layer is ~80% reusable.
  The backtesting framework is entirely new and is the single biggest piece of work.

  Want me to create a phased implementation plan, or should we start with the schema migration?
