"""
Walk-forward validation — expanding and rolling window tests.

Expanding Window (Primary):
  Fold 1: Train 2015–2018, Test 2019–2020 (COVID crash)
  Fold 2: Train 2015–2019, Test 2020–2021 (V-recovery)
  Fold 3: Train 2015–2020, Test 2021–2022 (inflation bear)
  Fold 4: Train 2015–2021, Test 2022–2024 (recent bull)

Rolling Window (Secondary):
  Fold 5: Train 2015–2018, Test 2019–2020
  Fold 6: Train 2017–2020, Test 2021–2022
  Fold 7: Train 2019–2022, Test 2023–2024

Gate: OOS Sharpe >= 70% of IS Sharpe in ALL folds
"""

from dataclasses import dataclass
from datetime import date

from loguru import logger
from sqlalchemy.orm import Session

from momentum_edge.backtest.engine import Backtester, BacktestConfig


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class WalkForwardFold:
    window_type: str  # "expanding" or "rolling"
    fold: int
    train_start: date
    train_end: date
    test_start: date
    test_end: date


@dataclass
class WalkForwardResult:
    fold: WalkForwardFold
    is_sharpe: float  # in-sample Sharpe
    oos_sharpe: float  # out-of-sample Sharpe
    oos_is_ratio: float  # oos_sharpe / is_sharpe
    is_cagr: float
    oos_cagr: float
    passed_gate: bool  # oos_sharpe >= 0.7 * is_sharpe


# ---------------------------------------------------------------------------
# Fold definitions
# ---------------------------------------------------------------------------

EXPANDING_FOLDS = [
    WalkForwardFold("expanding", 1, date(2015, 1, 1), date(2018, 12, 31), date(2019, 1, 1), date(2020, 12, 31)),
    WalkForwardFold("expanding", 2, date(2015, 1, 1), date(2019, 12, 31), date(2020, 1, 1), date(2021, 12, 31)),
    WalkForwardFold("expanding", 3, date(2015, 1, 1), date(2020, 12, 31), date(2021, 1, 1), date(2022, 12, 31)),
    WalkForwardFold("expanding", 4, date(2015, 1, 1), date(2021, 12, 31), date(2022, 1, 1), date(2024, 12, 31)),
]

ROLLING_FOLDS = [
    WalkForwardFold("rolling", 5, date(2015, 1, 1), date(2018, 12, 31), date(2019, 1, 1), date(2020, 12, 31)),
    WalkForwardFold("rolling", 6, date(2017, 1, 1), date(2020, 12, 31), date(2021, 1, 1), date(2022, 12, 31)),
    WalkForwardFold("rolling", 7, date(2019, 1, 1), date(2022, 12, 31), date(2023, 1, 1), date(2024, 12, 31)),
]

_SHARPE_DEGRADATION_GATE = 0.70  # OOS Sharpe must be >= 70% of IS Sharpe
_ROLLING_VS_EXPANDING_TOLERANCE_PP = 15  # rolling can be 15pp worse


# ---------------------------------------------------------------------------
# Walk-forward runner
# ---------------------------------------------------------------------------


def _run_single_fold(
    db: Session,
    fold: WalkForwardFold,
    base_config: BacktestConfig | None = None,
) -> WalkForwardResult:
    """
    Run a single walk-forward fold.

    1. Backtest on the train period to get in-sample (IS) metrics.
    2. Backtest on the test period with same params to get out-of-sample (OOS) metrics.
    3. Compute OOS/IS Sharpe ratio and check gate.
    """
    if base_config is None:
        base_config = BacktestConfig(
            start_date=fold.train_start,
            end_date=fold.train_end,
            initial_capital=1_000_000,
        )

    # --- In-sample backtest ---
    is_config = BacktestConfig(
        start_date=fold.train_start,
        end_date=fold.train_end,
        initial_capital=base_config.initial_capital,
    )
    logger.info(
        "Fold {} [{}] IS: {} to {}",
        fold.fold, fold.window_type, fold.train_start, fold.train_end,
    )
    is_bt = Backtester(db, is_config)
    is_result = is_bt.run()
    is_metrics = is_result.compute_metrics()

    # --- Out-of-sample backtest ---
    oos_config = BacktestConfig(
        start_date=fold.test_start,
        end_date=fold.test_end,
        initial_capital=base_config.initial_capital,
    )
    logger.info(
        "Fold {} [{}] OOS: {} to {}",
        fold.fold, fold.window_type, fold.test_start, fold.test_end,
    )
    oos_bt = Backtester(db, oos_config)
    oos_result = oos_bt.run()
    oos_metrics = oos_result.compute_metrics()

    # --- Compare ---
    is_sharpe = is_metrics.get("sharpe_ratio", 0.0)
    oos_sharpe = oos_metrics.get("sharpe_ratio", 0.0)
    is_cagr = is_metrics.get("cagr", 0.0)
    oos_cagr = oos_metrics.get("cagr", 0.0)

    if is_sharpe > 0:
        ratio = oos_sharpe / is_sharpe
    else:
        # If IS Sharpe is zero or negative, only pass if OOS is also non-negative
        ratio = 1.0 if oos_sharpe >= 0 else 0.0

    passed = ratio >= _SHARPE_DEGRADATION_GATE

    result = WalkForwardResult(
        fold=fold,
        is_sharpe=round(is_sharpe, 4),
        oos_sharpe=round(oos_sharpe, 4),
        oos_is_ratio=round(ratio, 4),
        is_cagr=round(is_cagr, 4),
        oos_cagr=round(oos_cagr, 4),
        passed_gate=passed,
    )

    status = "PASS" if passed else "FAIL"
    logger.info(
        "Fold {} result: IS Sharpe={:.3f}, OOS Sharpe={:.3f}, ratio={:.1%} [{}]",
        fold.fold, is_sharpe, oos_sharpe, ratio, status,
    )

    return result


def run_walk_forward(
    db: Session,
    window_type: str = "both",
    base_config: BacktestConfig | None = None,
) -> list[WalkForwardResult]:
    """
    Run walk-forward validation.

    For each fold:
    1. Run backtest on train period -> get IS metrics
    2. Run backtest on test period with same params -> get OOS metrics
    3. Compare OOS Sharpe to IS Sharpe
    4. Save result to walkforward_results table

    window_type: "expanding", "rolling", or "both"
    """
    folds: list[WalkForwardFold] = []

    if window_type in ("expanding", "both"):
        folds.extend(EXPANDING_FOLDS)
    if window_type in ("rolling", "both"):
        folds.extend(ROLLING_FOLDS)

    if not folds:
        raise ValueError(f"Invalid window_type '{window_type}'. Use 'expanding', 'rolling', or 'both'.")

    logger.info("Starting walk-forward validation: {} folds ({})", len(folds), window_type)

    results: list[WalkForwardResult] = []
    for fold in folds:
        result = _run_single_fold(db, fold, base_config)
        results.append(result)

    # --- Summary ---
    passed_count = sum(1 for r in results if r.passed_gate)
    total_count = len(results)
    logger.info(
        "Walk-forward complete: {}/{} folds passed gate (OOS >= {:.0%} of IS)",
        passed_count, total_count, _SHARPE_DEGRADATION_GATE,
    )

    gates = check_walk_forward_gates(results)
    if gates["all_passed"]:
        logger.info("Walk-forward gates: ALL PASSED")
    else:
        logger.warning("Walk-forward gates: FAILED — {}", gates["failure_reasons"])

    return results


def check_walk_forward_gates(results: list[WalkForwardResult]) -> dict:
    """
    Check v7 walk-forward gates:
    - Expanding: OOS Sharpe >= 70% of IS in ALL 4 folds
    - Rolling: not materially worse than expanding (within 15pp)

    Returns dict with:
        all_passed: bool
        expanding_passed: bool
        rolling_consistent: bool
        failure_reasons: list[str]
        expanding_avg_ratio: float
        rolling_avg_ratio: float
    """
    expanding = [r for r in results if r.fold.window_type == "expanding"]
    rolling = [r for r in results if r.fold.window_type == "rolling"]

    failure_reasons: list[str] = []

    # Gate 1: ALL expanding folds must pass the 70% threshold
    expanding_passed = all(r.passed_gate for r in expanding) if expanding else True
    if not expanding_passed:
        failed_folds = [r.fold.fold for r in expanding if not r.passed_gate]
        failure_reasons.append(
            f"Expanding folds {failed_folds} failed OOS/IS Sharpe gate "
            f"(required >= {_SHARPE_DEGRADATION_GATE:.0%})"
        )

    expanding_avg_ratio = (
        sum(r.oos_is_ratio for r in expanding) / len(expanding)
        if expanding else 0.0
    )

    # Gate 2: Rolling results should not be materially worse than expanding
    rolling_avg_ratio = (
        sum(r.oos_is_ratio for r in rolling) / len(rolling)
        if rolling else 0.0
    )

    rolling_consistent = True
    if expanding and rolling:
        diff_pp = (expanding_avg_ratio - rolling_avg_ratio) * 100
        if diff_pp > _ROLLING_VS_EXPANDING_TOLERANCE_PP:
            rolling_consistent = False
            failure_reasons.append(
                f"Rolling avg ratio ({rolling_avg_ratio:.1%}) is {diff_pp:.1f}pp "
                f"worse than expanding ({expanding_avg_ratio:.1%}), "
                f"exceeds {_ROLLING_VS_EXPANDING_TOLERANCE_PP}pp tolerance"
            )

    all_passed = expanding_passed and rolling_consistent

    return {
        "all_passed": all_passed,
        "expanding_passed": expanding_passed,
        "rolling_consistent": rolling_consistent,
        "failure_reasons": failure_reasons,
        "expanding_avg_ratio": round(expanding_avg_ratio, 4),
        "rolling_avg_ratio": round(rolling_avg_ratio, 4),
    }
