"use client";

/**
 * Injects the PostHog browser snippet when NEXT_PUBLIC_POSTHOG_KEY is set.
 * Renders nothing visible — purely a side-effect provider.
 * Placed inside AppProviders so it mounts once per session.
 */
import { useEffect } from "react";

export function PostHogProvider() {
  useEffect(() => {
    const key = process.env.NEXT_PUBLIC_POSTHOG_KEY;
    const host = process.env.NEXT_PUBLIC_POSTHOG_HOST ?? "https://app.posthog.com";
    if (!key || typeof window === "undefined") return;

    // Skip if already initialised
    const w = window as typeof window & { posthog?: unknown };
    if (w.posthog) return;

    // Minimal PostHog snippet (no external script tag required in RSC)
    import("posthog-js").then(({ default: posthog }) => {
      posthog.init(key, {
        api_host: host,
        capture_pageview: true,
        persistence: "localStorage",
        autocapture: false, // manual event tracking only
      });
      w.posthog = posthog;
    });
  }, []);

  return null;
}
