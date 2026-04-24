# PROMPTS.md — Day-by-Day Claude Code Prompts

Paste these into Claude Code one day at a time. Do not paste a day's prompt until the previous day's output is reviewed and committed. Each prompt is a complete session brief — Claude Code does not need you to explain context beyond what's in `CLAUDE.md` + `SPECTRAQUANT_RETAIL_SPEC.md`.

**How to use:** at the start of each day, open a fresh Claude Code session in the repo root. Paste the day's prompt. Review output before committing. Do not let Claude Code move to the next day's work in the same session.

---

## Day 1 — Monorepo scaffold + spectraquant-core skeleton

```
Goal: scaffold the monorepo per spec §8.1 and set up packages/spectraquant-core
with the first factor helpers (winsorize, z-score, rank).

Tasks:
1. Initialize the monorepo structure exactly as spec §8.1 shows. Create empty
   directories with .gitkeep where needed.
2. Create:
   - root package.json (name: spectraquant-retail, private: true, workspaces via pnpm)
   - pnpm-workspace.yaml (already committed — verify)
   - turbo.json (already committed — verify)
   - .nvmrc with 20
   - .python-version with 3.12
3. Scaffold packages/spectraquant-core:
   - pyproject.toml pinning pandas >= 2.2, numpy >= 2.0, statsmodels >= 0.14,
     pydantic >= 2, pandas-market-calendars, pytest, pytest-cov, mypy, ruff
   - src/spectraquant_core/__init__.py
   - src/spectraquant_core/normalize.py with three functions:
       def winsorize(x: pd.Series, lower: float = 0.01, upper: float = 0.99) -> pd.Series
       def zscore(x: pd.Series) -> pd.Series
       def rank_pct(x: pd.Series) -> pd.Series
     All three preserve NaN, handle empty input, raise on non-numeric.
   - src/spectraquant_core/errors.py with ZeroWeightPortfolioError,
     InsufficientDataError, InvalidUniverseError.
   - tests/test_normalize.py with golden fixtures covering:
       * known inputs → known outputs (6-decimal precision)
       * NaN preservation
       * empty series edge case
       * winsorize with all-equal values
4. Add a CI workflow (.github/workflows/ci.yml) that runs on every push:
       * pnpm install
       * uv pip install -e packages/spectraquant-core[dev]
       * pytest packages/spectraquant-core -q
       * ruff check packages/spectraquant-core
       * mypy packages/spectraquant-core
5. Write a one-page README.md at repo root: what this is, how to run tests,
   link to SPECTRAQUANT_RETAIL_SPEC.md.

Rules:
- No Streamlit, no Flask, no FastAPI in this package.
- No module-level side effects in any file under src/.
- Every function has a docstring with a minimal example.
- All tests are deterministic. Use np.random.default_rng(seed) if you need
  random data for fixtures.

Deliverable: one commit titled "feat(core): scaffold monorepo and normalize helpers"
that passes CI locally. Report what you did in ≤ 10 bullets.
```

---

## Day 2 — Momentum, low-vol, size factors

```
Goal: implement the three price-only factors: momentum, low_vol, size.

Context: read spec §7.1, §7.4, §7.5 for the exact formulas.

Tasks:
1. packages/spectraquant-core/src/spectraquant_core/data_models.py:
   Pydantic models for PriceFrame (symbol_id, trade_date, adj_close) and
   FundamentalsFrame (symbol_id, period_end, market_cap, pe_ratio, pb_ratio,
   ev_ebitda, roe, roce, debt_to_equity, eps_ttm).
2. src/spectraquant_core/factors/momentum.py:
       def compute_momentum(prices: pd.DataFrame, as_of: date) -> pd.Series
   - Input: wide DataFrame with dates as index, symbols as columns.
   - Output: Series indexed by symbol with raw 12-1 momentum.
   - Eligibility: drop symbols with < 240 valid prices in the window.
   - Must return NaN for ineligible symbols; do not drop the index entry.
3. src/spectraquant_core/factors/low_vol.py:
       def compute_low_vol(prices: pd.DataFrame, as_of: date) -> pd.Series
   - Computes -1 * std(daily_return, last 252d). Same eligibility rule.
4. src/spectraquant_core/factors/size.py:
       def compute_size(market_caps: pd.Series) -> pd.Series
   - Input: Series of market cap in INR indexed by symbol.
   - Output: -1 * log(market_cap), NaN preserved for missing/<=0.
5. Tests in packages/spectraquant-core/tests/test_factors_price.py:
   - Golden fixture: load tests/fixtures/prices_synthetic_252x50.csv
     (generate this CSV in a conftest fixture with a fixed seed, document
     the RNG approach).
   - Assert momentum for a known monotonic up-trend symbol is positive and large.
   - Assert momentum for a flat symbol is ~ 0.
   - Assert low_vol for a symbol with std=0 is +∞-bounded (large positive after z-score).
   - Assert size monotonically decreasing in market cap.
6. Wire into factors/__init__.py so downstream code imports:
       from spectraquant_core.factors import compute_momentum, compute_low_vol, compute_size

Rules:
- Use pandas-market-calendars XNSE calendar if you need trading-day arithmetic.
  Do not hand-roll holidays.
- No hard-coded date constants except the as_of parameter.
- No calls to yfinance or any external source in spectraquant-core.
- pandas 2.2-compatible only: no chained assignment, no .ix, no deprecated
  resample signatures. Run with warnings as errors in CI.

Deliverable: one commit "feat(core): momentum, low_vol, size factors" with
green CI. Summarize in ≤ 10 bullets.
```

---

## Day 3 — Value + Quality factors + composite

```
Goal: implement value and quality (both fundamentals-driven) and the composite.

Context: read spec §7.2, §7.3, §7.6. Also read §14.5 (value factor missing-input
rules and NULL propagation — supersedes the one-liner in CLAUDE.md).

Tasks:
1. src/spectraquant_core/factors/value.py:
       def compute_value(fundamentals: pd.DataFrame,
                         score_date: date) -> pd.Series
   - Input: fundamentals DataFrame with columns symbol_id, period_end, pe_ratio,
     pb_ratio, ev_ebitda (may have multiple rows per symbol across periods).
   - Apply §14.5.3 staleness filter first: for each symbol keep only the most
     recent row where period_end ≤ score_date AND score_date − period_end ≤ 90
     days. Symbols absent after this filter → all inputs NULL.
   - Handle negative/zero inputs per §14.5.2: assign rank_pct = 0.05 (worst
     decile) rather than dropping. These count toward the ≥2-of-3 threshold.
   - Require at least 2 of 3 non-null inputs per §14.5.1; else return NaN.
   - Normalize each available component via cross-sectional z-score, equal-weight
     mean over available inputs (denominator = count available, not 3), re-z-score.
   - Per §14.5.7: NaN symbols produce no row in factor_scores. Do not write
     sentinel values — the NOT NULL constraint enforces this.
2. src/spectraquant_core/factors/quality.py:
       def compute_quality(fundamentals: pd.DataFrame,
                           eps_history: pd.DataFrame) -> pd.Series
   - fundamentals columns: roe, debt_to_equity.
   - eps_history: DataFrame with columns symbol, period_end, eps_ttm covering
     last 8 quarters.
   - CV of EPS = std / |mean|. Invert (negative) so higher is better.
   - Require all 3 inputs; missing → NaN.
3. src/spectraquant_core/factors/composite.py:
       def compute_composite(z_scores: dict[str, pd.Series]) -> pd.Series
   - Input: {"momentum": series, "value": series, ...} all 5 factors.
   - Output: equal-weighted mean of z-scores, then re-z-scored.
   - If a symbol has NaN in any factor, that factor is excluded from its mean
     (treat as missing, not zero).
4. Extend tests/test_factors_fundamentals.py:
   - Fixture with 50 synthetic symbols covering all edge cases:
     * negative PE (should get worst-decile rank)
     * only 1 of 3 value inputs (should be NaN)
     * ROE=0 (valid, not missing)
     * missing 2 of 8 quarters (should still compute CV with warning)
     * fundamentals row with period_end 95 days before score_date (should be
       NaN due to staleness — symbol receives no factor_scores row)
   - Assert composite is a valid z-score (mean~0, std~1 within tolerance).

Rules:
- Same extraction rules as Day 1–2: no side effects, deterministic, typed.
- NaN semantics are tested explicitly — do not use sentinel values like -999.

Deliverable: one commit "feat(core): value, quality, composite factors".
Report edge case handling in ≤ 10 bullets.
```

---

## Day 4 — Portfolio exposures + attribution (Newey-West OLS)

```
Goal: close the core math by adding portfolio exposure computation and return
attribution via Newey-West OLS.

Context: spec §7.7, §7.8, and §14.4 (collinearity handling — locked decisions on
condition number threshold, rejection of ridge, n.s. badge definition, and the
AttributionResult pydantic shape). §14.4 supersedes the Day 4 inline spec notes.

Tasks:
1. src/spectraquant_core/portfolio.py:
       def normalize_weights(holdings: list[Holding]) -> pd.Series
   - Holding is a pydantic model: symbol, qty, avg_price, weight (optional).
   - If weights are given and sum to 1 (±0.01), use them.
   - If quantities + avg_price given, compute weights from value.
   - If total weight is 0, raise ZeroWeightPortfolioError.
   - Return Series indexed by symbol.

       def compute_exposures(weights: pd.Series,
                             z_scores: dict[str, pd.Series]) -> dict[str, float]
   - Weighted sum of z-scores per factor.

2. src/spectraquant_core/attribution.py:
       def compute_attribution(portfolio_returns: pd.Series,
                               factor_returns: pd.DataFrame,
                               hac_lags: int = 5) -> AttributionResult
   - Uses statsmodels.regression.linear_model.OLS with
     cov_type='HAC', cov_kwds={'maxlags': hac_lags}.
   - Returns pydantic AttributionResult — use the locked shape in spec §14.4.6
     exactly. Do not add, remove, or rename any field.
     FactorBeta: beta, se, ci_low, ci_high, pvalue, significant, contribution_bps.
     AttributionResult: alpha, alpha_pvalue, alpha_ci_low, alpha_ci_high,
     betas: dict[str, FactorBeta], r_squared, adj_r_squared, n_obs,
     condition_number, collinearity_warning, hac_lags, window_days, residual_series.
   - collinearity_warning = True when condition_number > 30 (per §14.4.2).
     Collinearity does not prevent computation — report and continue.

3. Tests tests/test_attribution.py:
   - Synthetic: construct a portfolio that is by construction 100% momentum,
     run attribution, assert momentum β ≈ 1 and other betas are n.s.
   - Collinearity test: two highly correlated factors → condition_number > 30,
     warning present.
   - Edge: fewer than 60 obs → raise InsufficientDataError.

Rules:
- No cov_type='HC3' or OLS defaults. HAC is mandatory.
- Return types are pydantic models, not dicts — downstream code type-checks.

Deliverable: commit "feat(core): exposures + attribution with HAC SE". Report
condition-number handling and n.s. labeling in ≤ 10 bullets.
```

---

## Day 4.5 — Historical `factor_returns` bootstrap

```
Goal: build and run the one-time backfill that populates factor_scores and
factor_returns for the 3-year window ending at launch date. This is a hard
prerequisite for Day 5 smoke tests — without it, portfolio attribution returns
all-null beta estimates and the analysis endpoint looks broken.

Context: read spec §14.1 (factor-return series construction) and §14.2
(bootstrap spec) in full before writing any code. Also §14.3.6 (yfinance as
the EOD backfill source) and §14.3.7 (index_membership seed — must already
be done before this prompt runs).

Pre-flight checks (verify before writing code):
- Migrations 0001 and 0002 are applied to your local Supabase.
- symbols table is populated from NSE equity master CSV (~1800+ rows — this is
  the full NSE listing, not just NIFTY 500; membership is recorded separately
  in index_membership). If not yet populated, run Task 6 (seed_symbols.py) from
  this session first.
- index_membership table seeded per HANDOFF.md Part D Step 6. Verify with:
    SELECT COUNT(*) FROM index_membership
    WHERE index_name = 'NIFTY500' AND effective_to IS NULL;
  Expect ~500. Do not proceed if this returns 0.
- SUPABASE_DB_URL, SUPABASE_SERVICE_ROLE_KEY, HOLDINGS_ENC_KEY,
  JOB_SHARED_SECRET, YFINANCE_CACHE_DIR are all set in .env.

Tasks:
1. packages/spectraquant-core/src/spectraquant_core/factor_returns.py
   Implement compute_factor_return_series() per §14.1.9 exactly.
   Signature:
       def compute_factor_return_series(
           factor: FactorName,
           z_scores_history: pd.DataFrame,   # symbol_id, score_date, z_score
           prices: pd.DataFrame,             # wide: index=date, cols=symbol_id, adj_close
           index_membership: pd.DataFrame,   # symbol_id, effective_from, effective_to
           calendar: MarketCalendar,         # XNSE
           start_date: date,
           end_date: date,
       ) -> pd.Series
   Key requirements:
   - Monthly rebalance on first XNSE trading day of each month.
   - Universe per §14.1.2: NIFTY500 members at τ with ≥ 240 prices in prior year
     and a non-null z_score for the factor on τ − 1.
   - Minimum universe size 250; if not met, carry forward prior quintiles and log.
   - Quintile size = floor(|U| / 5); remainder into middle quintiles, never Q1/Q5.
   - Q5 ranking uses z_scores at score_date = τ − 1 trading day (lookahead guard).
   - Returns pd.Series indexed by date, values = mean(Q5_returns) − mean(Q1_returns).
   - Composite uses its own z_score column, not the mean of the five factor series.

2. tests/test_factor_returns.py — four tests, all deterministic:
   - Monthly rebalance boundary: given a synthetic price+z_score matrix, assert
     the quintile membership changes exactly on the first XNSE day of each month.
   - Survivorship bias absence: inject a symbol that is in NIFTY500 for months 1–6
     then removed (effective_to set). Assert it appears in pre-removal factor returns
     and is absent from post-removal returns.
   - Minimum universe skip: set |U(τ)| = 200 at one rebalance; assert function
     carries forward prior quintiles and emits a warning (not raises).
   - Lookahead rejection: supply z_scores with score_date == t (not t−1) for one
     rebalance. Assert the function raises a PointInTimeLookAheadError.
     Add PointInTimeLookAheadError to errors.py.

3. apps/api/src/jobs/backfill_factor_returns.py — per §14.2.3.
   CLI entry point: python -m apps.api.jobs.backfill_factor_returns
       --start 2023-04-21 --end 2026-04-20 --env production
   (dates per spec §14.2.3 — 3-year window ending the day before founder handoff)
   Flow:
   a. Load XNSE calendar.
   b. Fetch historical EOD prices via yfinance (per §14.3.6):
      - Batch 20 symbols at a time; 2s sleep between batches.
      - Cache to YFINANCE_CACHE_DIR. Skip re-fetch if cache hit.
      - Populate eod_prices via COPY (50k rows/sec target).
   c. For each trading day t in [start, end]:
      - Compute per-symbol raw factor values (call spectraquant_core factor functions).
      - Winsorize + cross-sectional z-score.
      - UPSERT into factor_scores (batched, 10k rows per COPY).
      - On first-of-month: compute quintile memberships.
      - Compute daily long-short spread per factor.
      - UPSERT into factor_returns.
   d. Log row counts to job_runs.
   e. Emit summary to stdout.
   All writes are UPSERTs; job is fully rerunnable from any partial state.
   Requires --env production flag as an explicit safeguard.

4. apps/api/src/jobs/seed_index_membership.py — per §14.3.7.
   CLI: python -m apps.api.jobs.seed_index_membership <path_to_xlsx>
   Parses NSE "NIFTY500 Constituent Changes" Excel. Resolves symbols against
   symbols.nse_symbol. Builds (index_name, symbol_id, effective_from, effective_to)
   rows. Bulk inserts with ON CONFLICT DO NOTHING.
   (This may already be done if you ran HANDOFF.md Part D Step 6. Skip if
   index_membership already has ~500 active rows.)

5. apps/api/src/jobs/validate_backfill.py — per §14.2.5.
   Run after backfill completes. Checks:
   - No gaps in factor_returns for any factor on XNSE trading days in window.
   - factor_scores z_scores: mean ≈ 0, std ≈ 1 cross-sectionally per date (5% tol).
   - Momentum Sharpe in [0.2, 1.5] annualized. Fail loudly if outside range.
   - Cross-factor correlation: no |ρ| > 0.99 between any pair (per §14.2.5). If hit,
     something fed identical z-scores to two factor slots.
   Print PASS or FAIL with per-check detail. Exit code 1 on any FAIL.

6. apps/api/src/jobs/seed_symbols.py
   CLI: python -m apps.api.jobs.seed_symbols <path_to_equity_csv>
   Input: NSE equity master CSV (EQUITY_L.csv from NSE India → Market Data →
   Equity downloads). Expected columns: SYMBOL, NAME OF COMPANY, ISIN NUMBER,
   DATE OF LISTING (DD-MMM-YYYY).
   Behavior:
   - Strip whitespace from all string columns before mapping.
   - Map SYMBOL → nse_symbol, NAME OF COMPANY → company_name,
     ISIN NUMBER → isin, DATE OF LISTING → listed_on.
   - sector and industry left NULL (not in this source; enrichable later).
   - UPSERT on nse_symbol: update isin, company_name, listed_on if changed.
   - Print row counts: inserted / updated / skipped. Exit code 1 on parse error.
   MUST run before seed_index_membership.py — index_membership resolves
   symbol_id by looking up symbols.nse_symbol.

Execution order for data setup (run after all six tasks are built):
  1. seed_symbols.py         (populates symbols table)
  2. seed_index_membership.py (requires symbols to exist)
  3. backfill_factor_returns.py (requires both)
  4. validate_backfill.py    (verify results)

Run against a seeded 50-symbol universe first (local Supabase). After validation
passes locally, run against prod Supabase with the full 600-symbol universe.

Rules:
- No writes outside eod_prices, factor_scores, factor_returns, job_runs.
- No reads from portfolios, profiles, or any user table.
- backfill_factor_returns.py imports compute_factor_return_series from
  spectraquant_core — it never re-implements the math inline.
- NEVER run without --env production flag when targeting prod. Add an
  assert APP_ENV == "production" guard inside the script.

Deliverable: commit "feat(core): factor-return series per §14.1 + bootstrap per §14.2".
Report in ≤ 10 bullets: row counts for factor_scores and factor_returns, total runtime,
per-factor validation result (Sharpe, cross-correlation check).
```

---

## Day 5 — Ingest + nightly compute + FastAPI + portfolio endpoint

```
Goal: stand up apps/api with the first end-to-end path:
daily_eod_ingest → nightly_factor_compute → POST /portfolios → analysis JSON.

Context: spec §6, §8.2, §8.4. Migrations in infra/supabase/migrations/ are
already applied.

Tasks:
1. Scaffold apps/api:
   - pyproject.toml: fastapi, uvicorn[standard], asyncpg, sqlalchemy[asyncio],
     pydantic, pydantic-settings, httpx, python-jose[cryptography] (for JWT),
     redis[hiredis], structlog, sentry-sdk[fastapi], posthog, pytest, pytest-asyncio.
   - src/main.py with app factory + CORS + Sentry + structured logging middleware.
   - src/deps.py: get_db (async SQLAlchemy), get_redis, get_current_user
     (verifies Supabase JWT via JWKS cached 5 min), get_tier.
   - src/infra/encryption.py: wrap pgp_sym_encrypt / pgp_sym_decrypt calls
     via raw SQL (Supabase Vault holds the key).

2. Jobs (src/jobs/):
   - daily_eod_ingest.py: fetch Bhavcopy for today's date from NSE.
     Parse CSV. UPSERT into eod_prices. Handle holiday gracefully.
     On failure, retry 3x with exponential backoff. Log row count to job_runs.
   - nightly_factor_compute.py: for each symbol in NIFTY 500, load last 252d
     prices + latest fundamentals; call spectraquant_core factor functions;
     winsorize + z-score cross-sectionally; UPSERT to factor_scores.

3. Expose jobs as protected endpoints:
   - POST /internal/jobs/daily_eod_ingest
   - POST /internal/jobs/nightly_factor_compute
   - Auth: X-Job-Secret header matches JOB_SHARED_SECRET env var.
   - Run synchronously as BackgroundTasks; return 202 + job_id.

4. Implement POST /portfolios:
   - Request schema: name + holdings (list of {symbol, qty, avg_price} OR
     {symbol, weight}) + compliance_ack: bool.
   - Compliance gate (§14.3.2): if profiles.compliance_ack_at IS NULL AND
     request.compliance_ack != true → HTTP 403 {"error":
     "compliance_ack_required"}. On first true ack, set compliance_ack_at
     = now() in the same transaction as the insert.
   - Validate all symbols are in the symbols table + NSE 500 membership.
   - Idempotency (§14.3.1): compute content_hash via exact canonical form
     (sha256 of user_id + JSON of holdings sorted by symbol, weights
     rounded to 6dp, separators (",",":")). On UNIQUE index conflict,
     return existing portfolio_id with HTTP 200, do NOT bump updated_at,
     do NOT increment rate-limit counter, do NOT fire portfolio_analyzed.
   - Enforce tier: free = 1 active portfolio, pro = 5, elite = unlimited.
   - Enforce rate limit: free 1/30d, pro 100/day, elite 1000/day.
   - Insert portfolios row with pgp_sym_encrypt'd holdings.
   - Synchronously compute exposures + attribution via spectraquant-core.
   - Cache result in Redis (key per spec §8.5).
   - Return full JSON with _disclaimer field AND metadata.transaction_cost_bps: 0
     (§14.1.4 — explicit zero, not omitted).

5. GitHub Actions workflows:
   - .github/workflows/daily-eod-ingest.yml (cron 13:30 UTC = 19:00 IST)
   - .github/workflows/nightly-factor-compute.yml (cron 14:00 UTC = 19:30 IST)
   Both POST to the protected endpoint using a GitHub secret.

6. Tests (apps/api/tests/):
   - Unit: JWT verification happy path + expired + wrong aud + wrong iss.
   - Integration: seed 50 symbols + 2 years of prices; run nightly compute;
     POST /portfolios; assert response schema, _disclaimer present, < 5s p95.

Rules:
- All currency in paise as bigint in SQL and Pydantic.
- No raw SQL string concatenation. Use SQLAlchemy text() with bindparam.
- Every outbound log line has request_id + user_id + route.

Deliverable: commit "feat(api): ingest, nightly compute, portfolio endpoint".
Report p95 and row count from the smoke test in ≤ 10 bullets.
```

---

## Day 6 — Next.js web shell: auth + upload + dashboard + screener + billing

```
Goal: ship the web surface end-to-end. Magic-link auth, portfolio upload,
portfolio detail page with factor exposures + attribution, screener with
paywall, Razorpay checkout.

Context: spec §3 sitemap, §4 flows, §10 design language, §11 disclaimer copy.
Also read §14.6 (CSV parser scope — exact column names, format detection logic,
row/file error types, and parser signature), and §14.8 (size factor carry-back
bias disclosure — required copy for the /methodology page).

Tasks:
1. Scaffold apps/web:
   - pnpm create next-app . --typescript --tailwind --app --src-dir=false
     --import-alias "@/*"
   - Install: @supabase/ssr, @supabase/supabase-js, shadcn/ui primitives,
     recharts, zod, @tanstack/react-query, razorpay (client SDK via script tag).
   - shadcn init: Inter + JetBrains Mono; dark default; color tokens from spec §10.1.

2. Routes (App Router):
   - / (marketing landing, static)
   - /pricing, /methodology, /legal/disclaimer, /legal/privacy, /legal/terms,
     /legal/refund (all static MDX)
     NOTE: /methodology MUST include the size factor disclosure per §14.8.3
     (verbatim copy). At build time, substitute {BACKFILL_START} with the value
     of process.env.NEXT_PUBLIC_BACKFILL_START_DATE (formatted as e.g. "April 21, 2023").
     Place it immediately after the size factor formula block, not in a footnote.
     Build fails if the env var is missing.
   - /auth/login, /auth/callback (Supabase magic link)
   - /app (dashboard with empty state)
   - /app/portfolios/new (upload CSV or paste)
   - /app/portfolios/[id] (factor exposures + attribution)
   - /app/screener (factor screener with paywall row 21+ for free)
   - /app/billing/upgrade (Razorpay checkout)
   - /app/account, /app/settings

3. apps/web/src/lib/csv-parser.ts — implement per spec §14.6 exactly.
   Signature: parsePortfolioCsv(csvText: string, nseSymbols: Set<string>): ParseResult
   Three formats: Zerodha (§14.6.1), generic weight (§14.6.2), generic qty (§14.6.3).
   Detection per §14.6.4. RowError and FileError types per §14.6.5–14.6.6.
   No third-party CSV library. No network calls inside the parser.
   Tests: apps/web/src/lib/__tests__/csv-parser.test.ts covering:
     * Zerodha format with preamble line — parses correctly
     * Generic weight format as percentages — auto-divides by 100
     * Symbol not in nseSymbols → unknown_symbol row error, valid rows still parse
     * Duplicate symbol → duplicate_symbol error on second occurrence
     * Stale-row preamble skipping (Zerodha summary line before headers)
     * weights_dont_sum when sum = 0.91
     * too_many_rows when 201 data rows

4. Components:
   - <PortfolioUploader> with two tabs: CSV drop zone and paste table.
     On file drop/select, call parsePortfolioCsv(); show row errors inline
     in a table before the user can submit. On submit, POST JSON holdings
     to FastAPI POST /portfolios. nseSymbols fetched from GET /universe/symbols,
     cached 24h in React Query. Cache busts on localStorage key
     `nse_symbols_version` mismatch (server response includes a version
     string from latest seed_symbols run) — stale symbol lists would
     produce false unknown_symbol errors after new NSE listings.
   - <FactorBarChart> (Recharts, dual series: portfolio vs NIFTY 500 benchmark).
   - <AttributionTable> with β, CI low/high, p-value, n.s. badge.
   - <PaywallModal> plan-aware.
   - <ComplianceBanner> sticky on portfolio pages.
   - <CollinearityBanner> (§14.4.4 variant of ComplianceBanner): renders
     below <AttributionTable> when response.kappa > 30. Verbatim copy from
     §14.4.4. Non-blocking, non-dismissible. When both kappa > 30 AND
     R² < 0.4, render collinearity banner first, low-fit banner second.
   - <LimitedHistoryDisclaimer> (§14.2.2): renders below <AttributionTable>
     when the attribution window includes dates before (L − 365d). Copy
     verbatim from §14.2.2 with [date] substituted to the boundary
     (L − 365d formatted as "April 22, 2025"). This copy uses the word
     "estimated" — which requires `compliance_exempt_contexts` entry
     `"limited_history_disclaimer"` in forbidden_words.json.
   - <InsufficientHistoryEmptyState> (§14.4.5): rendered on the attribution
     tab when the API returns HTTP 422 {"error": "insufficient_history"}.
     Copy verbatim: "Not enough history to compute factor attribution.
     Analysis requires at least 3 months of portfolio data." The factor
     exposures tab (§7.7) renders normally regardless.
   - <ValueCoverageFootnote> (§14.5.6): caption-style footnote below the
     value bar in the factor exposures chart when any holding has NULL
     value score. Copy verbatim: "Value exposure computed from N of M
     holdings. M−N holdings excluded (fundamentals unavailable as of
     [date])." N/M from API response fields exposures.value.covered_count
     and exposures.value.total_count.

5. Compliance filter:
   - packages/compliance-rules/forbidden_words.json (populate from spec §11.1).
     Add `compliance_exempt_contexts` entry `"limited_history_disclaimer"`
     (§14.2.2 needs the word "estimated").
   - packages/compliance-rules/src/index.ts exports complianceCheck(text, ctx).
   - apps/web: build-time check runs over all MDX + copy strings; fails build
     on any match outside exempt_contexts.
   - apps/api middleware: applies to @user_facing response fields. On a hit,
     writes a compliance_log row with source='regex' (§14.3.3). The
     `source` column is NOT NULL with CHECK(source IN ('regex','llm_audit',
     'manual')) — the admin review queue at /admin/compliance-log filters
     by source. Never omit the source field on insert.

6. Razorpay:
   - POST /api/billing/create-order (calls FastAPI).
   - Client opens Razorpay Checkout with order_id.
   - On success, POST /api/billing/verify with signature.
   - FastAPI verifies HMAC, updates profiles.tier, creates subscriptions row.
   - Webhook endpoint at /api/internal/razorpay/webhook (FastAPI side) with
     idempotent UPSERT on razorpay_payment_id.

7. Disclaimer placement (spec §3.3):
   - Footer pill on every page.
   - Sticky banner on /app/portfolios/[id] (dismissible per session).
   - Hard-ack checkbox on first portfolio upload; persist to
     profiles.compliance_ack_at.

Rules:
- v1.0 ships annual plan only (₹1,699 Pro, ₹4,499 Elite). Monthly shows
  "Notify me" button — no checkout yet.
- CSV parser: implement per §14.6 exactly — do not invent a new format or add
  XLSX support. The three accepted formats are fully specified there.
- Every chart uses <ChartCard> wrapper; no raw Recharts in pages.
- Dark theme is default. Light theme switchable via settings, not system pref.

Deliverable: commit "feat(web): auth, upload, dashboard, screener, billing".
Screenshot the portfolio detail page and report Lighthouse scores (perf,
accessibility). In ≤ 10 bullets.
```

---

## Day 7 — Polish, compliance tests, deploy, launch readiness

```
Goal: hit launch readiness. No new features. Only: tests, compliance, perf,
accessibility, deploy, monitoring.

Tasks:
1. Compliance regression test:
   - CI step renders every page + every email template to HTML strings.
   - Pipe through complianceCheck().
   - Fails the build on any match outside exempt_contexts.
   - Positive-content assertion (§14.8.3): /methodology HTML must contain
     the verbatim size-factor carry-back bias disclosure string, with
     {BACKFILL_START} substituted from NEXT_PUBLIC_BACKFILL_START_DATE
     (formatted as e.g. "April 21, 2023"). Test fails if the paragraph
     is missing, truncated, or the date placeholder is unsubstituted.
   - Positive-content assertion (§14.7): email deliverability preflight —
     CI queries Resend API and asserts SPF, DKIM, and DMARC records all
     show "Verified" status for the sending domain. Fail build otherwise.
2. Performance regression test:
   - scripts/perf_smoke.py: replay 50-stock fixture through POST /portfolios
     100x. Assert p95 < 5s. Add to nightly CI.
3. Accessibility:
   - Run @axe-core/playwright against every authenticated page.
   - Fix any color-contrast or missing-label issues.
   - Focus ring visible on all interactive elements.
   - Keyboard nav: tab order sensible on portfolio detail page.
4. Observability:
   - Verify Sentry captures a thrown exception in both web and api.
   - Verify PostHog receives signup_completed, portfolio_analyzed,
     paywall_hit, checkout_started, subscription_activated.
   - Add /admin/jobs page reading job_runs table (founder-email gate).
5. Refund/cancel flow:
   - Cancel button in /app/billing → sets cancelled_at, tier_downgrade_at = period_end.
   - Manual refund SOP in docs/runbook.md (v1.0 uses Razorpay dashboard, not API).
6. DPDP-compliant account deletion:
   - Delete button in /app/settings → hard delete from profiles (cascades),
     set portfolios.deleted_at, schedule hard delete after 30 days.
   - Export-all: returns a JSON of everything personal about the user.
7. Deploy:
   - Vercel: production deploy from main. Set all env vars. Configure
     custom domain + SSL.
   - Railway: deploy FastAPI from main. Set env vars. Link custom subdomain
     api.spectraquant.in.
   - Supabase: switch to Pro plan, enable PITR backups.
   - UptimeRobot: add monitors for / and /api/healthz.
   - Email DNS gate (§14.7): verify Resend shows all three DNS records as
     "Verified" before any transactional email is sent. Send one test email
     to Gmail and Outlook; confirm inbox delivery and dmarc=pass in headers.
     DO NOT proceed if either test lands in spam — fix DNS first.
8. Launch blog posts:
   - docs/blog/what-is-factor-investing.mdx
   - docs/blog/momentum-in-indian-equities.mdx
   - docs/blog/reading-your-factor-card.mdx
   - Auto-publish at /blog/[slug] with OG tags + sitemap.xml.
9. Runbook:
   - docs/runbook.md covering: ingest failure, webhook backlog, DB restore,
     Razorpay account suspension, key rotation, emergency contact.

Rules:
- Do not add new features. Any user-facing addition beyond spec §5 v1.0 is rejected.
- Do not push to main on a Friday.
- All env vars for prod double-checked against .env.example before deploy.

Deliverable: commit "chore: launch readiness" + a launch checklist in PR
description confirming each Part H item from HANDOFF.md. Post Lighthouse
scores, p95 from perf smoke, Sentry + PostHog event confirmations.

After this, you're live.
```

---

## Meta rules for every day

- **One session = one day's prompt.** Don't roll Day 2 into Day 1's session.
- **Review before commit.** Claude Code will propose commits; read the diff.
- **Summary cap: 10 bullets.** Anything longer is Claude Code rambling — ask for the tight version.
- **No speculative scope.** If Claude Code offers to "also add X while I'm here," say no unless X is in §5 v1.0.
- **Keep CLAUDE.md current.** If a rule changes during the week, update CLAUDE.md in the same commit.
