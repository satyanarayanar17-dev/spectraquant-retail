"""Domain exceptions for spectraquant-core."""

from __future__ import annotations


class ZeroWeightPortfolioError(ValueError):
    """Raised when portfolio weights sum to zero."""


class InsufficientDataError(ValueError):
    """Raised when there is not enough data for a computation."""


class InvalidUniverseError(ValueError):
    """Raised when the symbol universe is invalid or too small."""
