"""
Position sizing engine -- 2% risk rule with portfolio constraints.

Rules:
- Risk per trade: entry_price - stop_loss defines risk per share
- Position size = (portfolio_value * risk_pct) / risk_per_share
- Position floor: 2% of portfolio
- Position ceiling: 20% of portfolio
- Portfolio heat: total open risk cannot exceed 6%
- Sector concentration: max 30% of portfolio in one sector
- Regime adjustment: risk_pct varies by regime level
"""

from dataclasses import dataclass

from loguru import logger

POSITION_FLOOR_PCT = 2.0
POSITION_CEILING_PCT = 20.0
MAX_PORTFOLIO_HEAT_PCT = 6.0
MAX_SECTOR_CONCENTRATION_PCT = 30.0

REGIME_RISK_MAP: dict[str, float] = {
    "Strong Bull": 2.0,
    "Bull": 1.5,
    "Weak": 1.0,
    "Bear": 0.5,
    "Full Bear": 0.0,
}


@dataclass
class PositionSize:
    shares: int
    position_value: float
    position_pct: float  # % of portfolio
    risk_amount: float
    risk_pct: float  # actual risk as % of portfolio
    regime_risk_pct: float  # regime-adjusted risk per trade


def calculate_position_size(
    portfolio_value: float,
    entry_price: float,
    stop_loss: float,
    regime_risk_pct: float,  # from regime allocation (2.0%, 1.5%, 1.0%, 0.5%)
    vol_scalar: float = 1.0,
) -> PositionSize | None:
    """
    Calculate position size using 2% risk rule.

    risk_per_share = entry_price - stop_loss
    risk_amount = portfolio_value * (regime_risk_pct / 100) * vol_scalar
    shares = risk_amount / risk_per_share
    position_value = shares * entry_price
    position_pct = position_value / portfolio_value

    Apply floor (2%) and ceiling (20%).
    Returns None if risk_per_share <= 0.
    """
    risk_per_share = entry_price - stop_loss
    if risk_per_share <= 0:
        logger.warning(
            "Invalid risk_per_share={:.2f} (entry={:.2f}, stop={:.2f})",
            risk_per_share,
            entry_price,
            stop_loss,
        )
        return None

    if portfolio_value <= 0:
        logger.warning("Portfolio value must be positive, got {:.2f}", portfolio_value)
        return None

    if regime_risk_pct <= 0:
        logger.info("Regime risk is 0% — no position allowed")
        return None

    risk_amount = portfolio_value * (regime_risk_pct / 100.0) * vol_scalar
    raw_shares = risk_amount / risk_per_share
    shares = int(raw_shares)

    if shares <= 0:
        logger.info(
            "Calculated shares=0 (risk_amount={:.2f}, risk_per_share={:.2f})",
            risk_amount,
            risk_per_share,
        )
        return None

    position_value = shares * entry_price
    position_pct = (position_value / portfolio_value) * 100.0

    # Apply floor: if position is below 2% of portfolio, skip it
    if position_pct < POSITION_FLOOR_PCT:
        logger.info(
            "Position {:.1f}% below floor {:.1f}% — skipping",
            position_pct,
            POSITION_FLOOR_PCT,
        )
        return None

    # Apply ceiling: cap at 20% of portfolio
    if position_pct > POSITION_CEILING_PCT:
        max_value = portfolio_value * (POSITION_CEILING_PCT / 100.0)
        shares = int(max_value / entry_price)
        position_value = shares * entry_price
        position_pct = (position_value / portfolio_value) * 100.0
        logger.info(
            "Position capped at ceiling {:.1f}% — shares reduced to {}",
            POSITION_CEILING_PCT,
            shares,
        )

    actual_risk = shares * risk_per_share
    actual_risk_pct = (actual_risk / portfolio_value) * 100.0

    return PositionSize(
        shares=shares,
        position_value=position_value,
        position_pct=round(position_pct, 2),
        risk_amount=round(actual_risk, 2),
        risk_pct=round(actual_risk_pct, 4),
        regime_risk_pct=regime_risk_pct,
    )


def check_portfolio_constraints(
    new_position: PositionSize,
    new_sector: str,
    open_positions: list[dict],
    portfolio_value: float,
) -> tuple[bool, str | None]:
    """
    Check if adding new_position would violate portfolio constraints.

    open_positions: list of dicts with position_value, entry_price, stop_loss, sector

    Constraints:
    1. Portfolio heat: sum of all (position_value * risk_per_share / entry_price)
       / portfolio_value <= 6%
    2. Sector concentration: sum of position_values in same sector
       / portfolio_value <= 30%

    Returns (allowed, rejection_reason).
    """
    if portfolio_value <= 0:
        return False, "Portfolio value must be positive"

    # --- Portfolio heat check ---
    total_risk = new_position.risk_amount
    for pos in open_positions:
        risk_per_share = pos["entry_price"] - pos["stop_loss"]
        if risk_per_share > 0:
            shares_in_pos = pos["position_value"] / pos["entry_price"]
            total_risk += shares_in_pos * risk_per_share

    heat_pct = (total_risk / portfolio_value) * 100.0
    if heat_pct > MAX_PORTFOLIO_HEAT_PCT:
        reason = (
            f"Portfolio heat {heat_pct:.2f}% would exceed "
            f"max {MAX_PORTFOLIO_HEAT_PCT:.1f}%"
        )
        logger.warning(reason)
        return False, reason

    # --- Sector concentration check ---
    sector_value = new_position.position_value
    for pos in open_positions:
        if pos.get("sector", "") == new_sector:
            sector_value += pos["position_value"]

    sector_pct = (sector_value / portfolio_value) * 100.0
    if sector_pct > MAX_SECTOR_CONCENTRATION_PCT:
        reason = (
            f"Sector '{new_sector}' concentration {sector_pct:.2f}% would exceed "
            f"max {MAX_SECTOR_CONCENTRATION_PCT:.1f}%"
        )
        logger.warning(reason)
        return False, reason

    return True, None


def get_regime_risk_pct(regime: str) -> float:
    """
    Map regime to risk-per-trade percentage.

    Strong Bull: 2.0%, Bull: 1.5%, Weak: 1.0%, Bear: 0.5%, Full Bear: 0%
    """
    risk_pct = REGIME_RISK_MAP.get(regime)
    if risk_pct is None:
        logger.warning("Unknown regime '{}', defaulting to Bear (0.5%)", regime)
        return 0.5
    return risk_pct
