"use client";

import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import copy from "@/lib/copy.json";
import { getDashboardFactorSeries } from "@/lib/api";
import { mergeFactorSeries } from "@/lib/portfolio";
import { useRequiredSession } from "@/lib/use-required-session";
import { FactorChart } from "@/components/FactorChart";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export default function DashboardPage() {
  const { loading, token } = useRequiredSession();
  const factorQuery = useQuery({
    queryKey: ["dashboard-factor-series", token],
    queryFn: async () => getDashboardFactorSeries(token ?? ""),
    enabled: Boolean(token)
  });

  const chartData = useMemo(
    () => (factorQuery.data ? mergeFactorSeries(factorQuery.data) : []),
    [factorQuery.data]
  );

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

  if (factorQuery.isError) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>{copy.dashboard.title}</CardTitle>
          <CardDescription>{copy.dashboard.subtitle}</CardDescription>
        </CardHeader>
        <CardContent className="text-neg">{copy.dashboard.empty}</CardContent>
      </Card>
    );
  }

  return (
    <section className="space-y-6">
      <div>
        <p className="text-xs uppercase tracking-[0.24em] text-tertiary">
          {copy.dashboard.eyebrow}
        </p>
        <h2 className="mt-2 text-3xl font-semibold text-primary">{copy.dashboard.title}</h2>
        <p className="mt-2 max-w-2xl text-sm text-secondary">{copy.dashboard.subtitle}</p>
      </div>
      {chartData.length > 0 ? (
        <FactorChart data={chartData} />
      ) : (
        <Card>
          <CardContent className="p-6 text-secondary">{copy.dashboard.empty}</CardContent>
        </Card>
      )}
    </section>
  );
}
