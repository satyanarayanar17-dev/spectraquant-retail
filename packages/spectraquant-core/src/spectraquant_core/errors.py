"""Domain exceptions for spectraquant-core."""

from __future__ import annotations


class ZeroWeightPortfolioError(ValueError):
    """Raised when portfolio weights sum to zero."""


class InsufficientDataError(ValueError):
    """Raised when there is not enough data for a computation."""


class InvalidUniverseError(ValueError):
    """Raised when the symbol universe is invalid or too small."""


class PointInTimeLookAheadError(ValueError):
    """Raised when factor z-scores use a score_date that equals or follows the
    rebalance date, violating the point-in-time lookahead guard (spec §14.1)."""
