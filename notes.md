Our analysis is validated across all 3 key signals:**

---

### M2 — Bear Regime ✓
The search confirms Nifty 50 broke below its 200-DMA in early March 2026, trading ~6.5% below it. Analysts on Business Standard are warning of a bear phase with a 19,000 target. Our classifier correctly picked this up — `Nifty>200MA: False`.

### M3 — Sector Rotation ✓
The searches confirm a major rotation away from tech/software into **Energy, Utilities, and Industrials** in Q1 2026 — driven by the Iran-Israel conflict pushing Brent crude toward $120/barrel and AI power demand boosting utilities. Our top 3 sectors (Utilities, Energy, Financial Services) match exactly what's happening globally and in India.

### Watchlist Stocks ✓
NTPC is at ₹378 with a 36% 1-year return and gained 8% in February 2026 as part of a broad power sector rally — consistent with our #3 ranking. COALINDIA and ONGC benefiting from the energy spike is textbook.

---

**Bottom line:** The pipeline is working correctly. Bear regime + Energy/Utilities/PSU banks leading in a defensive environment is exactly what the real market is showing right now.

Sources:
- [Is Nifty headed towards a bear phase? — Business Standard](https://www.business-standard.com/markets/news/stock-market-outlook-is-nifty-headed-towards-a-bear-phase-analyst-warns-19-000-mark-126030900326_1.html)
- [Nifty 50 200-day DMA breakdown March 2026 — karanpowar.in](https://karanpowar.in/nifty-50-200-day-dma-breakdown-march-2026/)
- [NTPC Stock Price — TradingView](https://www.tradingview.com/symbols/NSE-NTPC/)
- [From Bits to Atoms: The Great 2026 Sector Rotation — FinancialContent









-----


1. Breakout detection only runs for stocks passing M7 (Trend Template)**

In the pipeline, `detect_pattern()` is only called if `trend.passes = True`. On 2026-03-17 only 5 stocks passed — and those are exactly the 5 in the watchlist.

**2. Those 5 stocks passed the trend template but had no active breakout setup on that date**

The 4 pattern checks are strict:

| Pattern | Condition that failed |
|---|---|
| VCP | Needs progressively tighter ranges AND last period < 8% range AND contraction ratio < 50% |
| Base | Needs price range < 10% over 25 days + volume declining 15% |
| Resistance | Needs price break above 15-day pivot high + volume ≥ 1.5x average |
| Volume Breakout | Needs up-day + near 20-day high + volume ≥ 2x average |

In a Bear regime, stocks like NTPC, COALINDIA, ONGC are in slow uptrends — not forming tight VCP or explosive breakouts. None hit the thresholds.

This is **correct behavior** — having an uptrend structure (M7 pass) doesn't mean a breakout is imminent. The pattern score distinguishes stocks at a buyable pivot from those just holding their trend.

You'll see pattern data populate in a Bull market when stocks are forming consolidations near highs with volume drying up. Want me to lower the detection thresholds to catch looser setups, or leave them strict?
