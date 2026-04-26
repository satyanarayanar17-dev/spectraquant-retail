"use client";

import { useState } from "react";
import { useRequiredSession } from "@/lib/use-required-session";
import { cancelSubscription } from "@/lib/api";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import copy from "@/lib/copy.json";

const INCLUDED_FEATURES = [
  "Full factor attribution (6 factors)",
  "Unlimited portfolio analysis",
  "Historical factor returns (3 years)",
  "Priority support",
];

function formatIST(isoString: string): string {
  return new Date(isoString).toLocaleDateString("en-IN", {
    timeZone: "Asia/Kolkata",
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

export default function BillingPage() {
  const { loading, token } = useRequiredSession();
  const [cancelSuccess, setCancelSuccess] = useState<string | null>(null);
  const [cancelling, setCancelling] = useState(false);

  if (loading) {
    return (
      <Card>
        <CardContent className="p-6 text-secondary">{copy.states.loading}</CardContent>
      </Card>
    );
  }

  if (!token) {
    return null;
  }

  async function handleCancel() {
    const confirmed = window.confirm(
      "Cancel your Pro subscription? You will retain access until the end of the current billing period."
    );
    if (!confirmed) return;

    setCancelling(true);
    try {
      const result = await cancelSubscription(token!);
      setCancelSuccess(result.access_until);
    } catch (err) {
      console.error("Cancellation failed", err);
    } finally {
      setCancelling(false);
    }
  }

  return (
    <section className="space-y-8 max-w-2xl">
      <div>
        <p className="text-xs uppercase tracking-[0.24em] text-tertiary">Billing</p>
        <h2 className="mt-2 text-3xl font-semibold text-primary">Subscription</h2>
      </div>

      {/* Current plan */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <CardTitle>Current plan</CardTitle>
          <Badge variant="outline" className="text-sm px-3 py-1">
            Pro
          </Badge>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-2xl font-semibold text-primary">
            ₹1,699<span className="text-sm font-normal text-secondary">/mo</span>
          </p>

          <div>
            <p className="text-sm font-medium text-primary mb-2">What&#39;s included</p>
            <ul className="space-y-1">
              {INCLUDED_FEATURES.map((feature) => (
                <li key={feature} className="flex items-start gap-2 text-sm text-secondary">
                  <span className="mt-0.5 text-xs text-tertiary">—</span>
                  {feature}
                </li>
              ))}
            </ul>
          </div>
        </CardContent>
      </Card>

      {/* Cancel subscription */}
      <Card>
        <CardHeader>
          <CardTitle>Cancel subscription</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {cancelSuccess ? (
            <p className="text-sm text-secondary">
              Your subscription has been cancelled. You will retain access until{" "}
              <span className="font-medium text-primary">{formatIST(cancelSuccess)}</span>.
            </p>
          ) : (
            <>
              <p className="text-sm text-secondary">
                Cancelling will downgrade your account to the Starter plan at the end of your
                current billing period.
              </p>
              <Button variant="outline" onClick={handleCancel} disabled={cancelling}>
                {cancelling ? "Cancelling..." : "Cancel subscription"}
              </Button>
            </>
          )}
        </CardContent>
      </Card>
    </section>
  );
}
