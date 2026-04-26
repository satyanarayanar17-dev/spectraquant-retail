/**
 * Next.js instrumentation hook — initialises Sentry on the server side.
 * Only runs when NEXT_PUBLIC_SENTRY_DSN is set; silently skips otherwise.
 * https://nextjs.org/docs/app/building-your-application/optimizing/instrumentation
 */
export async function register() {
  const dsn = process.env.NEXT_PUBLIC_SENTRY_DSN;
  if (!dsn) return;

  if (process.env.NEXT_RUNTIME === "nodejs") {
    const { init } = await import("@sentry/nextjs");
    init({
      dsn,
      environment: process.env.NODE_ENV,
      tracesSampleRate: 0.05,
    });
  }
}
