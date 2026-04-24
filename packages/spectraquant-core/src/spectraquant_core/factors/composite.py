"""Composite factor: equal-weighted mean of all five factor z-scores, re-z-scored."""

from __future__ import annotations

import numpy as np
import pandas as pd

from spectraquant_core.normalize import zscore


def compute_composite(z_scores: dict[str, pd.Series]) -> pd.Series:
    """Compute equal-weighted composite z-score from individual factor z-scores.

    For each symbol, the mean is computed over whichever factors are non-NaN
    (denominator = count of available factors, not total). The result is then
    re-z-scored cross-sectionally.

    Args:
        z_scores: Mapping of factor name → cross-sectional z-score Series.
                  Typically the five factors: momentum, value, quality,
                  low_vol, size. NaN entries in any factor are excluded
                  from that symbol's mean (not treated as zero).

    Returns:
        Series indexed by the union of all factor Series indices.
        Symbols with NaN in every factor receive NaN.

    Example::

        >>> import pandas as pd
        >>> import numpy as np
        >>> rng = np.random.default_rng(0)
        >>> z = {f: pd.Series(rng.normal(size=10)) for f in
        ...      ["momentum", "value", "quality", "low_vol", "size"]}
        >>> result = compute_composite(z)
        >>> abs(float(result.dropna().mean())) < 1e-9
        True
    """
    if not z_scores:
        return pd.Series(dtype=float)

    df = pd.DataFrame(z_scores)

    raw = df.mean(axis=1, skipna=True)

    eligible = raw.dropna()
    if len(eligible) < 2:
        return pd.Series(np.nan, index=df.index, dtype=float)

    return zscore(eligible).reindex(df.index)
