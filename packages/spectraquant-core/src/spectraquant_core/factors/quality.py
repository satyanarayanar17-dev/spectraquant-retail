"""Quality factor: ROE, -Debt/Equity, -CV(EPS) (spec §7.3).

All three inputs required; any missing → NaN for that symbol.
EPS CV emits UserWarning when a symbol has fewer than 8 quarters.
"""

from __future__ import annotations

import warnings

import numpy as np
import pandas as pd

from spectraquant_core.normalize import zscore


def _eps_cv(eps_history: pd.DataFrame, min_quarters: int = 2) -> pd.Series:
    """Compute −CV(EPS) per symbol (inverted so higher = more stable earnings).

    Emits UserWarning for symbols with fewer than 8 quarters.
    Returns NaN for symbols with < min_quarters or zero mean EPS.

    Example::

        >>> import pandas as pd
        >>> eps = pd.DataFrame({"symbol": ["A"]*8, "eps_ttm": [1.0]*8,
        ...                     "period_end": range(8)})
        >>> _eps_cv(eps)  # doctest: +SKIP
    """
    results: dict[str, float] = {}
    for symbol, group in eps_history.groupby("symbol"):
        eps = group["eps_ttm"].dropna()
        n = len(eps)
        if n < 8:
            warnings.warn(
                f"{symbol}: {n} EPS quarters available (expected 8)",
                UserWarning,
                stacklevel=3,
            )
        if n < min_quarters:
            results[str(symbol)] = float("nan")
            continue
        mean_abs = abs(float(eps.mean()))
        if mean_abs == 0.0:
            results[str(symbol)] = float("nan")
            continue
        cv = float(eps.std(ddof=1)) / mean_abs
        results[str(symbol)] = -cv
    return pd.Series(results, dtype=float)


def compute_quality(
    fundamentals: pd.DataFrame,
    eps_history: pd.DataFrame,
) -> pd.Series:
    """Compute quality factor z-scores for a cross-section of symbols.

    Args:
        fundamentals: DataFrame with columns symbol_id, roe, debt_to_equity.
                      One row per symbol expected (caller applies any date filter).
        eps_history:  DataFrame with columns symbol, period_end, eps_ttm.
                      Covers up to last 8 quarters. Emits UserWarning when fewer
                      than 8 quarters are available for any symbol.

    Returns:
        Series indexed by symbol_id. Symbols missing any of the three inputs
        receive NaN; their index entries are preserved.

    Example::

        >>> import pandas as pd
        >>> fund = pd.DataFrame({"symbol_id": ["A"], "roe": [0.15],
        ...                      "debt_to_equity": [0.5]})
        >>> eps = pd.DataFrame({"symbol": ["A"]*8, "eps_ttm": [1.0]*8,
        ...                     "period_end": range(8)})
        >>> compute_quality(fund, eps).notna().all()
        True
    """
    fund = (
        fundamentals.set_index("symbol_id")
        if "symbol_id" in fundamentals.columns
        else fundamentals
    )

    roe_z = zscore(fund["roe"])
    neg_de_z = zscore(-fund["debt_to_equity"])

    cv_raw = _eps_cv(eps_history)
    cv_aligned = cv_raw.reindex(fund.index)
    cv_z = zscore(cv_aligned)

    z_df = pd.DataFrame(
        {"roe": roe_z, "neg_de": neg_de_z, "neg_cv": cv_z},
        index=fund.index,
    )

    raw_score = z_df.mean(axis=1, skipna=False)

    eligible = raw_score.dropna()
    if len(eligible) < 2:
        return pd.Series(np.nan, index=fund.index, dtype=float)

    return zscore(eligible).reindex(fund.index)
