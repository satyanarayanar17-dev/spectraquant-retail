"""Portfolio weight normalisation and factor exposure computation (spec §7.7)."""

from __future__ import annotations

import pandas as pd
from pydantic import BaseModel, model_validator

from spectraquant_core.errors import ZeroWeightPortfolioError


class Holding(BaseModel):
    """Single portfolio position.

    Supply either (qty + avg_price) to derive a value-based weight, or supply
    weight directly. If weight is given and all holdings sum to 1 (±0.01) the
    weights are used as-is; otherwise weights are normalised.

    Example::

        >>> Holding(symbol="RELIANCE", qty=10, avg_price=2500.0)
        Holding(symbol='RELIANCE', qty=10, avg_price=2500.0, weight=None)
    """

    symbol: str
    qty: float | None = None
    avg_price: float | None = None
    weight: float | None = None

    @model_validator(mode="after")
    def _check_inputs(self) -> Holding:
        has_value = self.qty is not None and self.avg_price is not None
        has_weight = self.weight is not None
        if not has_value and not has_weight:
            raise ValueError(
                "Provide either (qty + avg_price) or weight for each holding."
            )
        return self


def normalize_weights(holdings: list[Holding]) -> pd.Series:
    """Convert a list of holdings to a symbol-indexed weight Series that sums to 1.

    Priority:
      1. If all holdings supply ``weight`` and they sum to 1.0 ± 0.01 → use as-is.
      2. If ``qty`` + ``avg_price`` are given → weight = value / total_value.
      3. If supplied weights don't sum to 1 → normalise by sum.

    Raises:
        ZeroWeightPortfolioError: when total value or weight is zero.

    Example::

        >>> h = [Holding(symbol="A", qty=10, avg_price=100.0),
        ...      Holding(symbol="B", qty=5,  avg_price=200.0)]
        >>> normalize_weights(h)
        A    0.5
        B    0.5
        dtype: float64
    """
    if not holdings:
        raise ZeroWeightPortfolioError("Holdings list is empty.")

    symbols = [h.symbol for h in holdings]

    # --- path 1: all weights present ---
    if all(h.weight is not None for h in holdings):
        raw = pd.Series([h.weight for h in holdings], index=symbols, dtype=float)
        total = float(raw.sum())
        if total == 0.0:
            raise ZeroWeightPortfolioError("All weights are zero.")
        if abs(total - 1.0) <= 0.01:
            return raw
        return raw / total

    # --- path 2: value from qty × avg_price ---
    values = []
    for h in holdings:
        if h.qty is not None and h.avg_price is not None:
            values.append(h.qty * h.avg_price)
        elif h.weight is not None:
            values.append(h.weight)
        else:
            raise ValueError(f"Holding '{h.symbol}' has neither value nor weight.")

    raw = pd.Series(values, index=symbols, dtype=float)
    total = float(raw.sum())
    if total == 0.0:
        raise ZeroWeightPortfolioError("Total portfolio value is zero.")
    return raw / total


def compute_exposures(
    weights: pd.Series,
    z_scores: dict[str, pd.Series],
) -> dict[str, float]:
    """Compute portfolio factor exposures as weighted sum of cross-sectional z-scores.

    For each factor, the exposure = Σ(weight_i × z_score_i) over symbols
    present in both ``weights`` and the factor's Series. Symbols missing from
    a factor's z-score contribute 0 to that factor's exposure (i.e. they are
    treated as average).

    Args:
        weights:  Series indexed by symbol, summing to 1.
        z_scores: Mapping of factor name → cross-sectional z-score Series.

    Returns:
        Dict of factor name → float exposure.

    Example::

        >>> import pandas as pd
        >>> w = pd.Series({"A": 0.6, "B": 0.4})
        >>> z = {"momentum": pd.Series({"A": 1.0, "B": -1.0})}
        >>> compute_exposures(w, z)
        {'momentum': np.float64(0.19999999999999996)}
    """
    exposures: dict[str, float] = {}
    for factor, zs in z_scores.items():
        aligned_z = zs.reindex(weights.index).fillna(0.0)
        exposures[factor] = float((weights * aligned_z).sum())
    return exposures
