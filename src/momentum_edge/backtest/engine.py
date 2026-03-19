"""
Backtesting engine for MomentumEdge v7.

Simulates the daily pipeline over historical data:
- Loads all price data upfront from DB
- Iterates day-by-day, computing indicators and signals
- Tracks portfolio: cash, positions, equity curve
- Enforces realistic execution: next-day open, slippage, costs

Adapted from quant-research POC backtester.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

import numpy as np
import pandas as pd
from loguru import logger
from sqlalchemy import text
from sqlalchemy.orm import Session

from momentum_edge.db.models import BacktestResult, PerformanceLog, Stock

# ---------------------------------------------------------------------------
# Transaction cost model (v7 spec)
# ---------------------------------------------------------------------------

SLIPPAGE_ENTRY_PCT = 0.005  # +0.5% on entry
SLIPPAGE_EXIT_PCT = 0.005  # -0.5% on exit
BROKERAGE_PCT = 0.001  # 0.1% per side
STT_SELL_PCT = 0.001  # 0.1% on sell
EXCHANGE_PCT = 0.0005  # 0.05% per side
# Total round trip: ~0.4%


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass
class BacktestConfig:
    """Configuration for a backtest run."""

    start_date: date
    end_date: date
    initial_capital: float = 1_000_000
    max_positions: int = 15
    risk_per_trade_pct: float = 2.0
    max_position_pct: float = 0.20
    max_portfolio_heat_pct: float = 0.06
    max_sector_concentration_pct: float = 0.30
    # v7 momentum weights (tuned by Test 1)
    mom_weight_12_1: float = 0.40
    mom_weight_6m: float = 0.35
    mom_weight_3m: float = 0.25
    # Strategy toggles (for A/B testing)
    use_trend_template: bool = True
    use_fundamental_bonus: bool = True
    use_vol_scaling: bool = True
    use_regime_filter: bool = True


# ---------------------------------------------------------------------------
# Trade record
# ---------------------------------------------------------------------------


@dataclass
class TradeRecord:
    """Record of a completed trade."""

    symbol: str
    stock_id: int
    entry_date: date
    exit_date: date
    entry_price: float
    exit_price: float
    shares: int
    pnl: float  # absolute P&L after costs
    pnl_pct: float
    exit_reason: str
    holding_days: int
    max_gain_pct: float  # MFE
    max_loss_pct: float  # MAE
    regime_at_entry: str
    sector: str


# ---------------------------------------------------------------------------
# Backtester
# ---------------------------------------------------------------------------


class Backtester:
    """
    Historical backtesting engine for MomentumEdge v7.

    Usage:
        config = BacktestConfig(start_date=date(2015,1,1), end_date=date(2024,12,31))
        bt = Backtester(db, config)
        bt.prepare_data()
        bt.run()
        metrics = bt.compute_metrics()
    """

    def __init__(self, db: Session, config: BacktestConfig):
        self.db = db
        self.config = config
        self.cash: float = config.initial_capital
        self.positions: list[dict] = []  # open positions
        self.trades: list[TradeRecord] = []  # completed trades
        self.equity_curve: list[dict] = []  # daily snapshots
        self.pending_entries: list[dict] = []  # signals awaiting next-day entry

        # Pre-loaded data (populated by prepare_data)
        self._prices: dict[int, pd.DataFrame] = {}  # stock_id -> OHLCV df
        self._stock_meta: dict[int, dict] = {}  # stock_id -> {symbol, sector}
        self._nifty: pd.DataFrame = pd.DataFrame()
        self._trading_days: list[date] = []

    # ------------------------------------------------------------------
    # Data preparation
    # ------------------------------------------------------------------

    def prepare_data(self) -> None:
        """
        Load all historical data from DB into memory.
        - eod_prices (adj_close, open, high, low, close, volume) for all active stocks
        - Group by stock_id as dict[int, pd.DataFrame]
        - Load Nifty 50 index
        - Only load data within [start_date - 252 days buffer, end_date]
        """
        buffer_start = self.config.start_date - timedelta(days=400)  # ~252 trading days
        end = self.config.end_date

        logger.info(
            "[Backtest] Loading price data from {} to {} (buffer from {})",
            self.config.start_date,
            end,
            buffer_start,
        )

        # --- Load stock metadata ---
        stocks = self.db.execute(
            text("""
                SELECT id, symbol, sector
                FROM stocks
                WHERE is_active = true
            """)
        ).fetchall()

        for row in stocks:
            self._stock_meta[row[0]] = {"symbol": row[1], "sector": row[2] or "Unknown"}

        stock_ids = list(self._stock_meta.keys())
        logger.info("[Backtest] {} active stocks loaded", len(stock_ids))

        # --- Bulk load all EOD prices ---
        rows = self.db.execute(
            text("""
                SELECT stock_id, date, open, high, low, close, adj_close, volume
                FROM eod_prices
                WHERE date >= :start AND date <= :end
                ORDER BY stock_id, date
            """),
            {"start": buffer_start, "end": end},
        ).fetchall()

        if not rows:
            logger.error("[Backtest] No price data found in date range")
            return

        # Build DataFrame and group by stock_id
        all_prices = pd.DataFrame(
            rows,
            columns=["stock_id", "date", "open", "high", "low", "close", "adj_close", "volume"],
        )
        # Use adj_close; fall back to close if null
        all_prices["adj_close"] = all_prices["adj_close"].fillna(all_prices["close"])

        for stock_id, group in all_prices.groupby("stock_id"):
            df = group.copy()
            df = df.sort_values("date").reset_index(drop=True)
            df["date"] = pd.to_datetime(df["date"]).dt.date
            if len(df) >= 200:  # need enough history for indicators
                self._prices[stock_id] = df

        logger.info(
            "[Backtest] Price data loaded for {} stocks ({} rows total)",
            len(self._prices),
            len(all_prices),
        )

        # --- Load Nifty 50 index data ---
        nifty_rows = self.db.execute(
            text("""
                SELECT e.date, e.open, e.high, e.low, e.close, e.adj_close
                FROM eod_prices e
                JOIN stocks s ON s.id = e.stock_id
                WHERE s.symbol IN ('NIFTY 50', 'NIFTY50', '^NSEI')
                  AND e.date >= :start AND e.date <= :end
                ORDER BY e.date
            """),
            {"start": buffer_start, "end": end},
        ).fetchall()

        if nifty_rows:
            self._nifty = pd.DataFrame(
                nifty_rows,
                columns=["date", "open", "high", "low", "close", "adj_close"],
            )
            self._nifty["adj_close"] = self._nifty["adj_close"].fillna(self._nifty["close"])
            self._nifty["date"] = pd.to_datetime(self._nifty["date"]).dt.date
            self._nifty = self._nifty.sort_values("date").reset_index(drop=True)
            logger.info("[Backtest] Nifty 50 index: {} rows", len(self._nifty))
        else:
            logger.warning("[Backtest] No Nifty 50 index data found — regime detection will use fallback")

        # --- Build trading day calendar from actual price data ---
        all_dates = set()
        for df in self._prices.values():
            all_dates.update(df["date"].tolist())
        self._trading_days = sorted(
            d for d in all_dates
            if self.config.start_date <= d <= self.config.end_date
        )

        logger.info(
            "[Backtest] Trading calendar: {} days ({} to {})",
            len(self._trading_days),
            self._trading_days[0] if self._trading_days else "N/A",
            self._trading_days[-1] if self._trading_days else "N/A",
        )

    # ------------------------------------------------------------------
    # Main simulation loop
    # ------------------------------------------------------------------

    def run(self) -> None:
        """
        Main simulation loop — iterate over each trading day.

        For each day:
        1. Process pending entries (buy at today's open with slippage)
        2. Update market values of open positions
        3. Check exit signals for all open positions
        4. Compute indicators for the universe (using data up to today only)
        5. Compute regime, rank stocks, apply filters
        6. Generate new entry signals -> add to pending_entries (executed next day)
        7. Record daily equity snapshot
        """
        if not self._trading_days:
            logger.error("[Backtest] No trading days — call prepare_data() first")
            return

        logger.info(
            "[Backtest] Starting simulation: {} days, capital={:,.0f}",
            len(self._trading_days),
            self.config.initial_capital,
        )

        for day_idx, current_date in enumerate(self._trading_days):
            # 1. Process pending entries — buy at today's open with slippage
            self._process_pending_entries(current_date)

            # 2. Check exits for open positions
            self._check_exits(current_date)

            # 3. Compute regime (simplified — MA200 of index + breadth)
            regime = self._compute_regime(current_date)

            # 4. Rank universe and generate new signals (no look-ahead)
            if self.config.use_regime_filter and regime in ("Full Bear",):
                # No new entries in Full Bear
                pass
            elif len(self.positions) < self.config.max_positions:
                self._generate_signals(current_date, regime)

            # 5. Record daily equity snapshot
            equity = self._compute_equity(current_date)
            self.equity_curve.append({
                "date": current_date,
                "cash": self.cash,
                "market_value": equity - self.cash,
                "equity": equity,
                "positions_count": len(self.positions),
                "regime": regime,
            })

            if day_idx % 252 == 0:
                logger.info(
                    "[Backtest] {} | Equity: {:,.0f} | Positions: {} | Regime: {}",
                    current_date,
                    equity,
                    len(self.positions),
                    regime,
                )

        # Close any remaining positions at the last day's close
        self._close_all_positions(self._trading_days[-1], "backtest_end")

        logger.info(
            "[Backtest] Simulation complete: {} trades, final equity {:,.0f}",
            len(self.trades),
            self.equity_curve[-1]["equity"] if self.equity_curve else 0,
        )

    # ------------------------------------------------------------------
    # Transaction cost helpers
    # ------------------------------------------------------------------

    def _apply_entry_cost(self, price: float) -> float:
        """Apply slippage + brokerage to entry price."""
        return price * (1 + SLIPPAGE_ENTRY_PCT + BROKERAGE_PCT + EXCHANGE_PCT)

    def _apply_exit_cost(self, price: float) -> float:
        """Apply slippage + brokerage + STT to exit price."""
        return price * (1 - SLIPPAGE_EXIT_PCT - BROKERAGE_PCT - STT_SELL_PCT - EXCHANGE_PCT)

    # ------------------------------------------------------------------
    # Price helpers (no look-ahead)
    # ------------------------------------------------------------------

    def _get_price_row(self, stock_id: int, target_date: date) -> dict | None:
        """Get a single day's OHLCV for a stock. Returns None if no data."""
        df = self._prices.get(stock_id)
        if df is None:
            return None
        mask = df["date"] == target_date
        if not mask.any():
            return None
        row = df.loc[mask].iloc[0]
        return {
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
            "adj_close": float(row["adj_close"]),
            "volume": int(row["volume"]),
        }

    def _get_price_history(self, stock_id: int, up_to_date: date) -> pd.DataFrame:
        """
        Get price history up to and including target_date.
        No future data leakage — uses iloc slicing on the pre-sorted DataFrame.
        """
        df = self._prices.get(stock_id)
        if df is None:
            return pd.DataFrame()
        mask = df["date"] <= up_to_date
        return df.loc[mask].copy()

    # ------------------------------------------------------------------
    # Indicator computation (inline, no look-ahead)
    # ------------------------------------------------------------------

    def _compute_indicators(self, stock_id: int, up_to_date: date) -> dict | None:
        """
        Compute technical indicators for a stock using data up to (not beyond)
        the given date. Returns dict with ma50, ma150, ma200, ma200_slope,
        high_52w, low_52w, atr, mom_3m, mom_6m, mom_12_1, or None if
        insufficient data.
        """
        hist = self._get_price_history(stock_id, up_to_date)
        if len(hist) < 252:
            return None

        adj = hist["adj_close"].values
        high = hist["high"].values
        low = hist["low"].values
        close = hist["close"].values
        current = adj[-1]

        ma50 = float(np.mean(adj[-50:]))
        ma150 = float(np.mean(adj[-150:]))
        ma200 = float(np.mean(adj[-200:]))

        # MA200 slope: compare current MA200 to MA200 from 20 days ago
        if len(adj) >= 220:
            ma200_20d_ago = float(np.mean(adj[-220:-20]))
            ma200_slope = ma200 - ma200_20d_ago
        else:
            ma200_slope = 0.0

        # 52-week extremes
        high_52w = float(np.max(high[-252:]))
        low_52w = float(np.min(low[-252:]))

        # ATR (20-day)
        if len(hist) >= 21:
            tr_values = []
            for i in range(-20, 0):
                h = high[i]
                l = low[i]
                prev_c = close[i - 1]
                tr = max(h - l, abs(h - prev_c), abs(l - prev_c))
                tr_values.append(tr)
            atr = float(np.mean(tr_values))
        else:
            atr = 0.0

        # Momentum factors
        mom_12_1 = (adj[-21] / adj[-252] - 1) * 100 if len(adj) >= 252 else 0.0
        mom_6m = (current / adj[-126] - 1) * 100 if len(adj) >= 126 else 0.0
        mom_3m = (current / adj[-63] - 1) * 100 if len(adj) >= 63 else 0.0

        # 10-day high (for trailing stops)
        high_10d = float(np.max(high[-10:])) if len(high) >= 10 else float(current)

        # Volume ratio (20-day average vs 50-day average)
        vol = hist["volume"].values
        vol_ratio = (
            float(np.mean(vol[-20:])) / float(np.mean(vol[-50:]))
            if len(vol) >= 50 and np.mean(vol[-50:]) > 0
            else 1.0
        )

        return {
            "adj_close": float(current),
            "ma50": ma50,
            "ma150": ma150,
            "ma200": ma200,
            "ma200_slope": ma200_slope,
            "high_52w": high_52w,
            "low_52w": low_52w,
            "atr": atr,
            "mom_12_1": float(mom_12_1),
            "mom_6m": float(mom_6m),
            "mom_3m": float(mom_3m),
            "high_10d": high_10d,
            "vol_ratio": vol_ratio,
        }

    def _passes_trend_template(self, ind: dict) -> bool:
        """
        Simplified Minervini 8-condition trend template check.
        Uses pre-computed indicators dict (no DB query).
        """
        if not self.config.use_trend_template:
            return True

        adj = ind["adj_close"]
        c1 = adj > ind["ma50"]
        c2 = adj > ind["ma150"]
        c3 = adj > ind["ma200"]
        c4 = ind["ma50"] > ind["ma150"]
        c5 = ind["ma150"] > ind["ma200"]
        c6 = ind["ma200_slope"] > 0
        c7 = adj >= ind["high_52w"] * 0.80
        # c8 (20 consecutive days above MA200) — simplified: just check current
        c8 = adj > ind["ma200"]

        return all([c1, c2, c3, c4, c5, c6, c7, c8])

    def _compute_momentum_score(self, ind: dict) -> float:
        """
        Compute weighted momentum score using v7 weights.
        Returns raw score (higher = better momentum).
        """
        cfg = self.config
        score = (
            cfg.mom_weight_12_1 * ind["mom_12_1"]
            + cfg.mom_weight_6m * ind["mom_6m"]
            + cfg.mom_weight_3m * ind["mom_3m"]
        )
        return score

    # ------------------------------------------------------------------
    # Regime detection (simplified for backtest speed)
    # ------------------------------------------------------------------

    def _compute_regime(self, current_date: date) -> str:
        """
        Simplified regime detection using Nifty MA200 + breadth.
        Does not use the full M2 module (too many DB queries).

        Returns one of: 'Strong Bull', 'Bull', 'Weak', 'Bear', 'Full Bear'
        """
        # --- Nifty signals ---
        if self._nifty.empty:
            return "Weak"

        nifty_hist = self._nifty[self._nifty["date"] <= current_date]
        if len(nifty_hist) < 200:
            return "Weak"

        nifty_close = float(nifty_hist["adj_close"].iloc[-1])
        nifty_ma200 = float(nifty_hist["adj_close"].tail(200).mean())

        # S1: Nifty above MA200
        s1 = 1.0 if nifty_close > nifty_ma200 else 0.0

        # S2: MA200 slope rising (vs 20 days ago)
        if len(nifty_hist) >= 220:
            nifty_ma200_20d_ago = float(nifty_hist["adj_close"].iloc[-220:-20].tail(200).mean())
            s2 = 1.0 if nifty_ma200 > nifty_ma200_20d_ago else 0.0
        else:
            s2 = 0.0

        # S3: Breadth — % of stocks with adj_close > MA50
        above_50 = 0
        total_checked = 0
        for stock_id, df in self._prices.items():
            hist = df[df["date"] <= current_date]
            if len(hist) < 50:
                continue
            adj = hist["adj_close"].values
            if adj[-1] > np.mean(adj[-50:]):
                above_50 += 1
            total_checked += 1

        breadth_pct = (above_50 / total_checked * 100) if total_checked > 0 else 50.0
        if breadth_pct > 60:
            s3 = 1.0
        elif breadth_pct >= 40:
            s3 = 0.5
        else:
            s3 = 0.0

        # S5: Extension from MA200
        extension_pct = ((nifty_close - nifty_ma200) / nifty_ma200) * 100
        if abs(extension_pct) <= 15:
            s5 = 1.0
        elif abs(extension_pct) <= 25:
            s5 = 0.5
        else:
            s5 = 0.0

        # S6: 12-minus-1 month return
        if len(nifty_hist) >= 252:
            close_12m = float(nifty_hist["adj_close"].iloc[-252])
            close_1m = float(nifty_hist["adj_close"].iloc[-21])
            s6 = 1.0 if (close_1m / close_12m - 1) > 0 else 0.0
        else:
            s6 = 0.0

        # S4 simplified: use breadth as proxy (skip 52w high/low query)
        s4 = 0.5

        score = s1 + s2 + s3 + s4 + s5 + s6

        if score >= 5.0:
            return "Strong Bull"
        elif score >= 4.0:
            return "Bull"
        elif score >= 2.5:
            return "Weak"
        elif score >= 1.0:
            return "Bear"
        else:
            return "Full Bear"

    # ------------------------------------------------------------------
    # Position sizing
    # ------------------------------------------------------------------

    def _calculate_position_size(
        self,
        entry_price: float,
        stop_loss: float,
        regime: str,
    ) -> int | None:
        """
        Calculate number of shares using the 2% risk rule with regime adjustment.
        Returns share count or None if position is invalid.
        """
        from momentum_edge.engine.position_sizing import (
            REGIME_RISK_MAP,
            POSITION_FLOOR_PCT,
            POSITION_CEILING_PCT,
        )

        risk_per_share = entry_price - stop_loss
        if risk_per_share <= 0:
            return None

        equity = self._compute_equity_fast()
        risk_pct = REGIME_RISK_MAP.get(regime, 0.5)
        if risk_pct <= 0:
            return None

        risk_amount = equity * (risk_pct / 100.0)
        shares = int(risk_amount / risk_per_share)

        if shares <= 0:
            return None

        position_value = shares * entry_price
        position_pct = (position_value / equity) * 100.0

        # Floor check
        if position_pct < POSITION_FLOOR_PCT:
            return None

        # Ceiling cap
        if position_pct > POSITION_CEILING_PCT:
            max_value = equity * (POSITION_CEILING_PCT / 100.0)
            shares = int(max_value / entry_price)

        # Cash check
        cost = shares * entry_price
        if cost > self.cash:
            shares = int(self.cash / entry_price)

        return shares if shares > 0 else None

    def _check_portfolio_heat(self, new_risk_amount: float) -> bool:
        """Check if adding a trade would exceed the max portfolio heat."""
        equity = self._compute_equity_fast()
        if equity <= 0:
            return False

        total_risk = new_risk_amount
        for pos in self.positions:
            risk_per_share = pos["entry_price"] - pos["stop_loss"]
            if risk_per_share > 0:
                total_risk += pos["shares"] * risk_per_share

        heat_pct = (total_risk / equity) * 100.0
        return heat_pct <= (self.config.max_portfolio_heat_pct * 100.0)

    def _check_sector_concentration(self, sector: str, new_value: float) -> bool:
        """Check if adding a position would breach sector concentration limit."""
        equity = self._compute_equity_fast()
        if equity <= 0:
            return False

        sector_value = new_value
        for pos in self.positions:
            if pos.get("sector") == sector:
                sector_value += pos["shares"] * pos["current_price"]

        sector_pct = sector_value / equity
        return sector_pct <= self.config.max_sector_concentration_pct

    # ------------------------------------------------------------------
    # Equity calculation
    # ------------------------------------------------------------------

    def _compute_equity(self, current_date: date) -> float:
        """Portfolio equity = cash + sum(position_shares * current adj_close)."""
        market_value = 0.0
        for pos in self.positions:
            price_row = self._get_price_row(pos["stock_id"], current_date)
            if price_row:
                pos["current_price"] = price_row["adj_close"]
                market_value += pos["shares"] * price_row["adj_close"]
            else:
                # Use last known price
                market_value += pos["shares"] * pos["current_price"]
        return self.cash + market_value

    def _compute_equity_fast(self) -> float:
        """Quick equity using cached current_price on positions."""
        market_value = sum(p["shares"] * p["current_price"] for p in self.positions)
        return self.cash + market_value

    # ------------------------------------------------------------------
    # Entry processing
    # ------------------------------------------------------------------

    def _process_pending_entries(self, current_date: date) -> None:
        """
        Execute pending entry signals at today's open with slippage.
        Entries were generated yesterday — this enforces next-day execution.
        """
        if not self.pending_entries:
            return

        executed = []
        for signal in self.pending_entries:
            stock_id = signal["stock_id"]
            price_row = self._get_price_row(stock_id, current_date)
            if price_row is None:
                continue  # stock not traded today

            raw_open = price_row["open"]
            fill_price = self._apply_entry_cost(raw_open)
            stop_loss = signal["stop_loss"]
            regime = signal["regime"]
            sector = signal.get("sector", "Unknown")

            # Position sizing
            shares = self._calculate_position_size(fill_price, stop_loss, regime)
            if shares is None:
                continue

            cost = shares * fill_price
            risk_amount = shares * (fill_price - stop_loss)

            # Portfolio heat check
            if not self._check_portfolio_heat(risk_amount):
                continue

            # Sector concentration check
            if not self._check_sector_concentration(sector, cost):
                continue

            # Max positions check
            if len(self.positions) >= self.config.max_positions:
                break

            # Cash check
            if cost > self.cash:
                continue

            # Execute entry
            self.cash -= cost
            position = {
                "stock_id": stock_id,
                "symbol": signal["symbol"],
                "sector": sector,
                "entry_date": current_date,
                "entry_price": fill_price,
                "current_price": fill_price,
                "shares": shares,
                "stop_loss": stop_loss,
                "current_stop": stop_loss,
                "regime_at_entry": regime,
                "max_price": fill_price,  # for MFE tracking
                "min_price": fill_price,  # for MAE tracking
            }
            self.positions.append(position)
            executed.append(signal)

            logger.debug(
                "[Backtest] BUY {} | {} shares @ {:.2f} | Stop {:.2f} | {}",
                signal["symbol"],
                shares,
                fill_price,
                stop_loss,
                current_date,
            )

        self.pending_entries.clear()

    # ------------------------------------------------------------------
    # Exit checks
    # ------------------------------------------------------------------

    def _check_exits(self, current_date: date) -> None:
        """
        Check all exit rules for open positions.
        Simplified version of the 9-rule exit engine for backtest speed.
        """
        to_close: list[tuple[int, str]] = []  # (position_index, reason)

        for idx, pos in enumerate(self.positions):
            stock_id = pos["stock_id"]
            price_row = self._get_price_row(stock_id, current_date)
            if price_row is None:
                continue

            adj_close = price_row["adj_close"]
            today_low = price_row["low"]
            today_high = price_row["high"]

            # Update MFE/MAE tracking
            pos["current_price"] = adj_close
            pos["max_price"] = max(pos["max_price"], today_high)
            pos["min_price"] = min(pos["min_price"], today_low)

            entry_price = pos["entry_price"]
            gain_pct = ((adj_close - entry_price) / entry_price) * 100
            holding_days = (current_date - pos["entry_date"]).days

            # --- Rule 1: Initial/current stop hit ---
            if today_low < pos["current_stop"]:
                to_close.append((idx, "stop_loss"))
                continue

            # --- Rule 2: MA200 breach ---
            ind = self._compute_indicators(stock_id, current_date)
            if ind and adj_close < ind["ma200"]:
                to_close.append((idx, "ma200_breach"))
                continue

            # --- Rule 7: Time stop (20 days, < 5% gain) ---
            if holding_days >= 20 and abs(gain_pct) < 5:
                to_close.append((idx, "time_stop"))
                continue

            # --- Rule 8: Climax exit (20%+ gain in < 15 days) ---
            if gain_pct >= 20 and holding_days < 15:
                # In backtest, simplify to full exit instead of 50% partial
                to_close.append((idx, "climax_top"))
                continue

            # --- Trailing stop management ---
            if ind:
                high_10d = ind["high_10d"]

                # Rule 6: gain >= 100% → trail 15% below 10d high
                if gain_pct >= 100:
                    new_stop = high_10d * 0.85
                    pos["current_stop"] = max(pos["current_stop"], new_stop)
                # Rule 5: gain >= 40% → trail 10% below 10d high
                elif gain_pct >= 40:
                    new_stop = high_10d * 0.90
                    pos["current_stop"] = max(pos["current_stop"], new_stop)
                # Rule 4: gain >= 20% → move stop to entry (breakeven)
                elif gain_pct >= 20:
                    pos["current_stop"] = max(pos["current_stop"], entry_price)

        # Execute exits (reverse order to avoid index shift issues)
        for idx, reason in sorted(to_close, key=lambda x: x[0], reverse=True):
            self._execute_exit(idx, current_date, reason)

    def _execute_exit(self, position_idx: int, exit_date: date, reason: str) -> None:
        """Close a position and record the trade."""
        pos = self.positions[position_idx]
        price_row = self._get_price_row(pos["stock_id"], exit_date)

        if price_row is None:
            # Use last known price
            raw_exit = pos["current_price"]
        else:
            raw_exit = price_row["adj_close"]

        exit_price = self._apply_exit_cost(raw_exit)
        entry_price = pos["entry_price"]
        shares = pos["shares"]

        proceeds = shares * exit_price
        cost_basis = shares * entry_price
        pnl = proceeds - cost_basis
        pnl_pct = ((exit_price / entry_price) - 1) * 100

        # MFE / MAE
        max_gain_pct = ((pos["max_price"] - entry_price) / entry_price) * 100
        max_loss_pct = ((pos["min_price"] - entry_price) / entry_price) * 100

        holding_days = (exit_date - pos["entry_date"]).days

        trade = TradeRecord(
            symbol=pos["symbol"],
            stock_id=pos["stock_id"],
            entry_date=pos["entry_date"],
            exit_date=exit_date,
            entry_price=entry_price,
            exit_price=exit_price,
            shares=shares,
            pnl=pnl,
            pnl_pct=pnl_pct,
            exit_reason=reason,
            holding_days=holding_days,
            max_gain_pct=max_gain_pct,
            max_loss_pct=max_loss_pct,
            regime_at_entry=pos["regime_at_entry"],
            sector=pos.get("sector", "Unknown"),
        )
        self.trades.append(trade)
        self.cash += proceeds

        logger.debug(
            "[Backtest] SELL {} | {} shares @ {:.2f} | PnL: {:+.0f} ({:+.1f}%) | {} | {}",
            pos["symbol"],
            shares,
            exit_price,
            pnl,
            pnl_pct,
            reason,
            exit_date,
        )

        self.positions.pop(position_idx)

    def _close_all_positions(self, close_date: date, reason: str) -> None:
        """Close all open positions (used at backtest end)."""
        while self.positions:
            self._execute_exit(0, close_date, reason)

    # ------------------------------------------------------------------
    # Signal generation
    # ------------------------------------------------------------------

    def _generate_signals(self, current_date: date, regime: str) -> None:
        """
        Rank the universe and generate entry signals for next-day execution.
        No look-ahead: only uses data up to current_date.
        """
        candidates: list[dict] = []
        existing_symbols = {p["symbol"] for p in self.positions}
        pending_symbols = {p["symbol"] for p in self.pending_entries}

        for stock_id, meta in self._stock_meta.items():
            if stock_id not in self._prices:
                continue
            if meta["symbol"] in existing_symbols or meta["symbol"] in pending_symbols:
                continue

            ind = self._compute_indicators(stock_id, current_date)
            if ind is None:
                continue

            # Hard filter: trend template
            if not self._passes_trend_template(ind):
                continue

            # Momentum score
            mom_score = self._compute_momentum_score(ind)

            # Vol scaling (optional)
            vol_scalar = 1.0
            if self.config.use_vol_scaling and ind["atr"] > 0:
                # Scale inversely with volatility: lower vol = larger position
                vol_pct = (ind["atr"] / ind["adj_close"]) * 100
                if vol_pct < 1.5:
                    vol_scalar = 1.2
                elif vol_pct > 4.0:
                    vol_scalar = 0.7
                else:
                    vol_scalar = 1.0

            # Stop loss: 2 * ATR below current price
            stop_loss = ind["adj_close"] - (2.0 * ind["atr"])

            candidates.append({
                "stock_id": stock_id,
                "symbol": meta["symbol"],
                "sector": meta["sector"],
                "mom_score": mom_score,
                "vol_scalar": vol_scalar,
                "adj_close": ind["adj_close"],
                "stop_loss": stop_loss,
                "atr": ind["atr"],
                "regime": regime,
            })

        # Rank by momentum score, take top candidates
        candidates.sort(key=lambda x: x["mom_score"], reverse=True)

        slots_available = self.config.max_positions - len(self.positions) - len(self.pending_entries)
        top_n = min(slots_available, 3)  # add at most 3 signals per day

        for cand in candidates[:top_n]:
            self.pending_entries.append(cand)

    # ------------------------------------------------------------------
    # Performance metrics
    # ------------------------------------------------------------------

    def compute_metrics(self) -> dict:
        """
        Compute all 14 required performance metrics from v7 spec.

        Returns dict with:
        1. cagr
        2. nifty_alpha (cagr - nifty_cagr)
        3. win_rate
        4. avg_win_pct
        5. avg_loss_pct
        6. win_loss_ratio (avg_win / abs(avg_loss))
        7. expectancy_pct
        8. max_drawdown
        9. sharpe_ratio
        10. calmar_ratio (cagr / abs(max_dd))
        11. regime_performance (dict of cagr per regime)
        12. avg_holding_days
        13. annual_returns (dict of year -> return)
        14. best_year, worst_year

        Also: total_trades, positive_expectancy, passes_gates (dict of bool per gate)
        """
        if not self.equity_curve:
            logger.warning("[Backtest] No equity curve data — cannot compute metrics")
            return {}

        eq_df = pd.DataFrame(self.equity_curve)
        eq_df["date"] = pd.to_datetime(eq_df["date"])
        eq_df = eq_df.set_index("date").sort_index()

        initial = self.config.initial_capital
        final = eq_df["equity"].iloc[-1]
        days = (eq_df.index[-1] - eq_df.index[0]).days

        # --- 1. CAGR ---
        total_return = final / initial - 1
        cagr = (1 + total_return) ** (365.25 / days) - 1 if days > 0 else 0.0

        # --- 2. Nifty CAGR & Alpha ---
        nifty_cagr = 0.0
        if not self._nifty.empty:
            nifty_start_mask = self._nifty["date"] >= self.config.start_date
            nifty_end_mask = self._nifty["date"] <= self.config.end_date
            nifty_period = self._nifty[nifty_start_mask & nifty_end_mask]
            if len(nifty_period) >= 2:
                nifty_start_price = float(nifty_period["adj_close"].iloc[0])
                nifty_end_price = float(nifty_period["adj_close"].iloc[-1])
                nifty_total = nifty_end_price / nifty_start_price - 1
                nifty_days = (nifty_period["date"].iloc[-1] - nifty_period["date"].iloc[0]).days
                nifty_cagr = (1 + nifty_total) ** (365.25 / nifty_days) - 1 if nifty_days > 0 else 0.0

        nifty_alpha = cagr - nifty_cagr

        # --- Trade stats ---
        if self.trades:
            trades_df = pd.DataFrame([
                {"pnl": t.pnl, "pnl_pct": t.pnl_pct, "holding_days": t.holding_days,
                 "regime_at_entry": t.regime_at_entry, "entry_date": t.entry_date,
                 "exit_date": t.exit_date}
                for t in self.trades
            ])

            wins = trades_df[trades_df["pnl"] > 0]
            losses = trades_df[trades_df["pnl"] <= 0]

            # 3. Win rate
            win_rate = len(wins) / len(trades_df) if len(trades_df) > 0 else 0.0

            # 4 & 5. Avg win/loss %
            avg_win_pct = float(wins["pnl_pct"].mean()) if len(wins) > 0 else 0.0
            avg_loss_pct = float(losses["pnl_pct"].mean()) if len(losses) > 0 else 0.0

            # 6. Win/loss ratio
            win_loss_ratio = (
                abs(avg_win_pct / avg_loss_pct) if avg_loss_pct != 0 else float("inf")
            )

            # 7. Expectancy
            expectancy_pct = (win_rate * avg_win_pct) + ((1 - win_rate) * avg_loss_pct)

            # 12. Avg holding days
            avg_holding_days = float(trades_df["holding_days"].mean())

            # 11. Regime performance
            regime_performance = {}
            for regime_name, group in trades_df.groupby("regime_at_entry"):
                regime_total_pnl_pct = group["pnl_pct"].sum()
                regime_performance[regime_name] = round(regime_total_pnl_pct, 2)

            total_trades = len(self.trades)
        else:
            win_rate = 0.0
            avg_win_pct = 0.0
            avg_loss_pct = 0.0
            win_loss_ratio = 0.0
            expectancy_pct = 0.0
            avg_holding_days = 0.0
            regime_performance = {}
            total_trades = 0

        # --- 8. Max drawdown ---
        rolling_max = eq_df["equity"].cummax()
        drawdown = (eq_df["equity"] / rolling_max) - 1
        max_drawdown = float(drawdown.min())

        # --- 9. Sharpe ratio ---
        daily_returns = eq_df["equity"].pct_change().dropna()
        if len(daily_returns) > 1 and daily_returns.std() != 0:
            sharpe_ratio = float(
                (daily_returns.mean() / daily_returns.std()) * np.sqrt(252)
            )
        else:
            sharpe_ratio = 0.0

        # --- 10. Calmar ratio ---
        calmar_ratio = abs(cagr / max_drawdown) if max_drawdown != 0 else 0.0

        # --- 13. Annual returns ---
        annual_returns: dict[str, float] = {}
        eq_df["year"] = eq_df.index.year
        for year, group in eq_df.groupby("year"):
            year_start = group["equity"].iloc[0]
            year_end = group["equity"].iloc[-1]
            year_return = (year_end / year_start - 1) * 100
            annual_returns[str(year)] = round(year_return, 2)

        # --- 14. Best/worst year ---
        if annual_returns:
            best_year = max(annual_returns, key=annual_returns.get)  # type: ignore[arg-type]
            worst_year = min(annual_returns, key=annual_returns.get)  # type: ignore[arg-type]
        else:
            best_year = "N/A"
            worst_year = "N/A"

        metrics = {
            "cagr": round(cagr * 100, 2),
            "nifty_cagr": round(nifty_cagr * 100, 2),
            "nifty_alpha": round(nifty_alpha * 100, 2),
            "win_rate": round(win_rate * 100, 2),
            "avg_win_pct": round(avg_win_pct, 2),
            "avg_loss_pct": round(avg_loss_pct, 2),
            "win_loss_ratio": round(win_loss_ratio, 2),
            "expectancy_pct": round(expectancy_pct, 2),
            "max_drawdown": round(max_drawdown * 100, 2),
            "sharpe_ratio": round(sharpe_ratio, 2),
            "calmar_ratio": round(calmar_ratio, 2),
            "regime_performance": regime_performance,
            "avg_holding_days": round(avg_holding_days, 1),
            "annual_returns": annual_returns,
            "best_year": best_year,
            "worst_year": worst_year,
            "total_trades": total_trades,
            "positive_expectancy": expectancy_pct > 0,
            "initial_capital": initial,
            "final_equity": round(final, 2),
            "total_return_pct": round(total_return * 100, 2),
        }

        # Gate checks
        metrics["passes_gates"] = self._check_gates(metrics)

        return metrics

    def _check_gates(self, metrics: dict) -> dict:
        """
        Check if the backtest passes all 6 hard gates from v7 spec:
        1. Positive expectancy
        2. Sharpe > 0.8
        3. Max drawdown < 25%
        4. CAGR > 15%
        5. Outperforms Nifty 50 by 5%+ CAGR
        6. Positive in at least 3 of 4 regime types
        """
        regime_perf = metrics.get("regime_performance", {})
        positive_regimes = sum(1 for v in regime_perf.values() if v > 0)

        gates = {
            "positive_expectancy": metrics.get("positive_expectancy", False),
            "sharpe_gt_0_8": metrics.get("sharpe_ratio", 0) > 0.8,
            "max_dd_lt_25": abs(metrics.get("max_drawdown", -100)) < 25,
            "cagr_gt_15": metrics.get("cagr", 0) > 15,
            "nifty_alpha_gt_5": metrics.get("nifty_alpha", 0) > 5,
            "regime_robustness": positive_regimes >= 3,
        }

        gates["all_passed"] = all(
            v for k, v in gates.items() if k != "all_passed"
        )

        return gates

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save_results(self, test_name: str) -> int:
        """
        Save backtest results to backtest_results table.
        Save individual trades to performance_log table.
        Returns backtest run ID.
        """
        metrics = self.compute_metrics()

        # --- Save summary to backtest_results ---
        params = {
            "initial_capital": self.config.initial_capital,
            "max_positions": self.config.max_positions,
            "risk_per_trade_pct": self.config.risk_per_trade_pct,
            "mom_weight_12_1": self.config.mom_weight_12_1,
            "mom_weight_6m": self.config.mom_weight_6m,
            "mom_weight_3m": self.config.mom_weight_3m,
            "use_trend_template": self.config.use_trend_template,
            "use_fundamental_bonus": self.config.use_fundamental_bonus,
            "use_vol_scaling": self.config.use_vol_scaling,
            "use_regime_filter": self.config.use_regime_filter,
        }

        result = BacktestResult(
            test_name=test_name,
            period_start=self.config.start_date,
            period_end=self.config.end_date,
            parameters=params,
            cagr=metrics.get("cagr"),
            nifty_alpha=metrics.get("nifty_alpha"),
            win_rate=metrics.get("win_rate"),
            avg_win=metrics.get("avg_win_pct"),
            avg_loss=metrics.get("avg_loss_pct"),
            expectancy_pct=metrics.get("expectancy_pct"),
            max_drawdown=metrics.get("max_drawdown"),
            sharpe_ratio=metrics.get("sharpe_ratio"),
            calmar_ratio=metrics.get("calmar_ratio"),
            total_trades=metrics.get("total_trades"),
            avg_holding_days=metrics.get("avg_holding_days"),
            annual_returns=metrics.get("annual_returns"),
            passed_gate=metrics.get("passes_gates", {}).get("all_passed", False),
            notes=f"Generated by Backtester v7. Gates: {metrics.get('passes_gates', {})}",
        )

        self.db.add(result)
        self.db.flush()  # get the ID
        run_id = result.id

        # --- Save individual trades to performance_log ---
        for trade in self.trades:
            log_entry = PerformanceLog(
                stock_id=trade.stock_id,
                entry_date=trade.entry_date,
                exit_date=trade.exit_date,
                entry_price=trade.entry_price,
                actual_fill=trade.entry_price,  # already includes slippage
                exit_price=trade.exit_price,
                pnl_pct=trade.pnl_pct,
                pnl_inr=trade.pnl,
                exit_reason=trade.exit_reason,
                holding_days=trade.holding_days,
                max_gain_pct=trade.max_gain_pct,
                max_loss_pct=trade.max_loss_pct,
                regime_at_entry=trade.regime_at_entry,
            )
            self.db.add(log_entry)

        self.db.commit()

        logger.info(
            "[Backtest] Results saved: run_id={}, test_name='{}', {} trades",
            run_id,
            test_name,
            len(self.trades),
        )

        return run_id
