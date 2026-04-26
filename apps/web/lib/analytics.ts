/**
 * Thin PostHog wrapper — tracks the five required product events.
 *
 * Only active when NEXT_PUBLIC_POSTHOG_KEY is set; all calls are no-ops otherwise.
 * Import and call from client components after user actions.
 *
 * Required events (spec Day 7 §observability):
 *   signup_completed      – after magic-link auth confirmed
 *   portfolio_analyzed    – after successful attribution run
 *   paywall_hit           – when a free-tier user hits a Pro gate
 *   checkout_started      – when Razorpay Checkout modal opens
 *   subscription_activated – on webhook subscription.activated (server-side)
 *     → the server logs this to PostHog via REST API in webhooks.py
 */
"use client";

type EventName =
  | "signup_completed"
  | "portfolio_analyzed"
  | "paywall_hit"
  | "checkout_started"
  | "subscription_activated";

type Properties = Record<string, string | number | boolean | null | undefined>;

function _ph(): { capture: (e: string, p?: Properties) => void } | null {
  if (typeof window === "undefined") return null;
  // PostHog attaches itself to window.posthog after the snippet loads
  const w = window as typeof window & { posthog?: { capture: (e: string, p?: Properties) => void } };
  return w.posthog ?? null;
}

export function track(event: EventName, properties?: Properties): void {
  _ph()?.capture(event, properties);
}
