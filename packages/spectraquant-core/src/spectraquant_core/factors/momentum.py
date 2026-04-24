"""12-1 month cross-sectional momentum factor.

Formula (spec §7.1): return(t-21) / return(t-252) − 1, where t is as_of.
Eligibility: ≥ 240 non-NaN prices in the trailing 252-day window.
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd


def compute_momentum(prices: pd.DataFrame, as_of: date) -> pd.Series:
    """Compute raw 12-1 momentum for every symbol as of a given date.

    Args:
        prices: Wide DataFrame — index = trading dates (DatetimeIndex),
                columns = symbol identifiers.
        as_of:  Reference date. Only rows with index ≤ as_of are used.

    Returns:
        Series indexed by symbol. Ineligible symbols (< 240 valid prices
        in the trailing 252 rows) are set to NaN; the index entry is kept.

    Example::

        >>> import pandas as pd
        >>> from datetime import date
        >>> dates = pd.bdate_range(end="2024-12-31", periods=260)
        >>> prices = pd.DataFrame({"A": [100.0 + i for i in range(260)]}, index=dates)
        >>> result = compute_momentum(prices, date(2024, 12, 31))
        >>> float(result["A"]) > 0
        True
    """
    ts_asof = pd.Timestamp(as_of)
    hist = prices.loc[prices.index <= ts_asof].sort_index()

    if len(hist) < 252:
        return pd.Series(np.nan, index=prices.columns, dtype=float)

    window = hist.iloc[-252:]
    valid_counts = window.notna().sum()

    p_12m = hist.iloc[-252]
    p_1m = hist.iloc[-21]

    # Replace zero base prices with NaN to avoid inf returns
    p_12m_safe = p_12m.where(p_12m != 0)
    raw = (p_1m / p_12m_safe) - 1.0

    return raw.where(valid_counts >= 240)
