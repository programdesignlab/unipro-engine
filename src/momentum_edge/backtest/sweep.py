"""
Parameter sweep runner — generates combinatorial configs from FREE params.

Reads `test_range` fields from the strategy YAML (where FREE params are marked
with test ranges in comments). Generates all combinations and runs backtests
for each, ranking results by Sharpe ratio.

Usage:
    PYTHONPATH=src uv run python -c "
    from momentum_edge.backtest.sweep import run_sweep
    results = run_sweep(db, 'strategies/momentum_edge.yaml', date(2015,1,1), date(2024,12,31))
    "
"""

from __future__ import annotations

import copy
import itertools
from datetime import date
from functools import reduce
from typing import Iterator

import pandas as pd
from loguru import logger
from sqlalchemy.orm import Session

from momentum_edge.core.strategy import StrategyConfig, load_strategy


# ---------------------------------------------------------------------------
# Sweep parameter definitions
# ---------------------------------------------------------------------------

# These define the tunable parameters and their test ranges.
# Each entry: (yaml_path, list_of_values)
# Paths use dot notation matching the YAML structure.

DEFAULT_SWEEP_PARAMS: dict[str, list] = {
    # Universe filters
    "universe.hard_blocks.0.params.min_cr": [1000, 1500, 2000],
    # Exit engine — prove_it fixed stop
    "exits.phases.0.rules.0.stop_pct": [0.06, 0.08, 0.10],
    # Exit engine — let_it_run trail
    "exits.phases.1.rules.0.trail_pct": [0.15, 0.20, 0.25],
}


def _set_nested(d: dict, path: str, value) -> None:
    """Set a value in a nested dict using dot notation with integer indices."""
    keys = path.split(".")
    current = d
    for key in keys[:-1]:
        if key.isdigit():
            current = current[int(key)]
        else:
            current = current[key]
    final_key = keys[-1]
    if final_key.isdigit():
        current[int(final_key)] = value
    else:
        current[final_key] = value


def _get_nested(d: dict, path: str):
    """Get a value from a nested dict using dot notation."""
    keys = path.split(".")
    current = d
    for key in keys:
        if key.isdigit():
            current = current[int(key)]
        else:
            current = current[key]
    return current


def generate_configs(
    base_config: dict,
    sweep_params: dict[str, list] | None = None,
) -> Iterator[tuple[dict, dict]]:
    """
    Yield (modified_config_dict, param_values_dict) for each combination.
    """
    params = sweep_params or DEFAULT_SWEEP_PARAMS
    keys = list(params.keys())
    values = list(params.values())

    total = reduce(lambda a, b: a * b, [len(v) for v in values], 1)
    logger.info(f"Sweep: {total} combinations from {len(keys)} parameters")

    for combo in itertools.product(*values):
        config = copy.deepcopy(base_config)
        param_snapshot = {}
        for key, val in zip(keys, combo):
            _set_nested(config, key, val)
            param_snapshot[key] = val
        yield config, param_snapshot


def run_sweep(
    db: Session,
    strategy_path: str = "strategies/momentum_edge.yaml",
    start_date: date = date(2015, 1, 1),
    end_date: date = date(2024, 12, 31),
    sweep_params: dict[str, list] | None = None,
) -> pd.DataFrame:
    """
    Run parameter sweep: backtest each combination, return results ranked by Sharpe.
    """
    from momentum_edge.backtest.engine import Backtester, BacktestConfig
    from momentum_edge.core.strategy import compute_strategy_hash

    base_strategy = load_strategy(strategy_path)
    base_dict = base_strategy.model_dump()

    results = []
    configs = list(generate_configs(base_dict, sweep_params))
    total = len(configs)

    for i, (config_dict, param_values) in enumerate(configs):
        # Reconstruct StrategyConfig from modified dict
        try:
            strategy = StrategyConfig.model_validate(config_dict)
        except Exception as e:
            logger.warning(f"Sweep {i+1}/{total}: invalid config — {e}")
            continue

        strategy_hash = strategy.strategy_hash
        logger.info(f"Sweep {i+1}/{total} [{strategy_hash}]: {param_values}")

        # Create BacktestConfig from strategy
        bt_config = BacktestConfig.from_strategy(start_date, end_date, strategy_path)
        # Override with sweep-specific params
        bt_config.use_phase_exits = strategy.exits.framework == "phase_based"

        bt = Backtester(db, bt_config)
        bt.prepare_data()
        bt.run()
        metrics = bt.compute_metrics()

        metrics["strategy_hash"] = strategy_hash
        metrics["params"] = param_values
        results.append(metrics)

    if not results:
        logger.warning("Sweep produced no results")
        return pd.DataFrame()

    df = pd.DataFrame(results)
    df = df.sort_values("sharpe_ratio", ascending=False).reset_index(drop=True)

    logger.info(
        f"Sweep complete: {len(df)} configs. "
        f"Best Sharpe: {df.iloc[0]['sharpe_ratio']:.2f} "
        f"(CAGR: {df.iloc[0]['cagr']:.1f}%)"
    )

    return df
