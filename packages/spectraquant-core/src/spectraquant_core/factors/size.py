"""Size factor: −log(market_cap).

Formula (spec §7.5). Smaller market cap → larger (more positive) score.
Inputs of 0 or below, and NaN, produce NaN outputs.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def compute_size(market_caps: pd.Series) -> pd.Series:
    """Compute the size factor for a cross-section of symbols.

    Args:
        market_caps: Series indexed by symbol, values in INR.
                     Zero, negative, and NaN values yield NaN output.

    Returns:
        Series indexed by symbol with value −log(market_cap).

    Example::

        >>> import math, pandas as pd
        >>> caps = pd.Series({"BIG": 1e12, "SMALL": 1e9})
        >>> result = compute_size(caps)
        >>> float(result["SMALL"]) > float(result["BIG"])  # small cap scores higher
        True
    """
    positive = market_caps.where(market_caps > 0)
    return -positive.apply(np.log)
