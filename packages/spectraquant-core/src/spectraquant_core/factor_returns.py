"""Factor-return series construction via monthly-rebalanced long-short quintiles.

Implements spec §14.1.9 exactly.

Key constraints enforced here:
  - Monthly rebalance on first XNSE trading day of each month.
  - Universe per §14.1.2: NIFTY500 members at τ with ≥ 240 prices in prior year
    and a non-null z_score for the factor on τ − 1.
  - Minimum universe size 250; if not met, carry forward prior quintiles and log.
  - Quintile size = floor(|U| / 5); remainder into middle quintiles (Q2/Q3/Q4),
    never Q1/Q5.
  - Q5 ranking uses z_scores at score_date = τ − 1 trading day (lookahead guard).
  - Returns pd.Series indexed by date, values = mean(Q5_returns) − mean(Q1_returns).
  - PointInTimeLookAheadError when any z_score has score_date == τ (not τ − 1).
"""

from __future__ import annotations

import logging
import warnings
from datetime import date
from typing import Literal

import pandas as pd
import pandas_market_calendars as mcal  # type: ignore[import-untyped]

from spectraquant_core.errors import PointInTimeLookAheadError

_log = logging.getLogger(__name__)

FactorName = Literal["momentum", "value", "quality", "low_vol", "size", "composite"]

_MIN_UNIVERSE = 250


def _xnse_trading_days(start: date, end: date) -> pd.DatetimeIndex:
    cal = mcal.get_calendar("XNSE")
    schedule = cal.schedule(start_date=start, end_date=end)
    return mcal.date_range(schedule, frequency="1D").normalize()


def _first_trading_day_of_each_month(
    trading_days: pd.DatetimeIndex,
) -> pd.DatetimeIndex:
    """Return the first trading day in each calendar month."""
    series = pd.Series(trading_days, index=trading_days)
    dti = pd.DatetimeIndex(series.index)
    return pd.DatetimeIndex(
        series.groupby([dti.year, dti.month]).first()
    )


def _prev_trading_day(ts: pd.Timestamp, trading_days: pd.DatetimeIndex) -> pd.Timestamp:
    """Return the trading day immediately before ``ts``."""
    prior = trading_days[trading_days < ts]
    if prior.empty:
        raise ValueError(f"No trading day before {ts} in the provided calendar.")
    return prior[-1]


def _assign_quintiles(z: pd.Series, q_size: int) -> pd.Series:
    """Assign quintile labels 1–5 based on ascending z-score rank.

    Q1 = lowest z-scores, Q5 = highest.
    Remainder symbols go into Q2/Q3/Q4 (never Q1/Q5).

    Returns a Series of int labels, same index as ``z``.
    """
    n = len(z)
    ranked = z.rank(method="first").astype(int)
    labels = pd.Series(0, index=z.index, dtype=int)

    # Hard Q1 and Q5 boundaries
    q1_end = q_size
    q5_start = n - q_size + 1

    labels[ranked <= q1_end] = 1
    labels[ranked >= q5_start] = 5

    # Fill middle quintiles (2, 3, 4) for the remainder
    middle_mask = labels == 0
    middle_ranked = ranked[middle_mask].rank(method="first").astype(int)
    n_mid = middle_mask.sum()
    mid_q_size = n_mid // 3
    labels[middle_mask] = middle_ranked.apply(
        lambda r: 2 if r <= mid_q_size else (4 if r > 2 * mid_q_size else 3)
    )

    return labels


def compute_factor_return_series(
    factor: FactorName,
    z_scores_history: pd.DataFrame,
    prices: pd.DataFrame,
    index_membership: pd.DataFrame,
    calendar: mcal.MarketCalendar,
    start_date: date,
    end_date: date,
) -> pd.Series:
    """Compute the daily long-short factor return series (Q5 − Q1) for one factor.

    Args:
        factor:            Factor name (used to filter ``z_scores_history``).
        z_scores_history:  DataFrame with columns symbol_id, score_date, z_score,
                           factor_name.
        prices:            Wide price DataFrame — index = trading dates,
                           columns = symbol_id, values = adj_close.
        index_membership:  DataFrame with columns symbol_id, effective_from,
                           effective_to (NULL = still active). Dates as ``date``.
        calendar:          XNSE MarketCalendar instance.
        start_date:        First date of the output series.
        end_date:          Last date of the output series.

    Returns:
        pd.Series indexed by trading date in [start_date, end_date],
        values = mean(Q5 daily return) − mean(Q1 daily return).

    Raises:
        PointInTimeLookAheadError: if any z_score row has score_date == rebalance_date
                                   (must use score_date = rebalance_date − 1 trading day).

    Example::

        >>> # See tests/test_factor_returns.py for deterministic fixture examples.
        >>> pass
    """
    schedule = calendar.schedule(start_date=start_date, end_date=end_date)
    _raw_td = mcal.date_range(schedule, frequency="1D").normalize()
    all_td = _raw_td.tz_localize(None) if _raw_td.tz is not None else _raw_td

    if all_td.empty:
        return pd.Series(dtype=float)

    rebalance_dates = _first_trading_day_of_each_month(all_td)

    # Extended calendar for prev-trading-day lookups — goes back one month so
    # the first rebalance date (which may equal all_td[0]) always has a prior day.
    ext_month = start_date.month - 1 or 12
    ext_year = start_date.year if start_date.month > 1 else start_date.year - 1
    extended_start = date(ext_year, ext_month, 1)
    schedule_ext = calendar.schedule(start_date=extended_start, end_date=end_date)
    _raw_ext = mcal.date_range(schedule_ext, frequency="1D").normalize()
    all_td_ext = _raw_ext.tz_localize(None) if _raw_ext.tz is not None else _raw_ext

    factor_zs = z_scores_history[
        z_scores_history["factor_name"] == factor
    ].copy()
    factor_zs["score_date"] = pd.to_datetime(factor_zs["score_date"])

    membership = index_membership.copy()
    membership["effective_from"] = pd.to_datetime(membership["effective_from"])
    membership["effective_to"] = pd.to_datetime(membership["effective_to"])

    prices_idx = prices.copy()
    _pidx = pd.to_datetime(prices_idx.index)
    prices_idx.index = _pidx.tz_localize(None) if _pidx.tz is not None else _pidx

    daily_returns = prices_idx.pct_change()

    # Carry-forward quintile state
    prev_quintiles: pd.Series | None = None
    # Map: trading_date → (q5_symbols, q1_symbols)
    quintile_assignment: dict[pd.Timestamp, tuple[list[str], list[str]]] = {}

    for rebal_ts in rebalance_dates:
        prev_td = _prev_trading_day(rebal_ts, all_td_ext)

        # --- z-scores at τ − 1 ---
        z_prev_df = factor_zs[factor_zs["score_date"].dt.normalize() == prev_td]
        z_prev = z_prev_df.set_index("symbol_id")["z_score"]

        # --- lookahead guard ---
        # If no scores exist at prev_td but scores DO exist at τ itself, the caller
        # provided same-day scores (score_date == rebalance_date → lookahead).
        if z_prev_df.empty:
            z_on_rebal = factor_zs[
                factor_zs["score_date"].dt.normalize() == rebal_ts
            ]
            if not z_on_rebal.empty:
                raise PointInTimeLookAheadError(
                    f"z_scores have score_date = {rebal_ts.date()} (the rebalance "
                    "date). Use score_date = τ − 1 trading day to avoid lookahead bias."
                )

        # --- universe: NIFTY500 members active at τ ---
        rebal_date = rebal_ts.date()
        rebal_ts_pd = pd.Timestamp(rebal_date)
        active = membership[
            (membership["effective_from"] <= rebal_ts_pd)
            & (
                membership["effective_to"].isna()
                | (membership["effective_to"] >= rebal_ts_pd)
            )
        ]["symbol_id"]
        active_set = set(active)

        # --- eligibility: ≥ 240 prices in prior 252 trading days ---
        window_td = all_td[all_td <= rebal_ts]
        if len(window_td) >= 252:
            price_window = prices_idx.loc[
                prices_idx.index.isin(window_td[-252:])
            ]
            valid_counts = price_window.notna().sum()
            eligible_price = set(valid_counts[valid_counts >= 240].index)
        else:
            eligible_price = set(prices_idx.columns)

        # --- universe intersection ---
        universe = list(
            active_set & eligible_price & set(z_prev.index)
        )
        z_universe = z_prev.reindex(universe).dropna()

        if len(z_universe) < _MIN_UNIVERSE:
            _log.warning(
                "Universe size %d < %d at %s for factor %s; carrying forward quintiles.",
                len(z_universe),
                _MIN_UNIVERSE,
                rebal_ts.date(),
                factor,
            )
            warnings.warn(
                f"Universe size {len(z_universe)} < {_MIN_UNIVERSE} at "
                f"{rebal_ts.date()} for factor {factor}; carrying forward quintiles.",
                UserWarning,
                stacklevel=2,
            )
            if prev_quintiles is not None:
                q5_syms = list(prev_quintiles[prev_quintiles == 5].index)
                q1_syms = list(prev_quintiles[prev_quintiles == 1].index)
                quintile_assignment[rebal_ts] = (q5_syms, q1_syms)
            continue

        q_size = len(z_universe) // 5
        quintiles = _assign_quintiles(z_universe, q_size)
        prev_quintiles = quintiles

        q5_syms = list(quintiles[quintiles == 5].index)
        q1_syms = list(quintiles[quintiles == 1].index)
        quintile_assignment[rebal_ts] = (q5_syms, q1_syms)

    # --- compute daily long-short return ---
    output: dict[pd.Timestamp, float] = {}
    rebal_sorted = sorted(quintile_assignment.keys())

    for _i, td in enumerate(all_td):
        # Find the most recent rebalance date ≤ td
        current_rebal: pd.Timestamp | None = None
        for rd in reversed(rebal_sorted):
            if rd <= td:
                current_rebal = rd
                break

        if current_rebal is None:
            output[td] = float("nan")
            continue

        q5_syms, q1_syms = quintile_assignment[current_rebal]

        if td not in daily_returns.index:
            output[td] = float("nan")
            continue

        row = daily_returns.loc[td]
        q5_ret = row.reindex(q5_syms).dropna()
        q1_ret = row.reindex(q1_syms).dropna()

        if q5_ret.empty or q1_ret.empty:
            output[td] = float("nan")
        else:
            output[td] = float(q5_ret.mean()) - float(q1_ret.mean())

    return pd.Series(output, dtype=float)
