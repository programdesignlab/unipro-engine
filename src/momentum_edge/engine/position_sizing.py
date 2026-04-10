"""
v16 Position sizing engine — regime-aware with 3 adjustment layers.

Base: 2% risk rule (entry - stop defines risk per share)
Regime: portfolio heat varies by regime level (6%/5%/4%/2%/0%)
Adjustments (multiplicative):
  1. Beta > 2.5 → 40% size reduction
  2. Thin float (promoter > 75%, non-PSU) → 40% reduction + require bulk deal
  3. Correlation > 0.85 with existing holding → 50% reduction
     Correlation > 0.70 → 25% reduction

All constants read from strategy.position_sizing config.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from loguru import logger
from sqlalchemy.orm import Session

from momentum_edge.core.strategy import PositionSizingConfig, RegimeConfig


@dataclass
class PositionSize:
    shares: int
    position_value: float
    position_pct: float          # % of portfolio
    risk_amount: float
    risk_pct: float              # actual risk as % of portfolio
    regime_risk_pct: float       # regime-adjusted risk per trade
    adjustments_applied: list[str]  # which adjustments fired


def _get_regime_params(regime: str, regime_config: RegimeConfig | None) -> dict:
    """Get risk_per_trade and portfolio_heat for a regime."""
    defaults = {
        "Strong Bull": {"risk": 2.0, "heat": 6.0},
        "Bull": {"risk": 1.5, "heat": 5.0},
        "Weak": {"risk": 1.0, "heat": 4.0},
        "Bear": {"risk": 0.5, "heat": 2.0},
        "Full Bear": {"risk": 0.0, "heat": 0.0},
    }

    if regime_config:
        for cls in regime_config.classifications:
            if cls.name.replace("_", " ").title() == regime or cls.exposure_label == regime:
                return {"risk": cls.risk_per_trade, "heat": cls.portfolio_heat}
            # Also match enum-style names
            if cls.name == "strong_bull" and regime == "Strong Bull":
                return {"risk": cls.risk_per_trade, "heat": cls.portfolio_heat}
            if cls.name == "bull" and regime == "Bull":
                return {"risk": cls.risk_per_trade, "heat": cls.portfolio_heat}
            if cls.name == "weak" and regime == "Weak":
                return {"risk": cls.risk_per_trade, "heat": cls.portfolio_heat}
            if cls.name == "bear" and regime == "Bear":
                return {"risk": cls.risk_per_trade, "heat": cls.portfolio_heat}
            if cls.name == "full_bear" and regime == "Full Bear":
                return {"risk": cls.risk_per_trade, "heat": cls.portfolio_heat}

    d = defaults.get(regime, {"risk": 0.5, "heat": 2.0})
    return d


def _apply_beta_reduction(
    stock, db: Session, config: PositionSizingConfig,
) -> tuple[float, str | None]:
    """Beta > 2.5 → 40% size reduction. Returns (multiplier, label or None)."""
    for adj in config.adjustments:
        if adj.name == "beta_reduction" and adj.enabled:
            beta = getattr(stock, "beta", None)
            if beta is not None and beta > 2.5:
                mult = 1.0 - adj.reduction
                return mult, f"beta_{beta:.1f}_reduction_{adj.reduction*100:.0f}pct"
    return 1.0, None


def _apply_thin_float_reduction(
    stock, db: Session, config: PositionSizingConfig,
) -> tuple[float, str | None]:
    """Promoter > 75% AND not PSU → 40% reduction."""
    for adj in config.adjustments:
        if adj.name == "thin_float" and adj.enabled:
            promoter = getattr(stock, "promoter_holding_pct", None)
            is_psu = getattr(stock, "is_psu", False)
            if promoter is not None and promoter > 75 and not is_psu:
                mult = 1.0 - adj.reduction
                return mult, f"thin_float_promoter_{promoter:.0f}pct"
    return 1.0, None


def _apply_correlation_reduction(
    stock_id: int,
    open_positions: list,
    db: Session,
    target_date: date,
    config: PositionSizingConfig,
) -> tuple[float, str | None]:
    """Correlation with existing holdings → size reduction."""
    for adj in config.adjustments:
        if adj.name == "correlation" and adj.enabled:
            existing_ids = []
            for pos in open_positions:
                sid = pos.stock_id if hasattr(pos, "stock_id") else pos.get("stock_id")
                if sid and sid != stock_id:
                    existing_ids.append(sid)

            if not existing_ids:
                return 1.0, None

            from momentum_edge.engine.correlation import compute_pairwise_correlation

            lookback = adj.lookback_days or 60
            min_overlap = adj.min_overlap_days or 30
            correlations = compute_pairwise_correlation(
                db, stock_id, existing_ids, target_date,
                lookback_days=lookback, min_overlap_days=min_overlap,
            )

            if not correlations:
                return 1.0, None

            max_corr = max(correlations.values())
            thresh_high = adj.threshold_high or 0.85
            thresh_mod = adj.threshold_moderate or 0.70
            red_high = adj.reduction_high or 0.50
            red_mod = adj.reduction_moderate or 0.25

            if max_corr > thresh_high:
                return 1.0 - red_high, f"corr_{max_corr:.2f}_high_reduction"
            if max_corr > thresh_mod:
                return 1.0 - red_mod, f"corr_{max_corr:.2f}_moderate_reduction"

    return 1.0, None


def calculate_position_size(
    portfolio_value: float,
    entry_price: float,
    stop_loss: float,
    regime: str,
    vol_scalar: float = 1.0,
    stock=None,
    db: Session | None = None,
    target_date: date | None = None,
    open_positions: list | None = None,
    strategy=None,
) -> PositionSize | None:
    """
    Calculate position size using risk rule with regime + adjustment layers.

    Returns None if position is invalid (zero risk, zero regime allocation, etc).
    """
    sizing_config = strategy.position_sizing if strategy else None
    regime_config = strategy.regime if strategy else None

    # Get regime-dependent risk
    regime_params = _get_regime_params(regime, regime_config)
    regime_risk_pct = regime_params["risk"]

    if regime_risk_pct <= 0:
        logger.info("Regime risk is 0% — no position allowed")
        return None

    risk_per_share = entry_price - stop_loss
    if risk_per_share <= 0:
        logger.warning("Invalid risk_per_share={:.2f}", risk_per_share)
        return None

    if portfolio_value <= 0:
        return None

    # Base risk amount
    base_risk_pct = sizing_config.base_risk_pct if sizing_config else regime_risk_pct
    risk_amount = portfolio_value * (base_risk_pct / 100.0) * vol_scalar

    # Apply adjustment layers (multiplicative)
    adjustments = []
    total_mult = 1.0

    if stock and db and sizing_config:
        mult, label = _apply_beta_reduction(stock, db, sizing_config)
        total_mult *= mult
        if label:
            adjustments.append(label)

        mult, label = _apply_thin_float_reduction(stock, db, sizing_config)
        total_mult *= mult
        if label:
            adjustments.append(label)

    if stock and db and target_date and open_positions and sizing_config:
        stock_id = stock.id if hasattr(stock, "id") else stock.get("id")
        if stock_id:
            mult, label = _apply_correlation_reduction(
                stock_id, open_positions, db, target_date, sizing_config,
            )
            total_mult *= mult
            if label:
                adjustments.append(label)

    risk_amount *= total_mult
    raw_shares = risk_amount / risk_per_share
    shares = int(raw_shares)

    if shares <= 0:
        return None

    position_value = shares * entry_price
    position_pct = (position_value / portfolio_value) * 100.0

    # Floor and ceiling from config
    floor_pct = sizing_config.position_floor_pct if sizing_config else 2.0
    ceiling_pct = sizing_config.position_ceiling_pct if sizing_config else 20.0

    if position_pct < floor_pct:
        logger.info("Position {:.1f}% below floor {:.1f}%", position_pct, floor_pct)
        return None

    if position_pct > ceiling_pct:
        max_value = portfolio_value * (ceiling_pct / 100.0)
        shares = int(max_value / entry_price)
        position_value = shares * entry_price
        position_pct = (position_value / portfolio_value) * 100.0
        adjustments.append(f"capped_at_{ceiling_pct:.0f}pct")

    actual_risk = shares * risk_per_share
    actual_risk_pct = (actual_risk / portfolio_value) * 100.0

    return PositionSize(
        shares=shares,
        position_value=position_value,
        position_pct=round(position_pct, 2),
        risk_amount=round(actual_risk, 2),
        risk_pct=round(actual_risk_pct, 4),
        regime_risk_pct=regime_risk_pct,
        adjustments_applied=adjustments,
    )


def check_portfolio_constraints(
    new_position: PositionSize,
    new_sector: str,
    open_positions: list[dict],
    portfolio_value: float,
    strategy=None,
) -> tuple[bool, str | None]:
    """
    Check if adding new_position would violate portfolio constraints.

    Constraints:
    1. Portfolio heat: total open risk / portfolio_value <= regime heat cap
    2. Sector concentration: sector exposure / portfolio_value <= max_sector %
    """
    if portfolio_value <= 0:
        return False, "Portfolio value must be positive"

    sizing_config = strategy.position_sizing if strategy else None
    max_heat = 6.0  # default
    max_sector = 0.30

    if sizing_config:
        max_sector = sizing_config.max_sector_concentration

    # Portfolio heat check
    total_risk = new_position.risk_amount
    for pos in open_positions:
        risk_per_share = pos["entry_price"] - pos["stop_loss"]
        if risk_per_share > 0:
            shares_in_pos = pos["position_value"] / pos["entry_price"]
            total_risk += shares_in_pos * risk_per_share

    heat_pct = (total_risk / portfolio_value) * 100.0
    if heat_pct > max_heat:
        return False, f"Portfolio heat {heat_pct:.2f}% > max {max_heat:.1f}%"

    # Sector concentration check
    sector_value = new_position.position_value
    for pos in open_positions:
        if pos.get("sector", "") == new_sector:
            sector_value += pos["position_value"]

    sector_pct = sector_value / portfolio_value
    if sector_pct > max_sector:
        return False, f"Sector '{new_sector}' {sector_pct*100:.1f}% > max {max_sector*100:.0f}%"

    return True, None


def get_regime_risk_pct(regime: str, strategy=None) -> float:
    """Map regime to risk-per-trade percentage."""
    regime_config = strategy.regime if strategy else None
    params = _get_regime_params(regime, regime_config)
    return params["risk"]
