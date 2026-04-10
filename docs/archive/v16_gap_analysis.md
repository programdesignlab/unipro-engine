# v16 Gap Analysis — MomentumEdge

**Document:** v16 spec vs current v7 implementation
**Date:** March 2026
**Source:** UniProAI_MomentumEdge_v16.md (March 2026 Final)

---

## Summary

The core v7 scoring stack is solid. The **exit engine is the single largest gap** — v16's 4-phase gain-based framework with 5-layer cascade is fundamentally different from the current 9-rule system. This change alone is responsible for the Force Motors 8.8x vs 7.2x simulation improvement documented in v16.

---

## What's Already Implemented (solid)

- Multi-timeframe momentum (12-1m / 6m / 3m) with volatility scaling (Barroso 2015)
- OBV + A/D ratio accumulation scoring
- Smart institutional flow signal (bulk deals, FII/DII routing by promoter %)
- 8-condition Minervini trend template
- VCP breakout pattern detection + 7 entry rules
- 6-signal market regime + crash indicator
- Composite scoring (M9)
- Signal lifecycle (Pending → Confirmed / Failed / Expired)
- Basic 2% risk rule position sizing

---

## The Gaps

### 🔴 Critical — Exit Engine: Complete Redesign

Highest priority. Directly impacts alpha.

#### Individual position exits

| What | v7 (current) | v16 |
|---|---|---|
| Exit framework | 9 flat rules | **4-phase gain-based** (0–25% / 25–100% / 100–200% / 200%+) |
| Phase 1 (0–25%) | Fixed stop | 8% stop from entry only — prove-it phase |
| Phase 2 (25–100%) | — | 20% trail from 10-week high |
| Phase 3 (100–200%) | — | 15% trail from 10-week high |
| Phase 4 (200%+) | — | Staged 25%+25% partial exits, trail core 50% at 8%; 10-week MA as primary |
| RS exit trigger | Single-day breach | **4 consecutive weeks** below RS floor (`rs_below_floor_weeks` counter) |
| Time stop | Simple | **Suppressed if ATR is compressing** (`atr_now < atr_entry × 0.70`) |
| Volume on pullbacks | Not tracked | Hold override if vol < 0.75× on down days; instant 25% exit if vol > 1.5× on down days |
| Trend integrity | Not checked | Higher highs/higher lows check overrides 21DMA counter |

#### 5-Layer Exit Cascade (UC-03B) — entirely new

Operates at portfolio level. All 5 layers checked daily for every open position.

| Layer | Signal | Trigger | Response |
|---|---|---|---|
| E1 | Climax Run | 80%+ gain + stock up >30% in any 15-day window | Sell 25% immediately, 25% at next new high, rest on close below 10DMA |
| E2 | Distribution Days | Index down >0.2% on higher volume — count in last 25 days | 3–4: tighten stops; 5: reduce 25%; 6: reduce to 50% of size |
| E3 | A/D Line Divergence | Index new high + A/D lower high | Reduce all positions 25% immediately |
| E4 | New Highs Collapse | Nifty500 new 52-week highs count | < 50 stocks: tighten stops to 15% trail; < 20: reduce all to 50% |
| E5 | Tiered Trailing Stop | Gain-based tiered trail (8% / breakeven / 15% / 10% / 8%+MA10) | Per-position cascading stops |

**Estimated effort: 5–7 days.** This is a complete rewrite of `engine/exits.py`.

---

### 🔴 Critical — New Systems Not Built At All

#### Fast Crash Detector (UC-03D)

Missing entirely. Independent of the regime engine (which is too slow — 3-day stability rule).

- **Trigger:** Index declines > 8% in any rolling 5-trading-day window
- **Response:** Sell 50% of every open position at next open; block all new entries
- **Reset:** When no 5-day window in last 10 days shows > 8% decline
- **Interaction with monster override:** Fast crash halves monster positions too. Monster override flag stays `True` — Phase 4 rules resume automatically after reset.
- **Validated:** March 2020 — Nifty lost ~12% in first 5 days; regime engine needed until day 12–16 to transition.

**Estimated effort: 0.5 days.**

#### Monster Stock Detection Layer (UC-04 Step 5)

Missing entirely. Based on Bessembinder 2018 (top 4% of stocks drive all net market wealth creation).

`calculate_monster_score()` — score 0 to 100:

| Criterion | Points |
|---|---|
| RS rank ≥ 90th percentile | +25 |
| Consolidation count ≥ 3 (repeated institutional accumulation) | +20 |
| Momentum quality ≥ 0.70 (70%+ of weekly closes positive) | +20 |
| Sector rank = #1 | +15 |
| Sustained EPS acceleration 4+ consecutive quarters | +10 |
| Base depth contracting each successive base | +10 |
| Sector outperformance ≥ 2× over prior 6 months | +10 |
| **Max** | **100** |

**Activation:** Score ≥ 80 AND gain ≥ 40% → override to Phase 4 exit rules regardless of actual gain phase.
Gain < 40%: score is tracked and displayed but does not change exit phase (prevents premature Phase 4 on unproven positions).

**Estimated effort: 2–3 days.**

#### Bull Market Entry Protocol (UC-03C)

Missing entirely. Structured 4-phase re-entry after Bear regime. Prevents capital deployment into failed bear rallies.

| Phase | Trigger | Action |
|---|---|---|
| B1 — Capitulation | Panic volume spike >2× 20-day avg on Nifty500 AND A/D higher low while price lower low | WATCH mode — zero capital |
| B2 — Breadth Thrust | Single day: 90%+ of advancing stocks' volume > 90% of total Nifty500 volume | Deploy 25% capital |
| B3 — A/D Confirmation | A/D line makes higher high than at capitulation bottom | Deploy additional 25% |
| B4 — New Highs Expand | Nifty500 new 52-week highs > 100 stocks/week for 2+ consecutive weeks | Full deployment per regime allocation |

**Estimated effort: 1–2 days.**

#### Turnaround Watch (v16 new — UC-04 Step 0B)

Missing entirely. Fires 1–3 quarters before the EPS hard block clears on genuine business turnarounds.

Conditions (all must be true):
1. EPS was negative in ≥ 2 of last 8 quarters (genuine loss phase)
2. EPS improving monotonically for last 4 quarters
3. Most recent quarter EPS > 0 (first positive quarter)
4. Revenue growing > 10% YoY (real recovery, not cost-cutting)
5. EPS block still active (< 2 of last 4 quarters positive)

Hard block suppression: If pledge > threshold, SEBI fine active, business pivots ≥ 3, or OCF negative 3+ of 4 quarters → suppress from dashboard (prevents psychological pressure to override hard blocks).

**Output:** Dashboard panel + WhatsApp alert to Mohit. New `turnaround_watch` table.
**Validated:** GE Vernova T&D — Turnaround Watch fires at ₹220 (June 2023); entry signal fires at ₹280–320 (Sep–Oct 2023). +₹60–70/share improvement.

**Estimated effort: 1–2 days.**

#### Correlation-Aware Position Sizing (UC-07 Adjustment 3)

Missing entirely.

- Corr > 0.85 with any existing holding → 50% size reduction
- Corr > 0.70 with any existing holding → 25% size reduction
- Measured on 60-day daily returns; minimum 30 overlapping days
- Logged as `correlation_adj_applied` on the position

**Rationale:** Momentum portfolios cluster in leading sectors. Intra-portfolio correlations spike to 0.80–0.95 during crashes. Portfolio heat doesn't capture this — a 15-stock portfolio can behave like 3–4 concentrated positions.

**Estimated effort: 1 day.**

---

### 🟡 Important — Hard Block Expansion

Current: 4 junk filters. v16 requires **8 hard blocks**:

| Hard Block | Current? | Notes |
|---|---|---|
| EPS: 2+ positive of last 4 quarters | ✅ | Unchanged |
| Market cap ₹1,000–₹30,000cr + ADV ≥ ₹15cr | ✅ | Note: v16 audited ₹15cr as correct default (was ₹10cr in earlier drafts) |
| ASM/ESM surveillance | ✅ | Unchanged |
| OCF negative in 3 of last 4 quarters | ❌ | New — `ocf_cr` field from Screener.in |
| Promoter pledge > 20% (operational) or > 50% (infra) | ❌ | New — infra exception: D/E falling AND revenue > 30% growth |
| SEBI price manipulation fine in last 24 months | ❌ | New — needs data source |
| IPO listed < 200 trading days | ❌ | New — straightforward, use listing date |
| 3+ business pivot / object clause changes in 5 years | ❌ | New — needs data source |

**Estimated effort: 2–3 days** (data sourcing for SEBI fines and business pivots is the bottleneck).

---

### 🟡 Important — Position Sizing: 3 Missing Adjustments

| Adjustment | Current? |
|---|---|
| Base 2% risk rule | ✅ |
| Portfolio heat cap (flat) | ✅ |
| Sector concentration cap | ✅ |
| **Regime-dependent portfolio heat** (6% / 5% / 4% / 2% / 0%) | ❌ — current uses flat cap |
| Beta > 2.5 → 40% size reduction | ❌ |
| Thin float (promoter > 75%, non-PSU) → 40% reduction + require confirmed bulk deal | ❌ |
| Correlation-aware sizing | ❌ — see above |

**Estimated effort: 1–2 days.**

---

### 🟡 Important — Fundamental Bonus Expansion

Current range: `-5 to +20`. v16 range: `-20 to +30`.

#### New bonus signals

| Signal | Points | Current? |
|---|---|---|
| PEAD / SUE proxy (eps_growth_yoy > 50% in last 60 days) | +10 | ❌ |
| PEAD / SUE proxy (eps_growth_yoy > 25% in last 60 days) | +6 | ❌ |
| Market cap band crossing trigger (entered ₹1k–30k band ≤ 60 days ago) | +6 | ❌ |
| Promoter buying open market (last 2 quarters) | +8 | ❌ |
| Low D/E (< 1.5, non-financial) | +2 | ❌ |
| Revenue growth vs sector average (relative, not absolute) | +4/+6/+10 | ❌ Changed — was absolute threshold |

#### New penalty signals

| Signal | Points | Current? |
|---|---|---|
| Promoter selling (last 2 quarters) | −8 | ❌ |
| SEBI price investigation active | −10 | ❌ |
| LODR fine in last 12 months | −3 | ❌ |
| Debtors days > 180 | −5 | ❌ |
| Debtors days > 120 | −3 | ❌ |
| OCF quality (OCF/net profit < 0.4 for 2 consecutive quarters) | −5 | ❌ |

Note: `check_promoter_buying()` and `check_promoter_selling()` require shareholding pattern history — use existing `shareholding_pattern` table.

**Estimated effort: 2–3 days.**

---

### 🟢 Minor — Data & Schema Changes

#### New tables required

| Table | Purpose |
|---|---|
| `turnaround_watch` | Turnaround Watch entries + suppression log |
| `sector_rankings` | Daily sector rank by median 3m momentum |
| `data_quality_alerts` | NSE/BSE price divergence, missing Screener fields |
| `pipeline_log` | Step-by-step checkpoint for recovery (UC-37) |
| `blocked_order_attempts` | Immutable SEBI audit trail for blocked orders |

#### Schema changes to existing tables

| Table | Column | Purpose |
|---|---|---|
| `price_data` | `exchange VARCHAR(5)` | BSE expansion readiness (populate `'NSE'` now) |
| `stocks` | `bse_code`, `industry` | BSE cross-reference + NSE industry classification |
| `open_positions` | `monster_score`, `monster_override_active`, `rs_below_floor_weeks`, `entry_adv`, `correlation_adj_applied` | v16 exit engine fields |
| `regime_history` | `fast_crash_fired`, `fast_crash_active` | Fast crash detector state |
| `fundamentals` | `ocf_cr`, `other_income_cr`, `trade_receivables_days`, `is_financial`, `sebi_fine_last_24m`, `lodr_fine_last_12m`, `sebi_investigation_active` | New hard block + penalty fields |

#### Data source additions

- **BSE daily bhav copy** — cross-validation only (`cross_check_bse_nse()`); divergence > 0.5% logged as data quality alert; does not block pipeline
- **NSE FII breach/caution list** — needed for smart institutional flow signal (FII buying legally blocked on breach list stocks)
- **Screener.in fallback handling** — formalize: CRITICAL fields (eps, ocf, pledge) → missing = exclude + WhatsApp alert; bonus fields → missing = 0 (no block)

**Estimated effort: 2–3 days.**

---

## Later Phases — Do Not Build Yet

These should only be built after paper trading is running for 6 months.

| Use Case | Phase | Trigger |
|---|---|---|
| UC-18/19: Daily + Weekly reports | Phase 1 | Build after signal engine is stable |
| UC-20/21: Client-facing reports | Phase 2 | After SEBI RA registration |
| UC-23–30: Full compliance stack | Phase 2 | After SEBI RA registration |
| UC-34/35: Zerodha Kite Connect OMS | Phase 3 | At go-live (Week 43) |
| UC-36/37: Pipeline monitoring + checkpoint recovery | Phase 1 | Low priority; build before go-live |
| UC-31–33: NAV/fee engine | Phase 5 | After AIF/PMS licence |
| UC-24: Client portal (SaaS) | Phase 4 | After 500+ subscribers |

---

## Total Effort Estimate

| Area | Days |
|---|---|
| Exit engine complete rewrite (4-phase + cascade) | 5–7 |
| Fast crash detector | 0.5 |
| Bull market entry protocol (UC-03C) | 1–2 |
| Monster stock detection layer | 2–3 |
| Turnaround Watch | 1–2 |
| New hard blocks (pledge, SEBI, OCF, IPO age, pivot) | 2–3 |
| Position sizing additions (regime heat, beta, thin float, correlation) | 1–2 |
| Fundamental bonus/penalty expansion | 2–3 |
| Schema migrations + new tables | 2 |
| Data sources (BSE cross-check, FII breach list, Screener fallback) | 1–2 |
| **Phase 1 total** | **~18–27 developer days** |
| Phase 2 — compliance stack | ~10–15 |
| Phase 3+ — OMS, monitoring | ~15–20 |

---

## Recommended Build Order

1. **Exit engine redesign + fast crash detector** — highest alpha impact, Force Motors 8.8x is the proof
2. **Hard blocks expansion** — data quality gate, must be correct before backtest
3. **Monster stock detection** — lets Phase 4 exits fire correctly
4. **Position sizing additions** — regime heat + correlation adjustment
5. **Fundamental bonus expansion** — incremental scoring improvements
6. **Turnaround Watch** — nice-to-have, low operational complexity
7. **Data & schema changes** — run in parallel with above

---

## Key v16 Operational Decisions (not implementation — for Mohit)

| Decision | v7 | v16 |
|---|---|---|
| Backtest period | 2015–2024 (all in-sample) | 2010–2022 (OOS 2023–2024 locked) |
| Go-live capital | 25% immediately | 10% → 25% after 3 months live validation |
| Paper trading duration | 3 months | **6 months minimum** (120 trading days) |
| Liquidity threshold | ₹15cr (locked) | ₹15cr (default, audit-confirmed) |
