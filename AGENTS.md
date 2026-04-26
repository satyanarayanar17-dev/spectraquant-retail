# AGENTS.md — SpectraQuant Retail

**You are working on SpectraQuant Retail, a factor-analytics web product for the Indian retail investor.** The full spec is in `SPECTRAQUANT_RETAIL_SPEC.md` at the repo root. Read it once at the start of any new session. Do not re-derive decisions from it — the spec is the source of truth.

## One-line summary

Decompose Indian equity portfolios into five factor exposures (momentum, value, quality, low-vol, size) and attribute returns to each. Analytics, not advice.

## Tech stack (pinned)

- **Web:** Next.js 14 (App Router), TypeScript 5.4+, Tailwind 3.4+, shadcn/ui, Recharts, Supabase SSR helpers.
- **API:** Python 3.12, FastAPI 0.110+, Pydantic 2, SQLAlchemy 2 (async), asyncpg, Redis (Upstash), structlog.
- **Core library (`packages/spectraquant-core`):** Python 3.12, pandas 2.2+, numpy 2.0+, statsmodels 0.14+, pydantic 2, `pandas-market-calendars` for NSE trading calendar.
- **DB:** Supabase Postgres (pgcrypto, Vault).
- **Jobs:** GitHub Actions cron → hits protected FastAPI endpoints with shared secret.
- **Package manager:** `pnpm` 9 for JS, `uv` for Python (fast; `pip install uv` first).
- **Build orchestrator:** Turbo.

## Monorepo layout

```
apps/web            Next.js — Vercel
apps/api            FastAPI — Railway
packages/spectraquant-core   Pure-Python factor math. No I/O. No Streamlit.
packages/shared-types        pydantic → TypeScript generated types
packages/compliance-rules    forbidden_words.json + disclaimer copy
infra/supabase/migrations    sequenced SQL
infra/github-actions         cron workflows
docs                         architecture.md, runbook.md, methodology.md
```

## Non-negotiable rules

1. **Analytics, not advice.** Never generate user-facing copy containing "buy", "sell", "recommend", "target price", "stop loss", "must-buy", "guaranteed", "multibagger", or any directive phrasing. The full list is in `packages/compliance-rules/forbidden_words.json`. If unsure, assume forbidden.
2. **No Streamlit, no legacy imports.** `packages/spectraquant-core` must run in a pure Python REPL with only the pinned deps. It never imports from `backend/` or `spectraquant_v3/` in the legacy repo.
3. **No module-level side effects.** No file reads, no network calls, no `print`, no logger config at import time in any module under `packages/`.
4. **Deterministic compute.** All factor functions take typed inputs and return typed outputs. Any `np.random` use requires an explicit seed parameter.
5. **Column-level encryption on holdings.** `portfolios.holdings_enc` is `pgp_sym_encrypt`-ed with the key from Supabase Vault. Never log decrypted holdings. Never return decrypted holdings in API responses except to the owning user.
6. **Idempotent webhooks.** Razorpay webhook handlers UPSERT on `razorpay_payment_id`. Duplicate delivery is a no-op.
7. **JWT verification on every API route.** FastAPI caches Supabase JWKS (5-min TTL) and verifies signature, `aud`, `exp`, and `iss` before dispatching.
8. **Compliance filter in CI.** Every string that ships to users passes `complianceCheck()` at build time. CI fails on any forbidden-word match outside `exempt_contexts`.
9. **Performance budget.** Portfolio analysis p95 < 5s. Dashboard TTFB < 2s. Regression test in CI.
10. **No scope creep in v1.0.** The 7-day feature list is locked in §5 of the spec. If something doesn't appear under "IN v1.0", do not build it.

## Dev commands

```bash
# Install everything
pnpm install                          # JS deps
uv pip install -e packages/spectraquant-core[dev]
uv pip install -e apps/api[dev]

# Dev servers
pnpm --filter web dev                 # Next.js on :3000
pnpm --filter api dev                 # FastAPI on :8000 (uvicorn --reload)

# Tests
pnpm --filter web test                # Vitest + Playwright
pytest packages/spectraquant-core     # unit, determinism, golden fixtures
pytest apps/api                       # API contract + snapshot tests

# Type check / lint
pnpm lint
pnpm typecheck
ruff check .
mypy packages/spectraquant-core apps/api

# Migrations
supabase db reset                     # nuke + rerun all migrations locally
supabase db push                      # apply to linked project

# Full CI locally
pnpm turbo run check
```

## Environment

Copy `.env.example` to `.env.local` (for web), `.env` (for api), and fill in values. See `HANDOFF.md` for how to obtain each secret.

## Gotchas

- **Timestamps:** all DB columns are `TIMESTAMPTZ`. Application code works in UTC; the UI formats into IST (`Asia/Kolkata`) at the component boundary. Never do `TIMESTAMP WITHOUT TIME ZONE`.
- **NSE trading calendar:** use `pandas_market_calendars.get_calendar("XNSE")`. Do not hand-roll a holiday list.
- **pandas 2.2+ chained assignment:** no `df[col] = ...` after slicing. Use `.loc[]` or `.assign()`. The legacy code is full of this — do not copy patterns blindly.
- **Supabase RLS is always on.** If a query returns empty and you expect rows, check RLS first, then indexes, then joins.
- **Razorpay amounts are in paise.** ₹199 = 19900. ₹1,699 = 169900. Never use floats for currency.
- **Bhavcopy URL format changes occasionally.** The ingest job must fail-soft: last-good cache is served with a stale-data banner. Do not crash the dashboard on an ingest failure.
- **yfinance for fundamentals is a known wart.** Coverage on mid-cap EV/EBITDA is ~70%. Value factor must accept ≥ 2 of 3 inputs; single-input fallback is `NULL`.

## Where things live

| I need to... | Look in... |
|--------------|-----------|
| Understand a product decision | `SPECTRAQUANT_RETAIL_SPEC.md` (master spec) |
| Find a schema column | `infra/supabase/migrations/0001_initial_schema.sql` |
| Find RLS rules | `infra/supabase/migrations/0002_rls_policies.sql` |
| Modify forbidden words | `packages/compliance-rules/forbidden_words.json` |
| See factor formulas | `SPECTRAQUANT_RETAIL_SPEC.md` §7 |
| See the Day 1–7 plan | `SPECTRAQUANT_RETAIL_SPEC.md` §9.5 + `PROMPTS.md` |
| Runbook for ops incidents | `docs/runbook.md` |

## When unsure

- Extraction decisions → §9 of the spec.
- UI component choice → §10 of the spec. Use shadcn/ui primitives; don't install another UI lib.
- Copy wording → run it through `complianceCheck()` first, then check §11 disclaimer copy.
- Tradeoffs → ask the founder. Do not silently pick a new framework, library, or architecture pattern. Small choices (utility file naming, helper extraction) are fine at your discretion.

## Commit hygiene

- Conventional commits: `feat(api): ...`, `fix(web): ...`, `chore(infra): ...`, `test(core): ...`.
- Every PR must pass: `pnpm lint`, `pnpm typecheck`, `ruff check`, `mypy`, all tests, compliance check.
- No secrets in commits. `.env*` is in `.gitignore`. If you see a secret committed, rotate it before anything else.
- Do not `git push --force` to `main`. Do not amend a pushed commit.
