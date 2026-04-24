# SpectraQuant Retail

Factor-analytics platform for Indian retail investors. Decomposes equity portfolios
into five factor exposures — momentum, value, quality, low-vol, size — and attributes
returns to each. Analytics only; no advice.

Full product spec: [SPECTRAQUANT_RETAIL_SPEC.md](SPECTRAQUANT_RETAIL_SPEC.md)

---

## Running tests

### Prerequisites

```bash
pip install uv
uv pip install -e "packages/spectraquant-core[dev]"
```

### Core library

```bash
pytest packages/spectraquant-core -q
```

### Type-checking & lint

```bash
mypy packages/spectraquant-core/src
ruff check packages/spectraquant-core
```

### Full CI (requires pnpm 9 + Node 20)

```bash
pnpm install
pnpm turbo run check
```

---

## Monorepo layout

```
apps/web                  Next.js 14 (App Router) — Vercel
apps/api                  FastAPI — Railway
packages/spectraquant-core   Pure-Python factor math
packages/shared-types        Pydantic → TypeScript generated types
packages/compliance-rules    Forbidden words + disclaimer copy
infra/supabase/migrations    Sequenced SQL
infra/github-actions         Cron workflows
docs/                        Architecture, runbook, methodology
```

---

## Dev setup

Copy `.env.example` to `.env.local` (web) and `.env` (api). See `HANDOFF.md` for secrets.

```bash
pnpm install
pnpm --filter web dev      # Next.js on :3000
pnpm --filter api dev      # FastAPI on :8000
```
