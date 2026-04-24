"""Golden-fixture tests for spectraquant_core.normalize.

All tests are deterministic. Random data uses np.random.default_rng(seed=42).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from spectraquant_core.normalize import rank_pct, winsorize, zscore

# ---------------------------------------------------------------------------
# winsorize
# ---------------------------------------------------------------------------


class TestWinsorize:
    def test_golden_clip_values(self) -> None:
        """Known 100-element series: clipped values must lie in [lo, hi]."""
        rng = np.random.default_rng(42)
        x = pd.Series(rng.normal(size=100))
        result = winsorize(x, lower=0.05, upper=0.95)
        lo = float(x.quantile(0.05))
        hi = float(x.quantile(0.95))
        assert float(result.min()) >= lo - 1e-9
        assert float(result.max()) <= hi + 1e-9

    def test_interior_values_unchanged(self) -> None:
        """Values inside the quantile range are untouched."""
        x = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
        result = winsorize(x, lower=0.10, upper=0.90)
        # median value 3.0 must be unchanged
        assert abs(float(result.iloc[2]) - 3.0) < 1e-9

    def test_nan_preserved(self) -> None:
        x = pd.Series([1.0, np.nan, 3.0, 4.0, 5.0])
        result = winsorize(x)
        assert result.isna().sum() == 1
        assert result.isna().iloc[1]

    def test_empty_series(self) -> None:
        x: pd.Series = pd.Series([], dtype=float)
        result = winsorize(x)
        assert result.empty

    def test_all_equal_values(self) -> None:
        """All-equal series: every value stays the same."""
        x = pd.Series([5.0] * 10)
        result = winsorize(x)
        assert (result == 5.0).all()

    def test_non_numeric_raises(self) -> None:
        x: pd.Series = pd.Series(["a", "b", "c"])
        with pytest.raises(TypeError):
            winsorize(x)


# ---------------------------------------------------------------------------
# zscore
# ---------------------------------------------------------------------------


class TestZscore:
    def test_golden_three_point(self) -> None:
        """[10, 20, 30] → [-1, 0, 1] (mean=20, std=10)."""
        x = pd.Series([10.0, 20.0, 30.0])
        result = zscore(x)
        expected = pd.Series([-1.0, 0.0, 1.0])
        pd.testing.assert_series_equal(
            result.round(6), expected.round(6), check_names=False
        )

    def test_mean_zero_std_one(self) -> None:
        rng = np.random.default_rng(42)
        x = pd.Series(rng.normal(loc=50, scale=10, size=200))
        result = zscore(x)
        assert abs(float(result.mean())) < 1e-10
        assert abs(float(result.std(ddof=1)) - 1.0) < 1e-6

    def test_nan_preserved(self) -> None:
        x = pd.Series([1.0, np.nan, 3.0])
        result = zscore(x)
        assert result.isna().iloc[1]
        assert not result.isna().iloc[0]
        assert not result.isna().iloc[2]

    def test_empty_series(self) -> None:
        x: pd.Series = pd.Series([], dtype=float)
        result = zscore(x)
        assert result.empty

    def test_constant_returns_all_nan(self) -> None:
        """Constant input → std == 0 → all NaN (not divide-by-zero)."""
        x = pd.Series([7.0, 7.0, 7.0, 7.0])
        result = zscore(x)
        assert result.isna().all()

    def test_non_numeric_raises(self) -> None:
        x: pd.Series = pd.Series(["a", "b"])
        with pytest.raises(TypeError):
            zscore(x)


# ---------------------------------------------------------------------------
# rank_pct
# ---------------------------------------------------------------------------


class TestRankPct:
    def test_golden_three_point(self) -> None:
        """[10, 20, 30] → [1/3, 2/3, 1.0]."""
        x = pd.Series([10.0, 20.0, 30.0])
        result = rank_pct(x)
        expected = pd.Series([1 / 3, 2 / 3, 1.0])
        pd.testing.assert_series_equal(
            result.round(6), expected.round(6), check_names=False
        )

    def test_nan_preserved(self) -> None:
        x = pd.Series([1.0, np.nan, 3.0])
        result = rank_pct(x)
        assert result.isna().iloc[1]
        assert not result.isna().iloc[0]
        assert not result.isna().iloc[2]

    def test_empty_series(self) -> None:
        x: pd.Series = pd.Series([], dtype=float)
        result = rank_pct(x)
        assert result.empty

    def test_ties_averaged(self) -> None:
        """Tied values receive the average of their rank positions."""
        x = pd.Series([1.0, 1.0, 3.0])
        result = rank_pct(x)
        # ranks 1 and 2 are tied → average rank = 1.5, pct = 1.5/3 = 0.5
        assert abs(float(result.iloc[0]) - 0.5) < 1e-9
        assert abs(float(result.iloc[1]) - 0.5) < 1e-9
        assert abs(float(result.iloc[2]) - 1.0) < 1e-9

    def test_output_bounds(self) -> None:
        rng = np.random.default_rng(99)
        x = pd.Series(rng.normal(size=50))
        result = rank_pct(x)
        assert float(result.min()) > 0.0
        assert float(result.max()) <= 1.0 + 1e-9

    def test_non_numeric_raises(self) -> None:
        x: pd.Series = pd.Series(["x", "y"])
        with pytest.raises(TypeError):
            rank_pct(x)
