"""Tests for price-only factors: momentum, low_vol, size."""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from spectraquant_core.factors import compute_low_vol, compute_momentum, compute_size
from spectraquant_core.normalize import zscore

AS_OF = date(2024, 12, 31)


# ---------------------------------------------------------------------------
# compute_momentum
# ---------------------------------------------------------------------------


class TestComputeMomentum:
    def test_uptrend_symbol_large_positive(self, prices_fixture: pd.DataFrame) -> None:
        """SYM000 is a monotonic up-trend: 12-1 momentum must be large positive."""
        result = compute_momentum(prices_fixture, AS_OF)
        val = float(result["SYM000"])
        assert val > 0.20, f"Expected momentum > 20 %, got {val:.4f}"

    def test_flat_symbol_near_zero(self, prices_fixture: pd.DataFrame) -> None:
        """SYM001 is flat (constant price): 12-1 momentum must be exactly 0."""
        result = compute_momentum(prices_fixture, AS_OF)
        assert abs(float(result["SYM001"])) < 1e-9

    def test_index_covers_full_universe(self, prices_fixture: pd.DataFrame) -> None:
        result = compute_momentum(prices_fixture, AS_OF)
        assert list(result.index) == list(prices_fixture.columns)

    def test_ineligible_symbol_is_nan_not_dropped(
        self, prices_fixture: pd.DataFrame
    ) -> None:
        """Symbol with < 240 valid prices in the window → NaN, not missing from index."""
        sparse = prices_fixture.copy()
        col = sparse.columns.get_loc("SYM000")
        sparse.iloc[:-50, col] = np.nan  # only 50 valid rows remain (< 240)
        result = compute_momentum(sparse, AS_OF)
        assert pd.isna(result["SYM000"])
        assert "SYM000" in result.index  # entry kept

    def test_insufficient_total_history_returns_all_nan(self) -> None:
        """Fewer than 252 rows in history → all NaN."""
        dates = pd.bdate_range(end="2024-12-31", periods=100)
        prices = pd.DataFrame({"A": np.linspace(100, 200, 100)}, index=dates)
        result = compute_momentum(prices, AS_OF)
        assert result.isna().all()


# ---------------------------------------------------------------------------
# compute_low_vol
# ---------------------------------------------------------------------------


class TestComputeLowVol:
    def test_zero_std_is_max_after_zscore(self, prices_fixture: pd.DataFrame) -> None:
        """SYM002 has std=0 → raw low_vol=0.0 → highest z-score in the cross-section."""
        raw = compute_low_vol(prices_fixture, AS_OF)
        z = zscore(raw.dropna())
        assert float(z["SYM002"]) > 1.0

    def test_volatile_symbol_negative_raw(self, prices_fixture: pd.DataFrame) -> None:
        """Random-walk symbols have positive std → raw low_vol < 0."""
        raw = compute_low_vol(prices_fixture, AS_OF)
        assert float(raw["SYM003"]) < 0.0

    def test_index_covers_full_universe(self, prices_fixture: pd.DataFrame) -> None:
        result = compute_low_vol(prices_fixture, AS_OF)
        assert list(result.index) == list(prices_fixture.columns)

    def test_ineligible_symbol_is_nan_not_dropped(
        self, prices_fixture: pd.DataFrame
    ) -> None:
        sparse = prices_fixture.copy()
        col = sparse.columns.get_loc("SYM005")
        sparse.iloc[:-50, col] = np.nan
        result = compute_low_vol(sparse, AS_OF)
        assert pd.isna(result["SYM005"])
        assert "SYM005" in result.index

    def test_insufficient_total_history_returns_all_nan(self) -> None:
        dates = pd.bdate_range(end="2024-12-31", periods=100)
        prices = pd.DataFrame({"A": [100.0] * 100}, index=dates)
        result = compute_low_vol(prices, AS_OF)
        assert result.isna().all()


# ---------------------------------------------------------------------------
# compute_size
# ---------------------------------------------------------------------------


class TestComputeSize:
    def test_monotonically_decreasing_in_market_cap(self) -> None:
        """Larger market cap → more negative −log → lower size score."""
        caps = pd.Series([1e9, 5e9, 20e9, 100e9], index=["A", "B", "C", "D"])
        result = compute_size(caps)
        vals = result.tolist()
        assert vals[0] > vals[1] > vals[2] > vals[3]

    def test_known_value(self) -> None:
        """−log(e²) = −2.0."""
        caps = pd.Series([np.e**2], index=["X"])
        result = compute_size(caps)
        assert abs(float(result["X"]) - (-2.0)) < 1e-9

    def test_nan_for_zero_market_cap(self) -> None:
        caps = pd.Series([0.0, 1e9])
        result = compute_size(caps)
        assert pd.isna(result.iloc[0])
        assert not pd.isna(result.iloc[1])

    def test_nan_for_negative_market_cap(self) -> None:
        caps = pd.Series([-1e9, 1e9])
        result = compute_size(caps)
        assert pd.isna(result.iloc[0])

    def test_nan_preserved(self) -> None:
        caps = pd.Series([np.nan, 1e9])
        result = compute_size(caps)
        assert pd.isna(result.iloc[0])

    def test_small_cap_scores_higher_than_large_cap(self) -> None:
        caps = pd.Series({"BIG": 1e12, "SMALL": 1e9})
        result = compute_size(caps)
        assert float(result["SMALL"]) > float(result["BIG"])
