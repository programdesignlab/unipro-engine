"""
Test runner — orchestrates the 10 structured backtests from v7 use case doc.

Each test varies one parameter while keeping others at default.
Results stored in backtest_results table for comparison.
"""

from datetime import date

from loguru import logger
from sqlalchemy.orm import Session

from momentum_edge.backtest.engine import Backtester, BacktestConfig


# ---------------------------------------------------------------------------
# Default config — shared baseline for all tests
# ---------------------------------------------------------------------------

DEFAULT_CONFIG = BacktestConfig(
    start_date=date(2015, 1, 1),
    end_date=date(2024, 12, 31),
    initial_capital=1_000_000,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _run_variant(
    db: Session,
    test_name: str,
    label: str,
    config: BacktestConfig,
) -> dict:
    """
    Run a single backtest variant and return metrics dict.

    Logs the result and tags it with test_name (e.g. "T1A") for storage.
    """
    logger.info("Running {} — {}", test_name, label)
    bt = Backtester(db, config)
    result = bt.run()
    metrics = result.compute_metrics()
    metrics["test_name"] = test_name
    metrics["label"] = label

    logger.info(
        "{} done: Sharpe={:.3f}, CAGR={:.2%}, MaxDD={:.2%}",
        test_name,
        metrics.get("sharpe_ratio", 0),
        metrics.get("cagr", 0),
        metrics.get("max_drawdown", 0),
    )
    return metrics


def _pick_winner(results: list[dict], metric: str = "sharpe_ratio") -> dict:
    """Pick the variant with the highest value for the given metric."""
    winner = max(results, key=lambda r: r.get(metric, float("-inf")))
    logger.info(
        "Winner: {} ({}) with {}={:.4f}",
        winner["test_name"], winner["label"], metric, winner.get(metric, 0),
    )
    return winner


# ---------------------------------------------------------------------------
# Test 1: Momentum Factor Weights
# ---------------------------------------------------------------------------


def run_test_1_momentum_weights(db: Session) -> list[dict]:
    """
    Test 1: Momentum Factor Weights
    1A: 3m alone (0/0/100)
    1B: 6m alone (0/100/0)
    1C: 12-1 alone (100/0/0)
    1D: Equal (33/33/33)
    1E: Default (40/35/25)
    1F: Default + vol scaling
    Gate: Best beats Nifty 50 Sharpe by 0.3+
    """
    variants = [
        ("T1A", "3m alone (0/0/100)", {"mom_weight_12m": 0, "mom_weight_6m": 0, "mom_weight_3m": 100}),
        ("T1B", "6m alone (0/100/0)", {"mom_weight_12m": 0, "mom_weight_6m": 100, "mom_weight_3m": 0}),
        ("T1C", "12-1 alone (100/0/0)", {"mom_weight_12m": 100, "mom_weight_6m": 0, "mom_weight_3m": 0}),
        ("T1D", "Equal (33/33/33)", {"mom_weight_12m": 33, "mom_weight_6m": 33, "mom_weight_3m": 33}),
        ("T1E", "Default (40/35/25)", {"mom_weight_12m": 40, "mom_weight_6m": 35, "mom_weight_3m": 25}),
        ("T1F", "Default + vol scaling", {"mom_weight_12m": 40, "mom_weight_6m": 35, "mom_weight_3m": 25, "vol_scaling": True}),
    ]

    results = []
    for test_name, label, overrides in variants:
        config = BacktestConfig(
            start_date=DEFAULT_CONFIG.start_date,
            end_date=DEFAULT_CONFIG.end_date,
            initial_capital=DEFAULT_CONFIG.initial_capital,
            **overrides,
        )
        results.append(_run_variant(db, test_name, label, config))

    _pick_winner(results)
    return results


# ---------------------------------------------------------------------------
# Test 2: Market Cap Band
# ---------------------------------------------------------------------------


def run_test_2_market_cap(db: Session) -> list[dict]:
    """
    Test 2: Market Cap Band
    2A: All NSE | 2B: 500-30K | 2C: 1K-30K | 2D: 2K-30K | 2E: 2K-20K | 2F: 3K-25K
    Gate: Chosen band beats baseline on Sharpe AND drawdown
    """
    variants = [
        ("T2A", "All NSE (no filter)", {"mcap_min_cr": None, "mcap_max_cr": None}),
        ("T2B", "500-30K Cr", {"mcap_min_cr": 500, "mcap_max_cr": 30_000}),
        ("T2C", "1K-30K Cr", {"mcap_min_cr": 1_000, "mcap_max_cr": 30_000}),
        ("T2D", "2K-30K Cr", {"mcap_min_cr": 2_000, "mcap_max_cr": 30_000}),
        ("T2E", "2K-20K Cr", {"mcap_min_cr": 2_000, "mcap_max_cr": 20_000}),
        ("T2F", "3K-25K Cr", {"mcap_min_cr": 3_000, "mcap_max_cr": 25_000}),
    ]

    results = []
    for test_name, label, overrides in variants:
        config = BacktestConfig(
            start_date=DEFAULT_CONFIG.start_date,
            end_date=DEFAULT_CONFIG.end_date,
            initial_capital=DEFAULT_CONFIG.initial_capital,
            **overrides,
        )
        results.append(_run_variant(db, test_name, label, config))

    _pick_winner(results)
    return results


# ---------------------------------------------------------------------------
# Test 3: Regime Filter
# ---------------------------------------------------------------------------


def run_test_3_regime(db: Session) -> list[dict]:
    """
    Test 3: Regime Filter variations
    3A: No regime filter (always fully invested)
    3B: Binary (Bull=100%, Bear=0%)
    3C: Graduated (Strong Bull=100%, Bull=75%, Weak=50%, Bear=25%, Full Bear=0%)
    3D: Default v7 graduated with crash override
    """
    variants = [
        ("T3A", "No regime filter", {"regime_filter": "none"}),
        ("T3B", "Binary Bull/Bear", {"regime_filter": "binary"}),
        ("T3C", "Graduated 4-tier", {"regime_filter": "graduated"}),
        ("T3D", "v7 graduated + crash override", {"regime_filter": "v7_default"}),
    ]

    results = []
    for test_name, label, overrides in variants:
        config = BacktestConfig(
            start_date=DEFAULT_CONFIG.start_date,
            end_date=DEFAULT_CONFIG.end_date,
            initial_capital=DEFAULT_CONFIG.initial_capital,
            **overrides,
        )
        results.append(_run_variant(db, test_name, label, config))

    _pick_winner(results)
    return results


# ---------------------------------------------------------------------------
# Test 4: Trend Template
# ---------------------------------------------------------------------------


def run_test_4_trend_template(db: Session) -> list[dict]:
    """
    Test 4: Trend Template ON vs OFF, 20% vs 25%
    4A: Trend template OFF (no Minervini filter)
    4B: Trend template ON, 20% proximity threshold (default)
    4C: Trend template ON, 25% proximity threshold (looser)
    """
    variants = [
        ("T4A", "Trend template OFF", {"trend_template_enabled": False}),
        ("T4B", "TT ON, 20% proximity", {"trend_template_enabled": True, "tt_proximity_pct": 20}),
        ("T4C", "TT ON, 25% proximity", {"trend_template_enabled": True, "tt_proximity_pct": 25}),
    ]

    results = []
    for test_name, label, overrides in variants:
        config = BacktestConfig(
            start_date=DEFAULT_CONFIG.start_date,
            end_date=DEFAULT_CONFIG.end_date,
            initial_capital=DEFAULT_CONFIG.initial_capital,
            **overrides,
        )
        results.append(_run_variant(db, test_name, label, config))

    _pick_winner(results)
    return results


# ---------------------------------------------------------------------------
# Test 5: Fundamentals
# ---------------------------------------------------------------------------


def run_test_5_fundamentals(db: Session) -> list[dict]:
    """
    Test 5: No filter vs CANSLIM vs junk-only vs bonus scores
    5A: No fundamental filter
    5B: CANSLIM hard filter (exclude stocks with score < 10)
    5C: Junk-only (only stocks that FAIL CANSLIM) — control test
    5D: CANSLIM as bonus score (no hard filter, just score boost)
    """
    variants = [
        ("T5A", "No fundamental filter", {"fundamental_filter": "none"}),
        ("T5B", "CANSLIM hard filter (min 10)", {"fundamental_filter": "canslim_hard", "canslim_min_score": 10}),
        ("T5C", "Junk-only (fail CANSLIM)", {"fundamental_filter": "junk_only"}),
        ("T5D", "CANSLIM bonus (soft)", {"fundamental_filter": "canslim_bonus"}),
    ]

    results = []
    for test_name, label, overrides in variants:
        config = BacktestConfig(
            start_date=DEFAULT_CONFIG.start_date,
            end_date=DEFAULT_CONFIG.end_date,
            initial_capital=DEFAULT_CONFIG.initial_capital,
            **overrides,
        )
        results.append(_run_variant(db, test_name, label, config))

    _pick_winner(results)
    return results


# ---------------------------------------------------------------------------
# Test 6: VCP
# ---------------------------------------------------------------------------


def run_test_6_vcp(db: Session) -> list[dict]:
    """
    Test 6: VCP win rate analysis
    6A: VCP-only entries (only enter on VCP patterns)
    6B: All breakout patterns (VCP + base + resistance)
    6C: No pattern filter (enter on score alone)
    """
    variants = [
        ("T6A", "VCP-only entries", {"pattern_filter": "vcp_only"}),
        ("T6B", "All breakout patterns", {"pattern_filter": "all_breakouts"}),
        ("T6C", "No pattern filter (score-only)", {"pattern_filter": "none"}),
    ]

    results = []
    for test_name, label, overrides in variants:
        config = BacktestConfig(
            start_date=DEFAULT_CONFIG.start_date,
            end_date=DEFAULT_CONFIG.end_date,
            initial_capital=DEFAULT_CONFIG.initial_capital,
            **overrides,
        )
        results.append(_run_variant(db, test_name, label, config))

    _pick_winner(results)
    return results


# ---------------------------------------------------------------------------
# Test 7: Exits
# ---------------------------------------------------------------------------


def run_test_7_exits(db: Session) -> list[dict]:
    """
    Test 7: Exit rule variations
    7A: Fixed stop only (no trailing, no time stop)
    7B: Fixed + trailing stop (10%/15% trail at 40%/100% gain)
    7C: Full exit suite (all 9 rules from v7)
    7D: Tighter trailing (8%/12% trail at 30%/80% gain)
    7E: Wider trailing (12%/18% trail at 50%/120% gain)
    """
    variants = [
        ("T7A", "Fixed stop only", {"exit_rules": "fixed_stop"}),
        ("T7B", "Fixed + trailing", {"exit_rules": "fixed_trailing"}),
        ("T7C", "Full v7 exit suite", {"exit_rules": "v7_full"}),
        ("T7D", "Tighter trailing (8/12)", {
            "exit_rules": "custom_trailing",
            "trail_pct_40": 8, "trail_pct_100": 12,
            "trail_trigger_40": 30, "trail_trigger_100": 80,
        }),
        ("T7E", "Wider trailing (12/18)", {
            "exit_rules": "custom_trailing",
            "trail_pct_40": 12, "trail_pct_100": 18,
            "trail_trigger_40": 50, "trail_trigger_100": 120,
        }),
    ]

    results = []
    for test_name, label, overrides in variants:
        config = BacktestConfig(
            start_date=DEFAULT_CONFIG.start_date,
            end_date=DEFAULT_CONFIG.end_date,
            initial_capital=DEFAULT_CONFIG.initial_capital,
            **overrides,
        )
        results.append(_run_variant(db, test_name, label, config))

    _pick_winner(results)
    return results


# ---------------------------------------------------------------------------
# Test 8: Rebalancing
# ---------------------------------------------------------------------------


def run_test_8_rebalancing(db: Session) -> list[dict]:
    """
    Test 8: Rebalancing frequency
    8A: Weekly rebalance (every Friday)
    8B: Biweekly rebalance
    8C: Monthly rebalance
    8D: Daily (rebalance every trading day)
    """
    variants = [
        ("T8A", "Weekly rebalance", {"rebalance_freq": "weekly"}),
        ("T8B", "Biweekly rebalance", {"rebalance_freq": "biweekly"}),
        ("T8C", "Monthly rebalance", {"rebalance_freq": "monthly"}),
        ("T8D", "Daily rebalance", {"rebalance_freq": "daily"}),
    ]

    results = []
    for test_name, label, overrides in variants:
        config = BacktestConfig(
            start_date=DEFAULT_CONFIG.start_date,
            end_date=DEFAULT_CONFIG.end_date,
            initial_capital=DEFAULT_CONFIG.initial_capital,
            **overrides,
        )
        results.append(_run_variant(db, test_name, label, config))

    _pick_winner(results)
    return results


# ---------------------------------------------------------------------------
# Test 9: Volume Signals
# ---------------------------------------------------------------------------


def run_test_9_volume_signals(db: Session) -> list[dict]:
    """
    Test 9: OBV vs delivery % vs A/D ratio
    9A: OBV slope only
    9B: Delivery % only
    9C: A/D line ratio only
    9D: OBV + delivery % combined
    9E: All three combined (v7 default)
    """
    variants = [
        ("T9A", "OBV slope only", {"volume_signals": ["obv"]}),
        ("T9B", "Delivery % only", {"volume_signals": ["delivery_pct"]}),
        ("T9C", "A/D ratio only", {"volume_signals": ["ad_ratio"]}),
        ("T9D", "OBV + delivery %", {"volume_signals": ["obv", "delivery_pct"]}),
        ("T9E", "All three (v7 default)", {"volume_signals": ["obv", "delivery_pct", "ad_ratio"]}),
    ]

    results = []
    for test_name, label, overrides in variants:
        config = BacktestConfig(
            start_date=DEFAULT_CONFIG.start_date,
            end_date=DEFAULT_CONFIG.end_date,
            initial_capital=DEFAULT_CONFIG.initial_capital,
            **overrides,
        )
        results.append(_run_variant(db, test_name, label, config))

    _pick_winner(results)
    return results


# ---------------------------------------------------------------------------
# Test 10: Full Integrated System
# ---------------------------------------------------------------------------


def run_test_10_full_system(db: Session) -> dict:
    """
    Test 10: Full integrated system with winning params from tests 1-9.

    This test uses the default config (which should reflect the best params
    found from prior tests). It runs a single comprehensive backtest and
    reports full metrics.

    Gate: CAGR > 20%, Sharpe > 1.0, MaxDD < 30%
    """
    logger.info("Running Test 10: Full integrated system")

    config = BacktestConfig(
        start_date=DEFAULT_CONFIG.start_date,
        end_date=DEFAULT_CONFIG.end_date,
        initial_capital=DEFAULT_CONFIG.initial_capital,
    )

    bt = Backtester(db, config)
    result = bt.run()
    metrics = result.compute_metrics()
    metrics["test_name"] = "T10"
    metrics["label"] = "Full integrated system"

    # Check gates
    cagr = metrics.get("cagr", 0)
    sharpe = metrics.get("sharpe_ratio", 0)
    max_dd = metrics.get("max_drawdown", 0)

    gates_passed = cagr > 0.20 and sharpe > 1.0 and abs(max_dd) < 0.30
    metrics["gates_passed"] = gates_passed

    if gates_passed:
        logger.info(
            "T10 PASSED: CAGR={:.2%}, Sharpe={:.3f}, MaxDD={:.2%}",
            cagr, sharpe, max_dd,
        )
    else:
        logger.warning(
            "T10 FAILED gates: CAGR={:.2%} (>20%?), Sharpe={:.3f} (>1.0?), MaxDD={:.2%} (<30%?)",
            cagr, sharpe, max_dd,
        )

    return metrics


# ---------------------------------------------------------------------------
# Run all tests
# ---------------------------------------------------------------------------


def run_all_tests(db: Session) -> dict:
    """
    Run all 10 tests sequentially. Returns summary dict.

    Summary includes:
    - results: dict mapping test number to list of variant results
    - winners: dict mapping test number to winning variant
    - full_system: Test 10 result
    """
    logger.info("=" * 60)
    logger.info("Starting full backtest suite (10 tests)")
    logger.info("=" * 60)

    all_results: dict[str, list[dict]] = {}
    winners: dict[str, dict] = {}

    test_runners = [
        ("T1", "Momentum Weights", run_test_1_momentum_weights),
        ("T2", "Market Cap Band", run_test_2_market_cap),
        ("T3", "Regime Filter", run_test_3_regime),
        ("T4", "Trend Template", run_test_4_trend_template),
        ("T5", "Fundamentals", run_test_5_fundamentals),
        ("T6", "VCP Patterns", run_test_6_vcp),
        ("T7", "Exit Rules", run_test_7_exits),
        ("T8", "Rebalancing", run_test_8_rebalancing),
        ("T9", "Volume Signals", run_test_9_volume_signals),
    ]

    for test_key, test_label, runner_fn in test_runners:
        logger.info("-" * 40)
        logger.info("Test {}: {}", test_key, test_label)
        logger.info("-" * 40)
        results = runner_fn(db)
        all_results[test_key] = results
        winners[test_key] = _pick_winner(results)

    # Test 10: full system
    logger.info("-" * 40)
    logger.info("Test T10: Full Integrated System")
    logger.info("-" * 40)
    full_system = run_test_10_full_system(db)

    # --- Summary ---
    logger.info("=" * 60)
    logger.info("BACKTEST SUITE COMPLETE")
    logger.info("=" * 60)

    for test_key, winner in winners.items():
        logger.info(
            "  {} winner: {} — Sharpe={:.3f}",
            test_key,
            winner.get("label", "?"),
            winner.get("sharpe_ratio", 0),
        )

    logger.info(
        "  T10 full system: Sharpe={:.3f}, CAGR={:.2%}, gates={}",
        full_system.get("sharpe_ratio", 0),
        full_system.get("cagr", 0),
        "PASSED" if full_system.get("gates_passed") else "FAILED",
    )

    return {
        "results": all_results,
        "winners": winners,
        "full_system": full_system,
    }
