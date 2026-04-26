# SpectraQuant Retail — Operations Runbook

> **Audience:** Sid (founder / sole operator) in the first months of v1.0.  
> Keep this file updated whenever a new failure mode is discovered.

---

## 1. Ingest failure — Bhavcopy not fetched

**Symptom:** Dashboard shows "Data as of [stale date]" banner. `job_runs` has a row with `status = 'failed'` for `ingest_bhavcopy`.

**Cause:** NSE Bhavcopy URL format changes occasionally (the spec warns of this).

**Fix (< 5 min):**

1. Check the GitHub Actions log for the ingest cron job. Look for the HTTP status code returned.
2. Go to `apps/api/src/jobs/backfill_factor_returns.py` and update `NSE_BHAVCOPY_BASE_URL` in `.env` if the URL has moved.
3. If NSE is temporarily down, the job caches the last-good response. The stale-data banner appears but the dashboard keeps serving. No action needed; wait for NSE to recover.
4. As a last resort, manually download the Bhavcopy CSV from `https://www.nseindia.com/market-data/live-equity-market` and run:
   ```bash
   python -m apps.api.jobs.backfill_factor_returns \
     --start $(date -v-1d +%Y-%m-%d) \
     --end $(date +%Y-%m-%d) \
     --env production
   ```
5. Verify `job_runs` shows `status = 'success'` and the stale-data banner clears.

---

## 2. Webhook backlog — Razorpay retrying

**Symptom:** Razorpay dashboard shows pending/failed webhook deliveries. Subscriptions not activating.

**Cause:** The `/webhooks/razorpay` endpoint returned non-200, or Railway was down during delivery.

**Fix:**

1. Check Railway logs: `railway logs --tail 100 | grep webhooks`
2. Razorpay retries for up to 24 hours automatically. If Railway was briefly down, the events will replay — no manual action needed.
3. If the endpoint returned 400 (signature mismatch), verify `RAZORPAY_WEBHOOK_SECRET` in Railway matches the secret set in the Razorpay dashboard (Settings → Webhooks).
4. To manually reconcile a missed `subscription.activated` event:
   ```sql
   INSERT INTO subscriptions (user_id, razorpay_subscription_id, status, tier, period_start, period_end)
   VALUES ('<user_id>', '<rzp_sub_id>', 'active', 'pro', now(), now() + interval '30 days')
   ON CONFLICT (razorpay_subscription_id) DO UPDATE SET status = 'active';
   ```
5. Confirm in `payments` table that `razorpay_payment_id` row exists (idempotent UPSERT means re-delivery is safe).

---

## 3. Database restore — Supabase PITR

**When to use:** Data corruption, accidental DELETE without WHERE, migration gone wrong.

**Prerequisites:** Supabase Pro plan with PITR enabled (keep ≥ 7 days retention).

**Steps:**

1. Go to Supabase dashboard → Project → Database → Backups → Point in Time Recovery.
2. Select the timestamp just **before** the incident.
3. Supabase creates a new project with restored data. Do **not** restore over the live project — spin up a shadow project first.
4. Validate key tables in the shadow project: `symbols`, `portfolios`, `factor_scores`, `factor_returns`.
5. Once validated, update `SUPABASE_DB_URL` and `SUPABASE_URL` in Railway + Vercel to point to the restored project.
6. Run smoke test: `python scripts/perf_smoke.py --url https://api.spectraquant.in --token $TOKEN --reps 5`
7. Delete the old corrupt project only after a 24-hour soak period.

**RTO target:** < 2 hours. **RPO target:** < 1 hour (PITR granularity).

---

## 4. Razorpay account suspension

**Symptom:** Payments failing, Razorpay dashboard shows account suspended.

**Immediate actions (in order):**

1. Email `support@razorpay.com` with merchant ID and request for reason.
2. Do **not** refund manually during suspension — Razorpay holds funds, refunds may double.
3. Notify affected users via email (use Resend): "We are experiencing a temporary payment processing issue. No action needed on your part. Your subscription status is unaffected."
4. If suspension lasts > 48 hours, evaluate switching to Cashfree or PayU as fallback (separate integration, out of v1.0 scope).

**Manual refund SOP (v1.0 — use Razorpay dashboard, not API):**

1. Log into `https://dashboard.razorpay.com` → Payments.
2. Find the payment by `razorpay_payment_id` from the `payments` table.
3. Click Refund → Full amount.
4. Update `payments.status = 'refunded'` in Supabase:
   ```sql
   UPDATE payments SET status = 'refunded', refunded_at = now()
   WHERE razorpay_payment_id = '<id>';
   ```
5. If subscription should also be cancelled: run the cancel flow manually via API or SQL (see §billing cancel flow in user.py).

---

## 5. Key rotation

**When:** Suspected credential leak, periodic rotation (every 90 days recommended).

### HOLDINGS_ENC_KEY rotation

> This is the most sensitive key — it encrypts all user portfolios.

1. Generate new key: `openssl rand -hex 32`
2. Add `HOLDINGS_ENC_KEY_NEW` to Railway/Vercel alongside the existing key.
3. Write a one-off migration script that:
   - Reads each `portfolios.holdings_enc` with the old key (`pgp_sym_decrypt`)
   - Re-encrypts with the new key (`pgp_sym_encrypt`)
   - Updates the row
4. Verify a sample of portfolios decrypt correctly with the new key.
5. Remove `HOLDINGS_ENC_KEY` (old) and rename `HOLDINGS_ENC_KEY_NEW` → `HOLDINGS_ENC_KEY`.
6. Redeploy API.

### RAZORPAY_WEBHOOK_SECRET rotation

1. Generate new secret in Razorpay dashboard (Settings → Webhooks → Edit → regenerate).
2. Update `RAZORPAY_WEBHOOK_SECRET` in Railway env vars.
3. Redeploy API immediately — Razorpay starts using the new secret within minutes.

### SUPABASE_SERVICE_ROLE_KEY / JWT_SECRET

Contact Supabase support — these require coordination with Supabase Auth. Do not rotate without testing in a staging project first.

---

## 6. Emergency contacts

| Role | Contact | When to reach |
|------|---------|---------------|
| Supabase support | support@supabase.io | DB outage, RLS issue, PITR restore |
| Razorpay support | support@razorpay.com | Payment failures, account suspension |
| Vercel support | vercel.com/support | Web deploy failure, edge function errors |
| Railway support | railway.app/help | API container crash, deploy failure |
| Resend support | resend.com/support | Email deliverability, DNS verification |

---

## 7. Deploy checklist (pre-launch, one-time)

Run through this before flipping DNS to production:

- [ ] All env vars in `.env.example` set in Railway (API) and Vercel (web)
- [ ] `HOLDINGS_ENC_KEY` is a fresh 64-hex-char random value (not the placeholder)
- [ ] `RAZORPAY_WEBHOOK_SECRET` matches Razorpay dashboard
- [ ] Supabase Pro plan active with PITR enabled
- [ ] UptimeRobot monitors added for `https://spectraquant.in` and `https://api.spectraquant.in/health`
- [ ] Resend DNS shows SPF, DKIM, DMARC all **Verified** (not Pending)
- [ ] Test email sent to Gmail + Outlook — both land in inbox, not spam
- [ ] `dmarc=pass` visible in email headers (Gmail: "Show original")
- [ ] Sentry receiving test exception from both web and API
- [ ] PostHog receiving `signup_completed` event from a test login
- [ ] `scripts/perf_smoke.py` passes against production with p95 < 5s
- [ ] Lighthouse scores: Performance ≥ 80, Accessibility ≥ 90, Best Practices ≥ 90
- [ ] RLS verified: user A cannot see user B's portfolio via direct UUID access
- [ ] No `console.log` with sensitive data in browser devtools
- [ ] `NEXT_PUBLIC_BACKFILL_START_DATE` set to `April 21, 2023` in Vercel env vars
- [ ] Do **not** deploy on a Friday

---

## 8. Useful one-liners

```bash
# Tail Railway API logs
railway logs --tail 200

# Check job_runs table for recent failures
psql $SUPABASE_DB_URL -c "SELECT job_name, status, rows_written, started_at FROM job_runs ORDER BY started_at DESC LIMIT 20;"

# Re-run factor score backfill for a date range
python -m apps.api.jobs.backfill_factor_returns \
  --start 2024-01-01 --end 2024-01-31 --env production

# Validate backfill output
python -m apps.api.jobs.validate_backfill \
  --start 2024-01-01 --end 2024-01-31

# Force-clear settings cache (local dev)
python -c "from src.config import clear_settings_cache; clear_settings_cache()"

# Run compliance check locally
pnpm --filter web compliance:check

# Perf smoke against staging
python scripts/perf_smoke.py --url https://api-staging.spectraquant.in --token $TOKEN --reps 20
```
