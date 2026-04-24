# SpectraQuant Retail — Founder Handoff Guide

Everything you need before the first Claude Code session. Follow top-to-bottom. Estimated time: **2–3 hours** of account setup, then you're ready to start coding on Day 1.

---

## Part A — Pre-flight: Accounts & Secrets

Create these accounts in order. Each row lists what you'll save in `.env` and any notes.

### A1. Core infrastructure

| # | Service | Plan | Purpose | Save in `.env` as |
|---|---------|------|---------|-------------------|
| 1 | **GitHub** | Free | Code hosting + Actions | `GITHUB_*` (PAT if needed) |
| 2 | **Supabase** | Free → Pro ($25/mo when ready) | Postgres + Auth + Vault | `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET` |
| 3 | **Vercel** | Hobby (free) | Web hosting | `VERCEL_TOKEN` (for CLI deploys) |
| 4 | **Railway** | Hobby ($5/mo) | FastAPI + background workers | `RAILWAY_TOKEN` |
| 5 | **Upstash** | Free tier | Redis for cache + rate limit | `UPSTASH_REDIS_REST_URL`, `UPSTASH_REDIS_REST_TOKEN` |
| 6 | **Cloudflare** | Free + domain (~₹900/yr) | DNS + domain | — (DNS only) |

### A2. Application services

| # | Service | Plan | Purpose | Save in `.env` as |
|---|---------|------|---------|-------------------|
| 7 | **Razorpay** | Standard (2% per txn) | Payments. Needs PAN + current account under sole-prop name | `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET`, `RAZORPAY_WEBHOOK_SECRET` |
| 8 | **Resend** | Free (3k/mo) | Magic-link auth + transactional email | `RESEND_API_KEY` |
| 9 | **Sentry** | Free (5k events/mo) | Error monitoring | `SENTRY_DSN_WEB`, `SENTRY_DSN_API` |
| 10 | **PostHog** | Cloud Free (1M events/mo) | Product analytics | `POSTHOG_KEY`, `POSTHOG_HOST` |

### A3. Email domain setup (start 48h before launch)

Mandatory before shipping. Email deliverability is day-0 work.

1. Buy domain on Cloudflare (`spectraquant.in` or equivalent).
2. In Resend: add your domain → copy the three DNS records (SPF, DKIM, one more for DKIM).
3. In Cloudflare DNS: add those three records exactly as Resend shows them. Proxy status: **DNS only (grey cloud)**.
4. Add a DMARC record: `v=DMARC1; p=quarantine; rua=mailto:dmarc@spectraquant.in`.
5. Wait for Resend to show all three as "Verified" (1–48h).
6. **Do not send a single email before these are green** — a fresh domain that sends unauthenticated mail gets blacklisted for months.

### A4. Razorpay KYC (start 3–5 days before launch)

Razorpay KYC can take up to a week. Do it first.

1. PAN card (sole proprietor).
2. Aadhaar.
3. Current account in the business name (not savings, not personal).
4. Cancelled cheque or bank statement.
5. In Razorpay dashboard: `Settings → Account & Settings → Business type: Individual/Sole Proprietorship → Submit documents`.
6. Wait for "Activated" status. Test-mode credentials work immediately; live-mode unlocks after KYC.

### A5. Pre-launch legal (book this now)

| Item | Owner | Cost | Timeline |
|------|-------|------|----------|
| Securities lawyer reviews disclaimer + privacy policy | External | ~₹15,000 | 1 week |
| Trademark filing for "SpectraQuant" (optional TM-1) | External | ~₹4,500 | Can do after launch |

---

## Part B — Local Machine Setup

Install once, on the machine where you'll run Claude Code.

```bash
# Node toolchain
brew install node@20 pnpm@9
npm install -g vercel@latest

# Python toolchain
brew install python@3.12
pip install uv

# Supabase CLI
brew install supabase/tap/supabase
supabase login

# Railway CLI
brew install railway
railway login

# Docker (for local Postgres when needed)
brew install --cask docker

# Claude Code (if not already)
npm install -g @anthropic-ai/claude-code
```

Verify:

```bash
node -v         # v20+
pnpm -v         # 9+
python3 --version  # 3.12+
uv --version
supabase -v
railway version
docker --version
```

---

## Part C — Repo Bootstrap

Before the first Claude Code session, get a clean repo on disk.

```bash
# 1. Create and clone the repo
gh repo create spectraquant-retail --private --clone
cd spectraquant-retail

# 2. Drop the handoff artifacts in place
cp /path/to/retail-handoff/CLAUDE.md .
cp /path/to/retail-handoff/SPECTRAQUANT_RETAIL_SPEC.md .     # copy from parent folder
cp /path/to/retail-handoff/PROMPTS.md .
cp /path/to/retail-handoff/.env.example .
cp /path/to/retail-handoff/.gitignore .
cp /path/to/retail-handoff/pnpm-workspace.yaml .
cp /path/to/retail-handoff/turbo.json .
cp -r /path/to/retail-handoff/infra .

# 3. First commit
git add .
git commit -m "chore: initial scaffold + spec + migrations"
git push -u origin main

# 4. Create .env.local from template
cp .env.example .env.local
# edit .env.local — fill in the values from Part A
```

---

## Part D — Supabase Project Bootstrap

```bash
# 1. In Supabase dashboard: create a new project. Pick ap-south-1 (Mumbai).
# 2. Grab the URL + anon key + service role key from Project Settings → API.
# 3. Link the local repo to the project
supabase link --project-ref <your-project-ref>

# 4. Apply the migrations
supabase db push

# 5. DEFERRED (requires Day 4.5 code) — Seed symbols table
#
# NOTE: seed_symbols.py is built during Day 4.5 (Task 6). Complete HANDOFF.md
# steps 1–4 now, run Claude Code Day 1 through Day 4, then return here before
# starting Day 4.5.
#
# Source: NSE India website → Market Data → Equity → Download equity master CSV
# (filename is typically EQUITY_L.csv). Lists all NSE-listed equities.
#
# a. Download the file and place it at:
#       data/EQUITY_L.csv
#
# b. After Day 4.5 code is built, run:
#       python -m apps.api.jobs.seed_symbols data/EQUITY_L.csv
#
# c. Verify rows (all NSE equities, past and present):
#       psql "$SUPABASE_DB_URL" -c "SELECT COUNT(*) FROM symbols;"
#    Expected: ~1800+ rows.
#
# d. MUST complete before Step 6 — index_membership resolves symbol_id by
#    looking up symbols.nse_symbol.

# 6. DEFERRED (requires Day 4.5 code) — Seed historical NIFTY 500 membership data
#
# NOTE: seed_index_membership.py is built during Day 4.5 (Task 4). Run after
# Step 5 (symbols table) is confirmed populated.
#
# Source: NSE indices page → NIFTY 500 → Downloads → "Historical Constituent Changes"
# This is a free Excel download listing every addition/removal with effective date.
#
# a. Download the file and place it at:
#       data/nifty500_constituent_changes.xlsx
#
# b. Run the seed script:
#       python -m apps.api.jobs.seed_index_membership \
#         data/nifty500_constituent_changes.xlsx
#
# c. Verify ~500 active members:
#       psql "$SUPABASE_DB_URL" -c \
#         "SELECT COUNT(*) FROM index_membership
#          WHERE index_name = 'NIFTY500' AND effective_to IS NULL;"
#    Expected: ~500. If 0, stop — do not proceed to the backfill job.
#
# d. Spot-check one known change (e.g. a known addition in 2022) against
#    the Excel source before proceeding.
#
# WHY STEPS 5–6 ARE A BLOCKER: factor-return series construction (spec §14.1) uses
# index_membership for survivorship-bias-safe universe construction. Missing or
# incorrect history will silently corrupt all historical attribution figures.
# The backfill_factor_returns job (Day 4.5) MUST NOT run until both are verified.

# 7. Enable pgcrypto and Vault
# In Supabase SQL Editor, run:
#   CREATE EXTENSION IF NOT EXISTS pgcrypto;
# Vault is available on the Pro plan; on Free, hold holdings key as an env var until upgrade.

# 8. Seed a dev user + test data (optional for local development)
psql "$SUPABASE_DB_URL" -f infra/supabase/seed.sql
```

---

## Part E — First Claude Code Session

Once Parts A–D are done, launch Claude Code in the repo root.

**Paste this verbatim as your first prompt:**

```
Read CLAUDE.md and SPECTRAQUANT_RETAIL_SPEC.md. Confirm you understand the
project, then summarize in 5 bullets:
1. What we're building (one line).
2. The non-negotiable rules.
3. The tech stack.
4. The week-1 scope.
5. What is explicitly out of scope.

Do not write any code yet. After I confirm your understanding,
we will start with Day 1.
```

Wait for a clean summary. If Claude Code gets any rule wrong, correct it before proceeding. The summary is free insurance against drift.

Then use `PROMPTS.md` for Day 1 onwards.

---

## Part F — Guardrails for Claude Code

Things to explicitly tell Claude Code *not* to do. Paste this as a follow-up message to the first prompt:

```
Before we start, confirm you will NOT:
1. Add any "buy"/"sell"/"recommend" copy anywhere in the codebase.
2. Import from the legacy SpectraQuant repo (backend/, spectraquant_v3/,
   frontend/, admin_frontend/) into packages/spectraquant-core.
3. Install any UI library other than shadcn/ui primitives + Recharts.
4. Introduce a job queue (Celery, RQ, BullMQ) in v1.0. We use GitHub
   Actions cron + protected FastAPI endpoints.
5. Use floats for currency. Always paise as integers in the DB and API.
6. Write features not listed as "IN v1.0" in spec §5.
7. Add a "target price", "stop loss", or "price target" field to any
   model, schema, or UI.
8. Skip compliance checks or bypass the forbidden-word filter.
9. Leave secrets in committed files.
10. Push to main with failing tests.

Acknowledge each one, then we begin Day 1.
```

---

## Part G — When Things Break

| Symptom | First check |
|---------|-------------|
| "Row returned 0 rows" but data exists | RLS policy — `SELECT auth.uid()` inside the session |
| Supabase migration fails | Look for forward-only violations; migrations never `DROP` in place |
| Razorpay webhook not firing locally | Use Razorpay's webhook simulator + ngrok; don't try local webhooks without tunneling |
| `pandas FutureWarning` in logs | Update to `.loc[]` pattern immediately — do not suppress |
| Factor scores empty for a date | Check `job_runs` for `nightly_factor_compute` — last-good cache should be serving |
| JWT rejected by FastAPI | JWKS cache probably stale; restart API process or wait 5 min |
| Compliance CI step fails | Exact term logged in `compliance_log`; fix copy, do not add term to exempt list |

---

## Part H — Launch Day Checklist (T−24h)

- [ ] All DNS records verified (Resend + apex domain)
- [ ] Email deliverability smoke (§14.7): sent one test magic-link to
      Gmail and Outlook; both landed in inbox (not spam) with `dmarc=pass`
      in the Authentication-Results header. If either lands in spam,
      DO NOT launch — fix DNS first.
- [ ] Size-factor disclosure (§14.8.3) visible on /methodology with
      `{BACKFILL_START}` correctly substituted (e.g. "April 21, 2023").
      Manually verify the paragraph is present and not truncated.
- [ ] Razorpay live mode activated, not just test mode
- [ ] Supabase on Pro plan (for PITR backups + Vault)
- [ ] Sentry + PostHog receiving events in prod project
- [ ] Legal disclaimer + privacy policy reviewed by lawyer, signed off
- [ ] Refund/cancel flow end-to-end tested with a real ₹199 transaction (then refund)
- [ ] Compliance CI step passing on `main`
- [ ] `/healthz` and `/readyz` green on prod
- [ ] 3 launch blog posts published and indexable
- [ ] First portfolio upload tested from a throwaway account on prod
- [ ] Runbook reviewed; emergency contact has infra access
- [ ] Twitter/Substack launch post drafted, not yet sent

Launch when all boxes are checked. Do not launch on a Friday.
