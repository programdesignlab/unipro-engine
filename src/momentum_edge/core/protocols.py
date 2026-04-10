"""Plugin protocols and result dataclasses for scoring and filtering modules."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Protocol, runtime_checkable

from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


@dataclass
class ScoreResult:
    """Output from any scoring module."""

    symbol: str
    score: float
    max_possible: float
    components: dict[str, float] = field(default_factory=dict)
    metadata: dict | None = None


@dataclass
class FilterResult:
    """Output from any universe filter."""

    symbol: str
    passed: bool
    reason: str | None = None
    data_missing: bool = False


@dataclass
class ExitDecision:
    """Output from an exit rule evaluation."""

    should_exit: bool
    exit_pct: float = 1.0          # Partial exit support (0.25, 0.50, 1.0)
    new_stop: float | None = None  # Update stop without exiting
    rule_name: str = ""
    reason: str = ""


# ---------------------------------------------------------------------------
# Plugin protocols
# ---------------------------------------------------------------------------


@runtime_checkable
class ScorerProtocol(Protocol):
    """Protocol for scoring modules. Each reads params from strategy YAML."""

    @property
    def name(self) -> str: ...

    def score(
        self,
        db: Session,
        stock_id: int,
        symbol: str,
        target_date: date,
        params: dict,
    ) -> ScoreResult: ...


@runtime_checkable
class FilterProtocol(Protocol):
    """Protocol for universe filter modules."""

    @property
    def name(self) -> str: ...

    def check(
        self,
        db: Session,
        stock: object,  # Stock ORM instance
        target_date: date,
        params: dict,
    ) -> FilterResult: ...
