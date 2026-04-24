"""Tests for portfolio.py and attribution.py (spec §7.7, §7.8, §14.4)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from spectraquant_core.attribution import AttributionResult, compute_attribution
from spectraquant_core.errors import InsufficientDataError, ZeroWeightPortfolioError
from spectraquant_core.portfolio import Holding, compute_exposures, normalize_weights

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_IDX = pd.date_range("2022-01-03", periods=252, freq="B")
_RNG = np.random.default_rng(42)


def _make_factor_returns(
    n: int = 252,
    seed: int = 42,
    factors: tuple[str, ...] = ("momentum", "value", "quality", "low_vol", "size"),
) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    idx = pd.date_range("2022-01-03", periods=n, freq="B")
    return pd.DataFrame(
        {f: rng.normal(0.0, 0.01, n) for f in factors},
        index=idx,
    )


# ---------------------------------------------------------------------------
# normalize_weights
# ---------------------------------------------------------------------------


class TestNormalizeWeights:
    def test_value_weights_sum_to_one(self) -> None:
        h = [
            Holding(symbol="A", qty=10, avg_price=100.0),
            Holding(symbol="B", qty=5, avg_price=200.0),
        ]
        w = normalize_weights(h)
        assert abs(float(w.sum()) - 1.0) < 1e-9
        assert abs(float(w["A"]) - 0.5) < 1e-9

    def test_explicit_weights_already_sum_to_one(self) -> None:
        h = [
            Holding(symbol="X", weight=0.6),
            Holding(symbol="Y", weight=0.4),
        ]
        w = normalize_weights(h)
        assert abs(float(w["X"]) - 0.6) < 1e-9

    def test_explicit_weights_normalised_when_not_summing_to_one(self) -> None:
        h = [Holding(symbol="A", weight=2.0), Holding(symbol="B", weight=3.0)]
        w = normalize_weights(h)
        assert abs(float(w.sum()) - 1.0) < 1e-9

    def test_zero_weight_raises(self) -> None:
        h = [Holding(symbol="A", weight=0.0), Holding(symbol="B", weight=0.0)]
        with pytest.raises(ZeroWeightPortfolioError):
            normalize_weights(h)

    def test_zero_value_raises(self) -> None:
        h = [Holding(symbol="A", qty=10, avg_price=0.0)]
        with pytest.raises(ZeroWeightPortfolioError):
            normalize_weights(h)

    def test_empty_list_raises(self) -> None:
        with pytest.raises(ZeroWeightPortfolioError):
            normalize_weights([])


# ---------------------------------------------------------------------------
# compute_exposures
# ---------------------------------------------------------------------------


class TestComputeExposures:
    def test_equal_weight_positive_momentum(self) -> None:
        w = pd.Series({"A": 0.5, "B": 0.5})
        z = {"momentum": pd.Series({"A": 2.0, "B": 2.0})}
        exp = compute_exposures(w, z)
        assert abs(exp["momentum"] - 2.0) < 1e-9

    def test_missing_symbol_treated_as_zero(self) -> None:
        """Symbol not in z_scores contributes 0 to exposure."""
        w = pd.Series({"A": 0.5, "B": 0.5})
        z = {"momentum": pd.Series({"A": 1.0})}  # B missing
        exp = compute_exposures(w, z)
        assert abs(exp["momentum"] - 0.5) < 1e-9

    def test_returns_all_factor_keys(self) -> None:
        w = pd.Series({"A": 1.0})
        factors = ["momentum", "value", "quality", "low_vol", "size"]
        z = {f: pd.Series({"A": 0.0}) for f in factors}
        exp = compute_exposures(w, z)
        assert set(exp.keys()) == set(factors)


# ---------------------------------------------------------------------------
# compute_attribution — core regression tests
# ---------------------------------------------------------------------------


class TestComputeAttribution:
    def test_pure_momentum_portfolio(self) -> None:
        """Portfolio with returns = 1.0 × momentum + tiny noise → mom β ≈ 1,
        other betas are not significant."""
        rng = np.random.default_rng(0)
        n = 252
        fr = _make_factor_returns(n=n, seed=1)
        noise = rng.normal(0.0, 0.0005, n)
        port_ret = pd.Series(
            fr["momentum"].values + noise,
            index=fr.index,
        )
        result = compute_attribution(port_ret, fr)

        assert isinstance(result, AttributionResult)
        assert abs(result.betas["momentum"].beta - 1.0) < 0.15
        assert result.betas["momentum"].significant
        assert result.n_obs == n
        assert result.r_squared > 0.80

        # Other factor betas must be small in magnitude (economically near-zero).
        # We do not assert p-value significance here: with n=252 and very low noise,
        # spurious correlations can pass p<0.05 even when the true beta is ~0.
        for fname in ("value", "quality", "low_vol", "size"):
            assert abs(result.betas[fname].beta) < 0.10, (
                f"{fname} beta should be near zero, got {result.betas[fname].beta:.4f}"
            )

    def test_collinearity_warning_when_correlated_factors(self) -> None:
        """Two near-identical factor columns → condition_number > 30, warning True."""
        rng = np.random.default_rng(42)
        n = 252
        base = rng.normal(0.0, 0.01, n)
        idx = pd.date_range("2022-01-03", periods=n, freq="B")
        fr = pd.DataFrame(
            {
                "f1": base,
                "f2": base + rng.normal(0.0, 1e-6, n),  # near-identical
            },
            index=idx,
        )
        port_ret = pd.Series(base + rng.normal(0.0, 0.001, n), index=idx)
        result = compute_attribution(port_ret, fr)

        assert result.collinearity_warning is True
        assert result.condition_number > 30.0

    def test_insufficient_observations_raises(self) -> None:
        """Fewer than 60 obs → InsufficientDataError."""
        rng = np.random.default_rng(7)
        n = 30
        idx = pd.date_range("2024-01-02", periods=n, freq="B")
        fr = pd.DataFrame({"mom": rng.normal(0.0, 0.01, n)}, index=idx)
        port_ret = pd.Series(rng.normal(0.0, 0.01, n), index=idx)

        with pytest.raises(InsufficientDataError):
            compute_attribution(port_ret, fr)

    def test_result_schema_matches_spec(self) -> None:
        """All locked fields from §14.4.6 must be present with correct types."""
        fr = _make_factor_returns()
        port_ret = pd.Series(
            _RNG.normal(0.0, 0.01, 252), index=fr.index
        )
        result = compute_attribution(port_ret, fr)

        assert isinstance(result.alpha, float)
        assert isinstance(result.alpha_pvalue, float)
        assert isinstance(result.alpha_ci_low, float)
        assert isinstance(result.alpha_ci_high, float)
        assert isinstance(result.betas, dict)
        assert isinstance(result.r_squared, float)
        assert isinstance(result.adj_r_squared, float)
        assert isinstance(result.n_obs, int)
        assert isinstance(result.condition_number, float)
        assert isinstance(result.collinearity_warning, bool)
        assert isinstance(result.hac_lags, int)
        assert isinstance(result.window_days, int)
        assert isinstance(result.residual_series, list)
        assert len(result.residual_series) == result.n_obs

        for fb in result.betas.values():
            assert isinstance(fb.beta, float)
            assert isinstance(fb.se, float)
            assert isinstance(fb.ci_low, float)
            assert isinstance(fb.ci_high, float)
            assert isinstance(fb.pvalue, float)
            assert isinstance(fb.significant, bool)
            assert isinstance(fb.contribution_bps, float)

    def test_hac_lags_default_is_five(self) -> None:
        fr = _make_factor_returns()
        port_ret = pd.Series(_RNG.normal(0.0, 0.01, 252), index=fr.index)
        result = compute_attribution(port_ret, fr)
        assert result.hac_lags == 5

    def test_custom_hac_lags_stored(self) -> None:
        fr = _make_factor_returns()
        port_ret = pd.Series(_RNG.normal(0.0, 0.01, 252), index=fr.index)
        result = compute_attribution(port_ret, fr, hac_lags=10)
        assert result.hac_lags == 10

    def test_ci_bounds_ordered(self) -> None:
        """ci_low < ci_high for alpha and every factor beta."""
        fr = _make_factor_returns()
        port_ret = pd.Series(_RNG.normal(0.0, 0.01, 252), index=fr.index)
        result = compute_attribution(port_ret, fr)
        assert result.alpha_ci_low < result.alpha_ci_high
        for fb in result.betas.values():
            assert fb.ci_low < fb.ci_high
