"""Return attribution via Newey-West (HAC) OLS (spec §7.8, §14.4).

Locked output schema from spec §14.4.6 — field names must not change.
collinearity_warning = True when condition_number > 30 (§14.4.2).
Minimum 60 observations required; raises InsufficientDataError otherwise.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm
from pydantic import BaseModel

from spectraquant_core.errors import InsufficientDataError

_MIN_OBS = 60


class FactorBeta(BaseModel):
    """Per-factor regression output (spec §14.4.6)."""

    beta: float
    se: float
    ci_low: float
    ci_high: float
    pvalue: float
    significant: bool
    contribution_bps: float


class AttributionResult(BaseModel):
    """Full attribution result (spec §14.4.6). Field names are locked."""

    alpha: float
    alpha_pvalue: float
    alpha_ci_low: float
    alpha_ci_high: float
    betas: dict[str, FactorBeta]
    r_squared: float
    adj_r_squared: float
    n_obs: int
    condition_number: float
    collinearity_warning: bool
    hac_lags: int
    window_days: int
    residual_series: list[float]


def compute_attribution(
    portfolio_returns: pd.Series,
    factor_returns: pd.DataFrame,
    hac_lags: int = 5,
) -> AttributionResult:
    """OLS regression of portfolio returns on factor returns with HAC standard errors.

    Uses ``statsmodels.OLS`` with ``cov_type='HAC'`` and
    ``cov_kwds={'maxlags': hac_lags}``.  Collinearity is reported via
    ``condition_number`` and ``collinearity_warning`` (threshold > 30 per §14.4.2)
    but does NOT prevent computation.

    Args:
        portfolio_returns: Daily return Series, DatetimeIndex aligned with
                           ``factor_returns``.
        factor_returns:    DataFrame of daily factor long-short returns,
                           columns = factor names.  Must share index with
                           ``portfolio_returns``.
        hac_lags:          Newey-West lag truncation (default 5).

    Returns:
        AttributionResult with the locked schema from spec §14.4.6.

    Raises:
        InsufficientDataError: when fewer than 60 observations are available
                               after aligning ``portfolio_returns`` and
                               ``factor_returns``.

    Example::

        >>> import pandas as pd, numpy as np
        >>> rng = np.random.default_rng(0)
        >>> idx = pd.date_range("2023-01-01", periods=120, freq="B")
        >>> f = pd.DataFrame({"mom": rng.normal(0, 0.01, 120)}, index=idx)
        >>> r = f["mom"] * 1.0 + rng.normal(0, 0.001, 120)
        >>> result = compute_attribution(r, f)
        >>> abs(result.betas["mom"].beta - 1.0) < 0.2
        True
    """
    # --- align ---
    combined = pd.concat([portfolio_returns.rename("_ret"), factor_returns], axis=1).dropna()
    n_obs = len(combined)

    if n_obs < _MIN_OBS:
        raise InsufficientDataError(
            f"Attribution requires ≥ {_MIN_OBS} observations; got {n_obs}."
        )

    y = combined["_ret"]
    x_mat = combined.drop(columns="_ret")
    factor_names = list(x_mat.columns)

    x_const = sm.add_constant(x_mat, has_constant="add")

    model = sm.OLS(y, x_const)
    result = model.fit(cov_type="HAC", cov_kwds={"maxlags": hac_lags}, use_t=True)

    # Condition number on the factor matrix (without the constant column)
    x_arr = x_mat.to_numpy(dtype=float)
    cond = float(np.linalg.cond(x_arr))

    ci = result.conf_int(alpha=0.05)
    params = result.params
    pvalues = result.pvalues
    bse = result.bse

    # Alpha (intercept)
    alpha_val = float(params["const"])
    alpha_pval = float(pvalues["const"])
    alpha_ci_low = float(ci.loc["const", 0])
    alpha_ci_high = float(ci.loc["const", 1])

    # Per-factor betas
    betas: dict[str, FactorBeta] = {}
    for fname in factor_names:
        b = float(params[fname])
        se = float(bse[fname])
        p = float(pvalues[fname])
        ci_lo = float(ci.loc[fname, 0])
        ci_hi = float(ci.loc[fname, 1])
        # contribution_bps: beta × mean(factor_return) × 10_000
        contrib = b * float(x_mat[fname].mean()) * 10_000.0
        betas[fname] = FactorBeta(
            beta=b,
            se=se,
            ci_low=ci_lo,
            ci_high=ci_hi,
            pvalue=p,
            significant=p < 0.05,
            contribution_bps=contrib,
        )

    return AttributionResult(
        alpha=alpha_val,
        alpha_pvalue=alpha_pval,
        alpha_ci_low=alpha_ci_low,
        alpha_ci_high=alpha_ci_high,
        betas=betas,
        r_squared=float(result.rsquared),
        adj_r_squared=float(result.rsquared_adj),
        n_obs=n_obs,
        condition_number=cond,
        collinearity_warning=cond > 30.0,
        hac_lags=hac_lags,
        window_days=n_obs,
        residual_series=result.resid.tolist(),
    )
