-- 0002_rls_policies.sql
-- Row-level security policies.
-- Defense in depth: RLS is always on, service_role bypasses, anon key NEVER bypasses.
-- Principle: a user can only see/modify rows they own.

------------------------------------------------------------------------
-- Enable RLS
------------------------------------------------------------------------

ALTER TABLE public.profiles            ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.subscriptions       ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.portfolios          ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.portfolio_analyses  ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.saved_screens       ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.alerts              ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.api_keys            ENABLE ROW LEVEL SECURITY;

-- Market data tables are world-readable (read-only for authenticated users)
-- and write-restricted to service_role only.
ALTER TABLE public.symbols             ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.eod_prices          ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.index_membership    ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.corporate_actions   ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.fundamentals        ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.risk_free_rate      ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.factor_scores       ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.factor_returns      ENABLE ROW LEVEL SECURITY;

-- Ops tables — service_role only. No authenticated access.
ALTER TABLE public.razorpay_webhook_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.compliance_log      ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.job_runs            ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.rate_limit_buckets  ENABLE ROW LEVEL SECURITY;

------------------------------------------------------------------------
-- profiles: self read/update only
------------------------------------------------------------------------

CREATE POLICY profiles_self_select
  ON public.profiles
  FOR SELECT
  TO authenticated
  USING (id = auth.uid());

CREATE POLICY profiles_self_update
  ON public.profiles
  FOR UPDATE
  TO authenticated
  USING (id = auth.uid())
  WITH CHECK (id = auth.uid());

-- No INSERT/DELETE policy for authenticated role — profiles created via auth trigger,
-- deleted via cascade from auth.users. service_role handles everything else.

------------------------------------------------------------------------
-- subscriptions: self read only. writes via service_role (webhook handler).
------------------------------------------------------------------------

CREATE POLICY subscriptions_self_select
  ON public.subscriptions
  FOR SELECT
  TO authenticated
  USING (user_id = auth.uid());

------------------------------------------------------------------------
-- portfolios: self CRUD
------------------------------------------------------------------------

CREATE POLICY portfolios_self_select
  ON public.portfolios
  FOR SELECT
  TO authenticated
  USING (user_id = auth.uid() AND deleted_at IS NULL);

CREATE POLICY portfolios_self_insert
  ON public.portfolios
  FOR INSERT
  TO authenticated
  WITH CHECK (user_id = auth.uid());

CREATE POLICY portfolios_self_update
  ON public.portfolios
  FOR UPDATE
  TO authenticated
  USING (user_id = auth.uid())
  WITH CHECK (user_id = auth.uid());

CREATE POLICY portfolios_self_soft_delete
  ON public.portfolios
  FOR UPDATE
  TO authenticated
  USING (user_id = auth.uid())
  WITH CHECK (user_id = auth.uid() AND deleted_at IS NOT NULL);

------------------------------------------------------------------------
-- portfolio_analyses: readable if user owns the portfolio
------------------------------------------------------------------------

CREATE POLICY portfolio_analyses_self_select
  ON public.portfolio_analyses
  FOR SELECT
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM public.portfolios p
      WHERE p.id = portfolio_analyses.portfolio_id
        AND p.user_id = auth.uid()
        AND p.deleted_at IS NULL
    )
  );

-- Writes are service_role only (server computes + inserts).

------------------------------------------------------------------------
-- saved_screens, alerts, api_keys: self CRUD
------------------------------------------------------------------------

CREATE POLICY saved_screens_self_all
  ON public.saved_screens
  FOR ALL
  TO authenticated
  USING (user_id = auth.uid())
  WITH CHECK (user_id = auth.uid());

CREATE POLICY alerts_self_all
  ON public.alerts
  FOR ALL
  TO authenticated
  USING (user_id = auth.uid())
  WITH CHECK (user_id = auth.uid());

CREATE POLICY api_keys_self_select
  ON public.api_keys
  FOR SELECT
  TO authenticated
  USING (user_id = auth.uid());

CREATE POLICY api_keys_self_insert
  ON public.api_keys
  FOR INSERT
  TO authenticated
  WITH CHECK (user_id = auth.uid());

CREATE POLICY api_keys_self_revoke
  ON public.api_keys
  FOR UPDATE
  TO authenticated
  USING (user_id = auth.uid())
  WITH CHECK (user_id = auth.uid() AND revoked_at IS NOT NULL);

------------------------------------------------------------------------
-- Market data: read-only for all authenticated users
------------------------------------------------------------------------

CREATE POLICY symbols_read_authenticated
  ON public.symbols
  FOR SELECT TO authenticated USING (true);

CREATE POLICY eod_prices_read_authenticated
  ON public.eod_prices
  FOR SELECT TO authenticated USING (true);

CREATE POLICY index_membership_read_authenticated
  ON public.index_membership
  FOR SELECT TO authenticated USING (true);

CREATE POLICY corporate_actions_read_authenticated
  ON public.corporate_actions
  FOR SELECT TO authenticated USING (true);

CREATE POLICY fundamentals_read_authenticated
  ON public.fundamentals
  FOR SELECT TO authenticated USING (true);

CREATE POLICY risk_free_rate_read_authenticated
  ON public.risk_free_rate
  FOR SELECT TO authenticated USING (true);

CREATE POLICY factor_scores_read_authenticated
  ON public.factor_scores
  FOR SELECT TO authenticated USING (true);

CREATE POLICY factor_returns_read_authenticated
  ON public.factor_returns
  FOR SELECT TO authenticated USING (true);

-- Writes to market data are all service_role (no policy needed; service_role
-- bypasses RLS by default in Supabase).

------------------------------------------------------------------------
-- Ops tables: no authenticated policies → service_role only.
-- (RLS is enabled; absence of policy = deny for authenticated + anon.)
------------------------------------------------------------------------

-- razorpay_webhook_events, compliance_log, job_runs, rate_limit_buckets
-- are handled exclusively by the service role via the FastAPI server.
-- We intentionally do NOT create policies for the authenticated role.

------------------------------------------------------------------------
-- Anon role: public (no-auth) access
------------------------------------------------------------------------
-- v1.0 has no public data surfaces that read from DB — the marketing pages
-- are static MDX. If we later add a /methodology data pull, add anon
-- SELECT policies here per table.

-- End of migration 0002.
