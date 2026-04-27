-- 0003_missing_tables.sql
-- Adds tables referenced in application code but absent from 0001_initial_schema.sql:
--   payments, scheduled_deletions, analyses (from user.py export/delete)
-- Also fixes subscriptions: adds tier + tier_downgrade_at columns (used by user.py cancel),
-- and adds rows_written column to job_runs (used by admin.py).
-- Idempotent — safe to re-run.

------------------------------------------------------------------------
-- payments (Razorpay payment.captured webhook)
-- webhooks.py inserts here on CONFLICT (razorpay_payment_id) DO NOTHING
------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.payments (
  id                   BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  razorpay_payment_id  TEXT NOT NULL UNIQUE,
  user_id              UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  amount_paise         BIGINT NOT NULL,
  currency             TEXT NOT NULL DEFAULT 'INR',
  status               TEXT NOT NULL DEFAULT 'captured',
  captured_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS payments_user
  ON public.payments (user_id, captured_at DESC);

------------------------------------------------------------------------
-- scheduled_deletions (DPDP 30-day soft-delete — user.py delete_me)
------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.scheduled_deletions (
  id           BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  user_id      UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  delete_after TIMESTAMPTZ NOT NULL,
  executed_at  TIMESTAMPTZ,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (user_id)  -- one pending deletion per user
);

CREATE INDEX IF NOT EXISTS scheduled_deletions_pending
  ON public.scheduled_deletions (delete_after)
  WHERE executed_at IS NULL;

------------------------------------------------------------------------
-- analyses (analysis run count — referenced in user.py export_me)
-- Lightweight table; the heavy cache lives in portfolio_analyses.
------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.analyses (
  id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id      UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  portfolio_id UUID REFERENCES public.portfolios(id) ON DELETE SET NULL,
  window_days  INT NOT NULL,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS analyses_user
  ON public.analyses (user_id, created_at DESC);

------------------------------------------------------------------------
-- subscriptions: add missing columns used by application code
-- (idempotent ADD COLUMN IF NOT EXISTS)
------------------------------------------------------------------------

-- tier used by webhooks.py subscription.activated handler
ALTER TABLE public.subscriptions
  ADD COLUMN IF NOT EXISTS tier TEXT NOT NULL DEFAULT 'pro'
    CHECK (tier IN ('free','pro','elite'));

-- tier_downgrade_at used by user.py cancel endpoint
ALTER TABLE public.subscriptions
  ADD COLUMN IF NOT EXISTS tier_downgrade_at TIMESTAMPTZ;

------------------------------------------------------------------------
-- job_runs: add rows_written column (admin.py list_job_runs returns it)
------------------------------------------------------------------------

ALTER TABLE public.job_runs
  ADD COLUMN IF NOT EXISTS rows_written BIGINT;

-- End of migration 0003.
