"""Tests for fundamentals-driven factors: value, quality, composite.

Fixture seed: np.random.default_rng(42).
score_date: 2024-12-31.

Edge-case symbol map
  SYM000 — negative PE ratio              → PE gets rank_pct = 0.05 (worst decile)
  SYM001 — only 1 of 3 value inputs       → value score = NaN
  SYM002 — period_end 95 days before score_date (stale) → value score = NaN
  SYM003 — ROE = 0.0                      → valid, not treated as missing
  SYM004 — 6 EPS quarters (2 missing)    → CV computed with UserWarning
"""

from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from spectraquant_core.factors import (
    compute_composite,
    compute_quality,
    compute_value,
)

SCORE_DATE = date(2024, 12, 31)
N = 50

# ---------------------------------------------------------------------------
# Shared symbol list
# ---------------------------------------------------------------------------

SYMBOLS = [f"SYM{i:03d}" for i in range(N)]

SYM_NEG_PE = "SYM000"
SYM_ONLY1 = "SYM001"
SYM_STALE = "SYM002"
SYM_ROE0 = "SYM003"
SYM_MISSING_Q = "SYM004"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def value_fundamentals() -> pd.DataFrame:
    """50-symbol fundamentals for value factor.  Most symbols are valid;
    SYM000/001/002 cover the three key edge cases."""
    rng = np.random.default_rng(42)

    pe = rng.uniform(5.0, 30.0, N)
    pb = rng.uniform(0.5, 5.0, N)
    ev = rng.uniform(3.0, 20.0, N)
    days_ago = rng.integers(10, 85, N)
    period_ends = [SCORE_DATE - timedelta(days=int(d)) for d in days_ago]

    # SYM000: negative PE
    pe[0] = -5.0

    # SYM001: only pb_ratio present (1 of 3)
    pe[1] = float("nan")
    ev[1] = float("nan")

    # SYM002: stale — 95 days before score_date
    period_ends[2] = SCORE_DATE - timedelta(days=95)

    return pd.DataFrame(
        {
            "symbol_id": SYMBOLS,
            "period_end": period_ends,
            "pe_ratio": pe,
            "pb_ratio": pb,
            "ev_ebitda": ev,
        }
    )


@pytest.fixture(scope="module")
def quality_fundamentals() -> pd.DataFrame:
    """50-symbol roe + debt_to_equity for quality factor."""
    rng = np.random.default_rng(42)
    roe = rng.uniform(0.05, 0.30, N)
    de = rng.uniform(0.1, 1.5, N)

    # SYM003: ROE exactly 0.0 (valid, not missing)
    roe[3] = 0.0

    return pd.DataFrame(
        {"symbol_id": SYMBOLS, "roe": roe, "debt_to_equity": de}
    )


@pytest.fixture(scope="module")
def quality_eps_full() -> pd.DataFrame:
    """8 quarters of EPS history for all 50 symbols (no warnings)."""
    rng = np.random.default_rng(42)
    rows = []
    for sym in SYMBOLS:
        base = abs(rng.normal(1.0, 0.1))
        for q in range(8):
            rows.append(
                {
                    "symbol": sym,
                    "period_end": SCORE_DATE - timedelta(days=90 * (8 - q)),
                    "eps_ttm": base + rng.normal(0.0, 0.05),
                }
            )
    return pd.DataFrame(rows)


@pytest.fixture(scope="module")
def quality_eps_sparse(quality_eps_full: pd.DataFrame) -> pd.DataFrame:
    """Same as full but SYM004 has only 6 quarters (2 rows removed)."""
    mask = (quality_eps_full["symbol"] == SYM_MISSING_Q)
    drop_idx = quality_eps_full[mask].index[:2]
    return quality_eps_full.drop(index=drop_idx).reset_index(drop=True)


# ---------------------------------------------------------------------------
# compute_value tests
# ---------------------------------------------------------------------------


class TestComputeValue:
    def test_negative_pe_gets_worst_decile_and_is_eligible(
        self, value_fundamentals: pd.DataFrame
    ) -> None:
        """SYM000 has negative PE — it is replaced with rank_pct=0.05 and
        still counts toward the 2-of-3 threshold (has all 3 inputs)."""
        result = compute_value(value_fundamentals, SCORE_DATE)
        assert not pd.isna(result[SYM_NEG_PE]), "negative-PE symbol should be eligible"

    def test_negative_pe_scores_lower_than_positive_pe(
        self, value_fundamentals: pd.DataFrame
    ) -> None:
        """Assigning rank_pct=0.05 to negative PE should produce a below-median score."""
        result = compute_value(value_fundamentals, SCORE_DATE)
        median_score = float(result.dropna().median())
        assert float(result[SYM_NEG_PE]) < median_score

    def test_only_one_input_is_nan(self, value_fundamentals: pd.DataFrame) -> None:
        """SYM001 has only pb_ratio (1 of 3) → must be NaN; index entry kept."""
        result = compute_value(value_fundamentals, SCORE_DATE)
        assert pd.isna(result[SYM_ONLY1])
        assert SYM_ONLY1 in result.index

    def test_stale_symbol_is_nan(self, value_fundamentals: pd.DataFrame) -> None:
        """SYM002 has period_end 95 days before score_date → stale → NaN."""
        result = compute_value(value_fundamentals, SCORE_DATE)
        assert pd.isna(result[SYM_STALE])
        assert SYM_STALE in result.index

    def test_index_covers_full_input_universe(
        self, value_fundamentals: pd.DataFrame
    ) -> None:
        result = compute_value(value_fundamentals, SCORE_DATE)
        assert set(result.index) == set(SYMBOLS)

    def test_eligible_symbols_are_valid_zscore(
        self, value_fundamentals: pd.DataFrame
    ) -> None:
        """Eligible subset should have mean ≈ 0 and std ≈ 1."""
        result = compute_value(value_fundamentals, SCORE_DATE)
        eligible = result.dropna()
        assert abs(float(eligible.mean())) < 1e-9
        assert abs(float(eligible.std(ddof=1)) - 1.0) < 1e-6

    def test_multiple_periods_uses_most_recent(self) -> None:
        """When a symbol has two rows, the most recent valid one is used."""
        df = pd.DataFrame(
            {
                "symbol_id": ["X", "X", "Y"],
                "period_end": [
                    SCORE_DATE - timedelta(days=30),
                    SCORE_DATE - timedelta(days=60),
                    SCORE_DATE - timedelta(days=30),
                ],
                "pe_ratio": [10.0, 20.0, 15.0],
                "pb_ratio": [1.0, 2.0, 1.5],
                "ev_ebitda": [5.0, 8.0, 6.0],
            }
        )
        result = compute_value(df, SCORE_DATE)
        assert result.notna().all()

    def test_staleness_boundary_exactly_90_days(self) -> None:
        """period_end exactly 90 days before score_date is NOT stale (≤ 90 inclusive).
        91 days is stale. Needs >= 2 valid symbols to produce a z-score."""
        df = pd.DataFrame(
            {
                "symbol_id": ["A", "B", "C"],
                "period_end": [
                    SCORE_DATE - timedelta(days=90),   # valid (boundary)
                    SCORE_DATE - timedelta(days=30),   # valid
                    SCORE_DATE - timedelta(days=91),   # stale
                ],
                "pe_ratio": [15.0, 20.0, 25.0],
                "pb_ratio": [2.0, 2.5, 3.0],
                "ev_ebitda": [8.0, 10.0, 12.0],
            }
        )
        result = compute_value(df, SCORE_DATE)
        assert not pd.isna(result["A"])
        assert not pd.isna(result["B"])
        assert pd.isna(result["C"])


# ---------------------------------------------------------------------------
# compute_quality tests
# ---------------------------------------------------------------------------


class TestComputeQuality:
    def test_roe_zero_is_valid_not_missing(
        self, quality_fundamentals: pd.DataFrame, quality_eps_full: pd.DataFrame
    ) -> None:
        """ROE = 0.0 must produce a valid quality score, not NaN."""
        result = compute_quality(quality_fundamentals, quality_eps_full)
        assert not pd.isna(result[SYM_ROE0])

    def test_missing_quarters_computes_cv_with_warning(
        self,
        quality_fundamentals: pd.DataFrame,
        quality_eps_sparse: pd.DataFrame,
    ) -> None:
        """SYM004 has 6 EPS quarters: CV is computed and a UserWarning is emitted."""
        with pytest.warns(UserWarning, match="6 EPS quarters"):
            result = compute_quality(quality_fundamentals, quality_eps_sparse)
        assert not pd.isna(result[SYM_MISSING_Q])

    def test_missing_roe_produces_nan(
        self, quality_fundamentals: pd.DataFrame, quality_eps_full: pd.DataFrame
    ) -> None:
        fund = quality_fundamentals.copy()
        # Inject missing ROE for SYM010
        idx = fund[fund["symbol_id"] == "SYM010"].index[0]
        fund.loc[idx, "roe"] = float("nan")
        result = compute_quality(fund, quality_eps_full)
        assert pd.isna(result["SYM010"])
        assert "SYM010" in result.index

    def test_missing_de_produces_nan(
        self, quality_fundamentals: pd.DataFrame, quality_eps_full: pd.DataFrame
    ) -> None:
        fund = quality_fundamentals.copy()
        idx = fund[fund["symbol_id"] == "SYM011"].index[0]
        fund.loc[idx, "debt_to_equity"] = float("nan")
        result = compute_quality(fund, quality_eps_full)
        assert pd.isna(result["SYM011"])

    def test_missing_eps_symbol_produces_nan(
        self, quality_fundamentals: pd.DataFrame, quality_eps_full: pd.DataFrame
    ) -> None:
        """Remove all EPS rows for SYM012 → quality is NaN."""
        eps = quality_eps_full[quality_eps_full["symbol"] != "SYM012"].copy()
        result = compute_quality(quality_fundamentals, eps)
        assert pd.isna(result["SYM012"])

    def test_index_covers_full_universe(
        self, quality_fundamentals: pd.DataFrame, quality_eps_full: pd.DataFrame
    ) -> None:
        result = compute_quality(quality_fundamentals, quality_eps_full)
        assert set(result.index) == set(SYMBOLS)

    def test_eligible_subset_is_valid_zscore(
        self, quality_fundamentals: pd.DataFrame, quality_eps_full: pd.DataFrame
    ) -> None:
        result = compute_quality(quality_fundamentals, quality_eps_full)
        eligible = result.dropna()
        assert abs(float(eligible.mean())) < 1e-9
        assert abs(float(eligible.std(ddof=1)) - 1.0) < 1e-6


# ---------------------------------------------------------------------------
# compute_composite tests
# ---------------------------------------------------------------------------


class TestComputeComposite:
    @pytest.fixture
    def full_z_scores(self) -> dict[str, pd.Series]:
        rng = np.random.default_rng(42)
        return {
            f: pd.Series(rng.normal(size=N), index=SYMBOLS)
            for f in ["momentum", "value", "quality", "low_vol", "size"]
        }

    def test_result_is_valid_zscore(
        self, full_z_scores: dict[str, pd.Series]
    ) -> None:
        """Composite of 50 symbols with no NaN must be mean=0, std=1 exactly."""
        result = compute_composite(full_z_scores)
        non_nan = result.dropna()
        assert abs(float(non_nan.mean())) < 1e-9
        assert abs(float(non_nan.std(ddof=1)) - 1.0) < 1e-6

    def test_missing_factor_excluded_from_mean_not_zeroed(self) -> None:
        """A symbol missing 'value' should get mean over the other 4 factors."""
        syms = ["A", "B", "C"]
        z = {
            "momentum": pd.Series([1.0, 0.0, -1.0], index=syms),
            "value": pd.Series([1.0, np.nan, -1.0], index=syms),
            "quality": pd.Series([0.5, 0.5, -0.5], index=syms),
            "low_vol": pd.Series([0.5, -0.5, 0.5], index=syms),
            "size": pd.Series([-0.5, 0.5, -0.5], index=syms),
        }
        result = compute_composite(z)
        # B is missing value but has 4 other factors → not NaN
        assert not pd.isna(result["B"])

    def test_all_nan_symbol_is_nan(self) -> None:
        syms = ["A", "B"]
        z = {
            "momentum": pd.Series([1.0, np.nan], index=syms),
            "value": pd.Series([0.5, np.nan], index=syms),
            "quality": pd.Series([-0.5, np.nan], index=syms),
            "low_vol": pd.Series([0.0, np.nan], index=syms),
            "size": pd.Series([0.0, np.nan], index=syms),
        }
        result = compute_composite(z)
        assert pd.isna(result["B"])

    def test_empty_input_returns_empty(self) -> None:
        result = compute_composite({})
        assert result.empty

    def test_index_covers_union_of_all_inputs(self) -> None:
        z = {
            "momentum": pd.Series([1.0, 0.0], index=["A", "B"]),
            "value": pd.Series([0.5, -0.5, 1.0], index=["A", "B", "C"]),
        }
        result = compute_composite(z)
        assert set(result.index) == {"A", "B", "C"}
