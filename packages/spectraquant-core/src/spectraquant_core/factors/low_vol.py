"""Low-volatility factor: −1 × std(daily_return, trailing 252 days).

Formula (spec §7.4). Higher score = lower realised volatility.
Eligibility: ≥ 240 non-NaN prices in the trailing 252-day window.
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd


def compute_low_vol(prices: pd.DataFrame, as_of: date) -> pd.Series:
    """Compute the low-volatility factor for every symbol as of a given date.

    Args:
        prices: Wide DataFrame — index = trading dates (DatetimeIndex),
                columns = symbol identifiers.
        as_of:  Reference date. Only rows with index ≤ as_of are used.

    Returns:
        Series indexed by symbol with value −std(daily_return).
        Ineligible symbols (< 240 valid prices in the trailing 252 rows)
        are set to NaN; the index entry is kept.

    Example::

        >>> import pandas as pd
        >>> from datetime import date
        >>> dates = pd.bdate_range(end="2024-12-31", periods=260)
        >>> prices = pd.DataFrame({"A": [100.0] * 260}, index=dates)
        >>> float(compute_low_vol(prices, date(2024, 12, 31))["A"])
        -0.0
    """
    ts_asof = pd.Timestamp(as_of)
    hist = prices.loc[prices.index <= ts_asof].sort_index()

    if len(hist) < 252:
        return pd.Series(np.nan, index=prices.columns, dtype=float)

    window = hist.iloc[-252:]
    valid_counts = window.notna().sum()

    daily_ret = window.pct_change().iloc[1:]
    vol = daily_ret.std(ddof=1)

    raw = -vol

    return raw.where(valid_counts >= 240)
