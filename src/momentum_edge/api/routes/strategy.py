"""Strategy info API endpoints."""

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1", tags=["strategy"])


@router.get("/strategy/info")
def get_strategy_info():
    """Return active strategy metadata and hash."""
    from momentum_edge.core.strategy import load_strategy

    try:
        s = load_strategy("strategies/momentum_edge.yaml")
        return {
            "name": s.meta.name,
            "version": s.meta.version,
            "description": s.meta.description,
            "strategy_hash": s.strategy_hash,
            "exit_framework": s.exits.framework,
            "hard_blocks": len([b for b in s.universe.hard_blocks if b.enabled]),
            "scoring_modules": len([m for m in s.scoring.modules if m.enabled]),
            "exit_phases": len(s.exits.phases),
            "cascade_layers": len(s.exits.cascade.layers),
            "monster_enabled": s.monster.enabled,
            "fast_crash_enabled": s.regime.fast_crash.enabled,
        }
    except Exception as e:
        return {"error": str(e)}


@router.get("/strategy/params")
def get_strategy_params():
    """Return full strategy parameters (read-only)."""
    from momentum_edge.core.strategy import load_strategy

    try:
        s = load_strategy("strategies/momentum_edge.yaml")
        return s.model_dump()
    except Exception as e:
        return {"error": str(e)}
