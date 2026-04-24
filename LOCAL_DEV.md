# LOCAL_DEV.md — Local-First Development

This repo is developed locally first. Cloud providers (Vercel, Railway, hosted Supabase) are deferred until the founder explicitly chooses to deploy. This file governs how local dev differs from the spec's deployed topology.

**Reading order:** CLAUDE.md → SPECTRAQUANT_RETAIL_SPEC.md → this file → PROMPTS.md.

---

## 1. Principle

Everything runs on localhost during development. No cloud account is created unless the founder has personally initiated it. Claude Code MUST NOT:

- Create accounts on any hosted service
- Deploy to Vercel, Railway, or any other host
- Run `vercel`, `railway`, `gh repo create`, or any equivalent CLI that provisions remote resources
- Commit secrets that assume a hosted environment

The spec's §8.3 (Deployment Topology) is the *eventual* target. It is not the current state.

---

## 2. Local dependency stack

| Spec component | Local substitute | Command |
|---|---|---|
| Supabase Postgres + Auth | **Supabase CLI local** (Docker) | `supabase start` |
| Upstash Redis | **Redis in Docker** | `docker run -d -p 6379:6379 redis:7-alpine` |
| Vercel (Next.js) | `npm run dev` | port 3000 |
| Railway (FastAPI) | `uvicorn app.main:app --reload` | port 8000 |
| GitHub Actions cron | **Manual CLI invocation** | `python -m app.jobs.daily_eod_ingest` |
| Sentry | **No-op when `SENTRY_DSN` unset** | env var empty |
| PostHog | **No-op when `POSTHOG_KEY` unset** | env var empty |
| Resend | **No-op when `RESEND_API_KEY` unset; log email body to stdout** | env var empty |
| Razorpay | **Razorpay test mode (still remote)** — no local substitute | test keys in `.env.local` |

Razorpay is the only non-local dependency during development because they do not ship a local sandbox. Test-mode keys hit their hosted API, but the money flow is simulated end-to-end.

---

## 3. One-time local setup

Run these once per developer machine. Claude Code may include this in Day 1 as a `scripts/bootstrap-local.sh` file — do not run it automatically during scaffolding.

```bash
# Prerequisites (macOS example)
brew install node@20 python@3.11 docker docker-compose supabase/tap/supabase redis

# Clone or init repo locally — NO remote yet
cd ~/code
mkdir spectraquant-retail && cd spectraquant-retail
git init
# (the rest of Day 1 scaffolding runs inside this directory)

# Start local Supabase (spawns Postgres + Studio + Auth on docker)
supabase start
# copy the API URL, anon key, service_role key into .env.local

# Start local Redis
docker run -d --name sq-redis -p 6379:6379 redis:7-alpine

# Python venv for api + core
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e packages/spectraquant-core
pip install -r apps/api/requirements.txt

# Node deps for web
pnpm install
```

After this, `make dev` brings the whole stack up.

---

## 4. `.env.local` template for local dev

This file is **gitignored**. Never commit it. Never paste real secrets into Claude Code. The spec-defined `.env.example` continues to be committed as the reference shape.

```bash
# Supabase (from `supabase start` output — local containers only)
SUPABASE_URL=http://127.0.0.1:54321
SUPABASE_ANON_KEY=<from supabase start>
SUPABASE_SERVICE_ROLE_KEY=<from supabase start>
SUPABASE_DB_URL=postgresql://postgres:postgres@127.0.0.1:54322/postgres

# Redis (local Docker)
REDIS_URL=redis://localhost:6379

# Razorpay (test mode — only remote dep)
RAZORPAY_KEY_ID=rzp_test_<yours>
RAZORPAY_KEY_SECRET=<yours>
RAZORPAY_WEBHOOK_SECRET=<set locally; replay via CLI>

# Left empty for local dev — services no-op when unset
SENTRY_DSN=
NEXT_PUBLIC_POSTHOG_KEY=
NEXT_PUBLIC_POSTHOG_HOST=
RESEND_API_KEY=

# Shared secret for local job invocations
JOB_SHARED_SECRET=local-dev-only-change-me

# Encryption key (generate once per dev machine)
HOLDINGS_ENC_KEY=<openssl rand -base64 32>

# Backfill window (§14.8)
BACKFILL_START_DATE=2023-04-21
NEXT_PUBLIC_BACKFILL_START_DATE=2023-04-21

# Local URLs
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WEB_URL=http://localhost:3000
```

---

## 5. Make targets

The `Makefile` at repo root drives local dev. Required targets:

```makefile
.PHONY: install dev verify test lint typecheck db-reset db-migrate seed clean

install:
	pnpm install
	cd apps/api && pip install -r requirements.txt
	pip install -e packages/spectraquant-core

dev:
	# starts supabase, redis, api, web in parallel (use `make dev` in a terminal with mprocs/overmind)
	overmind start -f Procfile.dev

verify: lint typecheck test

lint:
	pnpm -r lint
	cd apps/api && ruff check . && ruff format --check .
	cd packages/spectraquant-core && ruff check .

typecheck:
	pnpm -r typecheck
	cd apps/api && mypy app
	cd packages/spectraquant-core && mypy src

test:
	pnpm -r test
	cd apps/api && pytest
	cd packages/spectraquant-core && pytest

db-reset:
	supabase db reset

db-migrate:
	supabase db push

seed:
	cd apps/api && python -m app.jobs.seed_dev_fixtures

clean:
	supabase stop
	docker rm -f sq-redis || true
```

`Procfile.dev` (used with `overmind` or `foreman`):

```
supabase: supabase start --workdir .
redis:    docker start -a sq-redis
api:      cd apps/api && uvicorn app.main:app --reload --port 8000
web:      cd apps/web && pnpm dev
```

---

## 6. Local job execution

Per spec §8.4, jobs run on GitHub Actions cron in prod. Locally they are invoked manually during development:

```bash
# Trigger the daily EOD ingest (dev DB only)
python -m app.jobs.daily_eod_ingest --env local

# Trigger nightly factor compute
python -m app.jobs.nightly_factor_compute --env local

# Trigger the 3-year backfill (Day 4.5)
python -m app.jobs.backfill_factor_returns \
  --start 2023-04-21 --end 2026-04-20 --env local
```

**Non-negotiable:** every job accepts `--env {local,staging,production}` and refuses to run without the flag. Production runs require a matching `JOB_ENV=production` env var as a second lock. This prevents a stray dev invocation from hitting the wrong database.

---

## 7. Razorpay locally

Razorpay test mode is the only way to exercise the payment flow locally. Two scenarios:

**Checkout flow (client → Razorpay → verify):** works out of the box against `rzp_test_*` keys. No tunneling needed. The verify endpoint on your local FastAPI receives the HMAC, validates, upgrades tier in local Supabase.

**Webhook flow (Razorpay → your server):** Razorpay cannot reach `localhost:8000`. Two options:

1. **Recommended for dev:** simulate webhook delivery with a local CLI script (`scripts/replay_razorpay_webhook.py`) that reads a committed fixture payload, signs it with `RAZORPAY_WEBHOOK_SECRET`, and POSTs to `http://localhost:8000/api/internal/razorpay/webhook`. Day 5 ships this script.
2. **When you want to test real webhook delivery:** run `cloudflared tunnel` or `ngrok http 8000` to get a public URL, then register it temporarily in Razorpay dashboard. Use sparingly — tunneling exposes your local environment to the internet.

The replay script is the default. The tunnel is the exception.

---

## 8. Git without a remote

Local-first means `git init` but no `git remote add origin`. You still:

- Use feature branches (`feat/day-1-scaffold`, `feat/day-2-factors`)
- Write conventional commits per CLAUDE.md §13
- Run `make verify` before every commit
- Tag milestones: `git tag v0.1-day-1`, `v0.2-day-2`, etc.

Pre-commit hooks still run locally. Install with `pre-commit install`. The config (`.pre-commit-config.yaml`) is identical to what it'll be post-push.

When you later push to GitHub:

```bash
gh repo create spectraquant-retail --private --source=. --remote=origin
git push -u origin main
git push --tags
```

Nothing about the repo structure changes at push time.

---

## 9. What Claude Code MUST NOT do in local mode

- Do not run `vercel`, `railway`, `flyctl`, `aws`, `gcloud`, or any cloud CLI
- Do not run `gh repo create` or any remote creation command
- Do not push to any remote — even if a remote is later added, commits push only on explicit founder instruction
- Do not create hosted accounts by scripting signups
- Do not hardcode `localhost` URLs into source code — all URLs come from env vars, so the same code runs unmodified in prod later
- Do not disable features when cloud services aren't reachable — the code must gracefully no-op when DSNs are empty, not crash

If a task in PROMPTS.md references a cloud service, execute the local equivalent from §2 of this file and note it in the commit message (`feat(infra): local Supabase setup — cloud deferred`).

---

## 10. What the founder must do (not Claude Code)

These stay in the founder's lane even in local dev:

- Razorpay account creation + KYC (needed for test keys, not just production)
- Domain purchase + DNS publication (§14.7 — still 48h lead time whenever launch happens)
- Any TM-1 filing, lawyer review, compliance consultation
- Decision to push to GitHub (including choice of repo visibility)
- Decision to deploy to any hosted environment

Claude Code waits for explicit instructions before initiating any of these.

---

## 11. Transition from local to deployed

When the founder is ready to deploy (probably end of Day 6 or Day 7):

1. Create cloud accounts manually (Vercel, Railway, upgrade Supabase to Pro, Upstash Redis).
2. Push repo to GitHub (`gh repo create`, then `git push`).
3. Connect Vercel to the repo — auto-deploys on push to `main`.
4. Deploy FastAPI to Railway via its GitHub integration.
5. Migrate local Supabase schema to cloud: `supabase link` → `supabase db push`.
6. Run the backfill job against cloud Supabase per HANDOFF.md Part D.
7. Configure Razorpay webhook URL to point at the Railway-hosted API.
8. Wait for DMARC propagation (§14.7), send test emails, verify headers.
9. Launch.

No code changes are required for this transition — only env vars in the hosted environment. That is the whole point of local-first.

---

*End of LOCAL_DEV.md. This file is a living annex to the spec; updates land as PRs on the repo once GitHub is connected.*
