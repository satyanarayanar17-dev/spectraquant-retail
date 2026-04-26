-- 0001_initial_schema.sql
-- SpectraQuant Retail — initial schema
-- Idempotent where possible. Forward-only.
-- Reference: SPECTRAQUANT_RETAIL_SPEC.md §6.2

------------------------------------------------------------------------
-- Extensions
------------------------------------------------------------------------

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

------------------------------------------------------------------------
-- updated_at trigger helper
------------------------------------------------------------------------

CREATE OR REPLACE FUNCTION public.touch_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END;
$$;

------------------------------------------------------------------------
-- Universe: symbols
------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.symbols (
  id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  nse_symbol      TEXT NOT NULL UNIQUE,
  isin            TEXT NOT NULL UNIQUE,
  company_name    TEXT NOT NULL,
  sector          TEXT,
  industry        TEXT,
  is_active       BOOLEAN NOT NULL DEFAULT TRUE,
  listed_on       DATE,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TRIGGER symbols_touch_updated_at
  BEFORE UPDATE ON public.symbols
  FOR EACH ROW EXECUTE FUNCTION public.touch_updated_at();

------------------------------------------------------------------------
-- End-of-day prices (partitioned by year)
------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.eod_prices (
  symbol_id       BIGINT NOT NULL REFERENCES public.symbols(id) ON DELETE CASCADE,
  trade_date      DATE NOT NULL,
  open            NUMERIC(14,4) NOT NULL,
  high            NUMERIC(14,4) NOT NULL,
  low             NUMERIC(14,4) NOT NULL,
  close           NUMERIC(14,4) NOT NULL,
  adj_close       NUMERIC(14,4) NOT NULL,
  volume          BIGINT NOT NULL,
  PRIMARY KEY (symbol_id, trade_date)
) PARTITION BY RANGE (trade_date);

-- Pre-create partitions for 2019–2027. Add more as needed in future migrations.
DO $$
DECLARE
  y INT;
BEGIN
  FOR y IN 2019..2027 LOOP
    EXECUTE format(
      'CREATE TABLE IF NOT EXISTS public.eod_prices_y%1$s
         PARTITION OF public.eod_prices
         FOR VALUES FROM (%2$L) TO (%3$L);',
      y, make_date(y,1,1), make_date(y+1,1,1)
    );
  END LOOP;
END $$;

CREATE INDEX IF NOT EXISTS eod_prices_date_idx
  ON public.eod_prices (trade_date);

------------------------------------------------------------------------
-- Index membership (survivorship-safe NIFTY 500 history)
------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.index_membership (
  id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  index_name      TEXT NOT NULL,
  symbol_id       BIGINT NOT NULL REFERENCES public.symbols(id) ON DELETE CASCADE,
  effective_from  DATE NOT NULL,
  effective_to    DATE,
  weight          NUMERIC(8,6),
  UNIQUE (index_name, symbol_id, effective_from)
);

CREATE INDEX IF NOT EXISTS idx_membership_active
  ON public.index_membership (index_name, effective_to);

------------------------------------------------------------------------
-- Corporate actions
------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.corporate_actions (
  id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  symbol_id       BIGINT NOT NULL REFERENCES public.symbols(id) ON DELETE CASCADE,
  ex_date         DATE NOT NULL,
  action_type     TEXT NOT NULL CHECK (action_type IN ('split','bonus','dividend','rights')),
  ratio_or_amount NUMERIC(14,6) NOT NULL,
  raw_payload     JSONB,
  UNIQUE (symbol_id, ex_date, action_type)
);

------------------------------------------------------------------------
-- Fundamentals
------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.fundamentals (
  symbol_id       BIGINT NOT NULL REFERENCES public.symbols(id) ON DELETE CASCADE,
  period_end      DATE NOT NULL,
  market_cap      NUMERIC(18,2),
  pe_ratio        NUMERIC(10,4),
  pb_ratio        NUMERIC(10,4),
  ev_ebitda       NUMERIC(10,4),
  roe             NUMERIC(10,6),
  roce            NUMERIC(10,6),
  debt_to_equity  NUMERIC(10,4),
  eps_ttm         NUMERIC(14,4),
  source          TEXT NOT NULL,
  fetched_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (symbol_id, period_end)
);

------------------------------------------------------------------------
-- Risk-free rate
------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.risk_free_rate (
  rate_date       DATE PRIMARY KEY,
  rate_pct        NUMERIC(8,4) NOT NULL
);

------------------------------------------------------------------------
-- Factor scores (partitioned by year)
------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.factor_scores (
  symbol_id       BIGINT NOT NULL REFERENCES public.symbols(id) ON DELETE CASCADE,
  score_date      DATE NOT NULL,
  factor          TEXT NOT NULL CHECK (factor IN ('momentum','value','quality','low_vol','size','composite')),
  raw_value       NUMERIC(18,8),
  z_score         NUMERIC(10,6) NOT NULL,
  rank_pct        NUMERIC(6,4) NOT NULL,
  PRIMARY KEY (symbol_id, score_date, factor)
) PARTITION BY RANGE (score_date);

DO $$
DECLARE
  y INT;
BEGIN
  FOR y IN 2019..2027 LOOP
    EXECUTE format(
      'CREATE TABLE IF NOT EXISTS public.factor_scores_y%1$s
         PARTITION OF public.factor_scores
         FOR VALUES FROM (%2$L) TO (%3$L);',
      y, make_date(y,1,1), make_date(y+1,1,1)
    );
  END LOOP;
END $$;

CREATE INDEX IF NOT EXISTS factor_scores_lookup
  ON public.factor_scores (score_date, factor, z_score DESC);

------------------------------------------------------------------------
-- Factor returns (used by attribution OLS)
------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.factor_returns (
  factor          TEXT NOT NULL,
  return_date     DATE NOT NULL,
  daily_return    NUMERIC(14,8) NOT NULL,
  PRIMARY KEY (factor, return_date)
);

------------------------------------------------------------------------
-- User profile (mirror of auth.users we need)
------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.profiles (
  id                   UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  email                TEXT NOT NULL UNIQUE,
  display_name         TEXT,
  tier                 TEXT NOT NULL DEFAULT 'free' CHECK (tier IN ('free','pro','elite')),
  tier_renews_at       TIMESTAMPTZ,
  compliance_ack_at    TIMESTAMPTZ,
  marketing_opt_in     BOOLEAN NOT NULL DEFAULT FALSE,
  created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TRIGGER profiles_touch_updated_at
  BEFORE UPDATE ON public.profiles
  FOR EACH ROW EXECUTE FUNCTION public.touch_updated_at();

-- Auto-create a profile when a new auth.users row appears.
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = public
AS $$
BEGIN
  INSERT INTO public.profiles (id, email)
  VALUES (NEW.id, NEW.email)
  ON CONFLICT (id) DO NOTHING;
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

------------------------------------------------------------------------
-- Subscriptions
------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.subscriptions (
  id                       BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  user_id                  UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  plan                     TEXT NOT NULL CHECK (plan IN ('pro_monthly','pro_yearly','elite_monthly','elite_yearly')),
  status                   TEXT NOT NULL CHECK (status IN ('active','past_due','cancelled','expired')),
  razorpay_payment_id      TEXT UNIQUE,
  razorpay_subscription_id TEXT UNIQUE,
  amount_paise             BIGINT NOT NULL,
  period_start             TIMESTAMPTZ NOT NULL,
  period_end               TIMESTAMPTZ NOT NULL,
  cancelled_at             TIMESTAMPTZ,
  created_at               TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS subscriptions_user_active
  ON public.subscriptions (user_id)
  WHERE status = 'active';

CREATE TABLE IF NOT EXISTS public.razorpay_webhook_events (
  id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  event_id        TEXT NOT NULL UNIQUE,
  event_type      TEXT NOT NULL,
  payload         JSONB NOT NULL,
  processed_at    TIMESTAMPTZ,
  error           TEXT,
  received_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

------------------------------------------------------------------------
-- Portfolios (holdings encrypted with pgcrypto)
------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.portfolios (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  name            TEXT NOT NULL,
  holdings_enc    BYTEA NOT NULL,
  num_holdings    INT NOT NULL,
  total_value_inr NUMERIC(18,2),
  content_hash    TEXT NOT NULL,  -- sha256 of normalized holdings + user_id + day → idempotency key
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  deleted_at      TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS portfolios_user
  ON public.portfolios (user_id)
  WHERE deleted_at IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS portfolios_user_contenthash_day_idx
  ON public.portfolios (user_id, content_hash, ((created_at AT TIME ZONE 'UTC')::date))
  WHERE deleted_at IS NULL;

CREATE TRIGGER portfolios_touch_updated_at
  BEFORE UPDATE ON public.portfolios
  FOR EACH ROW EXECUTE FUNCTION public.touch_updated_at();

------------------------------------------------------------------------
-- Portfolio analyses (cached compute results)
------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.portfolio_analyses (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  portfolio_id          UUID NOT NULL REFERENCES public.portfolios(id) ON DELETE CASCADE,
  analysis_date         DATE NOT NULL,
  exposures_json        JSONB NOT NULL,
  attribution_json      JSONB NOT NULL,
  benchmark             TEXT NOT NULL DEFAULT 'NIFTY500',
  benchmark_exposures   JSONB NOT NULL,
  computed_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
  ttl_until             TIMESTAMPTZ NOT NULL DEFAULT (now() + interval '24 hours')
);

CREATE INDEX IF NOT EXISTS portfolio_analyses_lookup
  ON public.portfolio_analyses (portfolio_id, analysis_date DESC);

------------------------------------------------------------------------
-- Saved screens, alerts
------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.saved_screens (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  name            TEXT NOT NULL,
  filter_json     JSONB NOT NULL,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.alerts (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  portfolio_id    UUID REFERENCES public.portfolios(id) ON DELETE CASCADE,
  alert_type      TEXT NOT NULL CHECK (alert_type IN ('exposure_drift','factor_rank_change','composite_threshold')),
  config_json     JSONB NOT NULL,
  is_active       BOOLEAN NOT NULL DEFAULT TRUE,
  last_fired_at   TIMESTAMPTZ,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

------------------------------------------------------------------------
-- API keys (Elite tier)
------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.api_keys (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id         UUID NOT NULL REFERENCES public.profiles(id) ON DELETE CASCADE,
  prefix          TEXT NOT NULL,
  hashed_key      TEXT NOT NULL,
  name            TEXT NOT NULL,
  last_used_at    TIMESTAMPTZ,
  revoked_at      TIMESTAMPTZ,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS api_keys_prefix
  ON public.api_keys (prefix)
  WHERE revoked_at IS NULL;

------------------------------------------------------------------------
-- Operational
------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS public.rate_limit_buckets (
  bucket_key      TEXT PRIMARY KEY,
  count           INT NOT NULL DEFAULT 0,
  window_start    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.compliance_log (
  id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  context         TEXT NOT NULL,
  matched_term    TEXT NOT NULL,
  raw_text        TEXT NOT NULL,
  source          TEXT NOT NULL DEFAULT 'regex' CHECK (source IN ('regex','llm_audit','manual')),
  created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS compliance_log_recent
  ON public.compliance_log (created_at DESC);

CREATE TABLE IF NOT EXISTS public.job_runs (
  id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  job_name        TEXT NOT NULL,
  status          TEXT NOT NULL CHECK (status IN ('running','succeeded','failed')),
  started_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
  finished_at     TIMESTAMPTZ,
  error           TEXT,
  metrics_json    JSONB
);

CREATE INDEX IF NOT EXISTS job_runs_recent
  ON public.job_runs (job_name, started_at DESC);

------------------------------------------------------------------------
-- Helper: encrypt/decrypt holdings via Vault-held key
------------------------------------------------------------------------
-- Vault is available on Supabase Pro. Before Pro, set HOLDINGS_ENC_KEY env var
-- and pass it through the app layer as the second arg to pgp_sym_encrypt.
--
-- Usage from app layer (SQLAlchemy text()):
--   INSERT INTO portfolios (..., holdings_enc)
--   VALUES (..., pgp_sym_encrypt(:holdings_json, :enc_key));
--
--   SELECT pgp_sym_decrypt(holdings_enc, :enc_key)::json AS holdings FROM portfolios WHERE id = :id;

-- End of migration 0001.
