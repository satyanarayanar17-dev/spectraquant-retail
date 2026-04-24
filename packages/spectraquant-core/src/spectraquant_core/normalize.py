"""Cross-sectional normalisation helpers.

All functions preserve NaN, handle empty input, and raise TypeError on
non-numeric input. No module-level side effects.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def winsorize(x: pd.Series, lower: float = 0.01, upper: float = 0.99) -> pd.Series:
    """Clip x to the [lower, upper] quantile range, preserving NaN.

    Example::

        >>> import pandas as pd
        >>> s = pd.Series([1.0, 2.0, 3.0, 4.0, 100.0])
        >>> winsorize(s, lower=0.05, upper=0.95).iloc[-1] < 100
        True
    """
    if not pd.api.types.is_numeric_dtype(x):
        raise TypeError(f"Expected numeric Series, got {x.dtype}")
    if x.empty:
        return x.copy()
    lo = float(x.quantile(lower))
    hi = float(x.quantile(upper))
    return x.clip(lower=lo, upper=hi)


def zscore(x: pd.Series) -> pd.Series:
    """Cross-sectional z-score: (x − mean) / std, NaN preserved.

    Returns an all-NaN series when std == 0 (constant input).

    Example::

        >>> import pandas as pd
        >>> z = zscore(pd.Series([10.0, 20.0, 30.0]))
        >>> round(float(z.iloc[0]), 6)
        -1.0
    """
    if not pd.api.types.is_numeric_dtype(x):
        raise TypeError(f"Expected numeric Series, got {x.dtype}")
    if x.empty:
        return x.copy()
    mu = float(x.mean())
    sigma = float(x.std(ddof=1))
    if sigma == 0:
        return pd.Series(np.nan, index=x.index, dtype=float)
    return (x - mu) / sigma


def rank_pct(x: pd.Series) -> pd.Series:
    """Percentile rank in [1/n, 1], ties averaged, NaN preserved.

    Example::

        >>> import pandas as pd
        >>> r = rank_pct(pd.Series([10.0, 20.0, 30.0]))
        >>> list(round(v, 6) for v in r)
        [0.333333, 0.666667, 1.0]
    """
    if not pd.api.types.is_numeric_dtype(x):
        raise TypeError(f"Expected numeric Series, got {x.dtype}")
    if x.empty:
        return x.copy()
    return x.rank(pct=True, na_option="keep")
