"""Value factor: PE, PB, EV/EBITDA equal-weighted composite (spec §7.2, §14.5).

Staleness rule (§14.5.3): keep most recent period_end ≤ score_date and within 90 days.
Neg/zero rule (§14.5.2): assign rank_pct = 0.05 (worst decile); counts toward 2-of-3.
Minimum inputs (§14.5.1): require ≥ 2 of 3 non-null inputs; else NaN.
NaN sentinel rule (§14.5.7): return NaN for ineligible symbols; do not write sentinels.
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from spectraquant_core.normalize import rank_pct, zscore


def _normalize_component(raw: pd.Series) -> pd.Series:
    """Rank-pct with neg/zero → 0.05, then cross-sectional z-score.

    Example::

        >>> import pandas as pd
        >>> _normalize_component(pd.Series([-1.0, 5.0, 10.0, 15.0]))  # doctest: +SKIP
    """
    neg_zero = (raw <= 0) & raw.notna()
    ranks = rank_pct(raw)
    ranks = ranks.where(~neg_zero, other=0.05)
    return zscore(ranks)


def compute_value(fundamentals: pd.DataFrame, score_date: date) -> pd.Series:
    """Compute value factor z-scores for a cross-section of symbols.

    Args:
        fundamentals: DataFrame with columns symbol_id, period_end, pe_ratio,
                      pb_ratio, ev_ebitda. Multiple rows per symbol accepted.
        score_date:   Reference date for staleness filter.

    Returns:
        Series indexed by symbol_id. Stale symbols or symbols with < 2 of 3
        non-null inputs receive NaN; their index entries are preserved.

    Example::

        >>> import pandas as pd
        >>> from datetime import date, timedelta
        >>> df = pd.DataFrame({
        ...     "symbol_id": ["A", "B"],
        ...     "period_end": [date(2024, 11, 1), date(2024, 11, 1)],
        ...     "pe_ratio": [15.0, 12.0], "pb_ratio": [2.0, 1.5], "ev_ebitda": [8.0, 7.0],
        ... })
        >>> result = compute_value(df, date(2024, 12, 31))
        >>> result.notna().all()
        True
    """
    all_symbols: pd.Index = pd.Index(fundamentals["symbol_id"].unique())

    filt = fundamentals.copy()
    filt["period_end"] = pd.to_datetime(filt["period_end"])
    score_ts = pd.Timestamp(score_date)

    valid = filt[
        (filt["period_end"] <= score_ts)
        & ((score_ts - filt["period_end"]).dt.days <= 90)
    ]
    if valid.empty:
        return pd.Series(np.nan, index=all_symbols, dtype=float)

    latest = valid.sort_values("period_end").groupby("symbol_id").last()

    available = latest[["pe_ratio", "pb_ratio", "ev_ebitda"]].notna().sum(axis=1)

    pe_z = _normalize_component(latest["pe_ratio"])
    pb_z = _normalize_component(latest["pb_ratio"])
    ev_z = _normalize_component(latest["ev_ebitda"])

    z_df = pd.DataFrame({"pe": pe_z, "pb": pb_z, "ev": ev_z})
    raw_score = z_df.mean(axis=1, skipna=True)
    raw_score = raw_score.where(available >= 2)

    eligible = raw_score.dropna()
    if len(eligible) < 2:
        return pd.Series(np.nan, index=all_symbols, dtype=float)

    return zscore(eligible).reindex(all_symbols)
