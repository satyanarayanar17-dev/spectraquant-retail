"use client";

import { FormEvent, useEffect, useState } from "react";

import copy from "@/lib/copy.json";
import { runAnalysis, type AttributionResult } from "@/lib/api";
import { useRequiredSession } from "@/lib/use-required-session";
import { BetaTable } from "@/components/BetaTable";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function AnalysisPage() {
  const { loading, token } = useRequiredSession();
  const [portfolioId, setPortfolioId] = useState("");
  const [status, setStatus] = useState<"idle" | "loading" | "error">("idle");
  const [message, setMessage] = useState<string | null>(null);
  const [result, setResult] = useState<AttributionResult | null>(null);

  useEffect(() => {
    const lastPortfolioId = window.localStorage.getItem("sq:lastPortfolioId");
    if (lastPortfolioId) {
      setPortfolioId(lastPortfolioId);
    }
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token || !portfolioId) {
      return;
    }

    setStatus("loading");
    setMessage(null);

    try {
      const nextResult = await runAnalysis(portfolioId, token);
      setResult(nextResult);
      setStatus("idle");
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : copy.analysis.error);
    }
  }

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

  return (
    <section className="space-y-6">
      <div>
        <p className="text-xs uppercase tracking-[0.24em] text-tertiary">
          {copy.analysis.eyebrow}
        </p>
        <h2 className="mt-2 text-3xl font-semibold text-primary">{copy.analysis.title}</h2>
        <p className="mt-2 max-w-2xl text-sm text-secondary">{copy.analysis.subtitle}</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>{copy.analysis.title}</CardTitle>
          <CardDescription>{copy.analysis.subtitle}</CardDescription>
        </CardHeader>
        <CardContent>
          <form className="flex flex-col gap-4 md:flex-row md:items-end" onSubmit={handleSubmit}>
            <div className="flex-1 space-y-2">
              <Label htmlFor="portfolio-id">{copy.analysis.portfolioIdLabel}</Label>
              <Input
                id="portfolio-id"
                value={portfolioId}
                onChange={(event) => setPortfolioId(event.target.value)}
                placeholder={copy.analysis.portfolioIdPlaceholder}
              />
            </div>
            <Button type="submit" disabled={status === "loading" || portfolioId.length === 0}>
              {status === "loading" ? copy.analysis.submitting : copy.analysis.submit}
            </Button>
          </form>

          {message ? <p className="mt-4 text-sm text-neg">{message}</p> : null}
        </CardContent>
      </Card>

      {result ? (
        <div className="grid gap-6 xl:grid-cols-[0.8fr_1.2fr]">
          <Card>
            <CardHeader>
              <CardTitle>{copy.analysis.title}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-3 sm:grid-cols-2">
                <div className="rounded-lg border border-border-subtle bg-surface-2 p-4">
                  <p className="text-xs uppercase tracking-[0.18em] text-tertiary">
                    {copy.analysis.alpha}
                  </p>
                  <p className="mt-2 font-mono text-2xl text-primary">{result.alpha.toFixed(4)}</p>
                </div>
                <div className="rounded-lg border border-border-subtle bg-surface-2 p-4">
                  <p className="text-xs uppercase tracking-[0.18em] text-tertiary">
                    {copy.analysis.rSquared}
                  </p>
                  <p className="mt-2 font-mono text-2xl text-primary">
                    {result.r_squared.toFixed(3)}
                  </p>
                </div>
                <div className="rounded-lg border border-border-subtle bg-surface-2 p-4">
                  <p className="text-xs uppercase tracking-[0.18em] text-tertiary">
                    {copy.analysis.adjRSquared}
                  </p>
                  <p className="mt-2 font-mono text-2xl text-primary">
                    {result.adj_r_squared.toFixed(3)}
                  </p>
                </div>
                <div className="rounded-lg border border-border-subtle bg-surface-2 p-4">
                  <p className="text-xs uppercase tracking-[0.18em] text-tertiary">
                    {copy.analysis.conditionNumber}
                  </p>
                  <p className="mt-2 font-mono text-2xl text-primary">
                    {result.condition_number.toFixed(0)}
                  </p>
                </div>
              </div>

              <Badge variant={result.alpha_pvalue < 0.05 ? "success" : "secondary"}>
                p = {result.alpha_pvalue.toFixed(4)}
              </Badge>

              {result.collinearity_warning ? (
                <div className="rounded-lg border border-accent/30 bg-accent/10 px-4 py-3 text-sm text-primary">
                  {copy.analysis.collinearity}
                </div>
              ) : null}
            </CardContent>
          </Card>

          <BetaTable result={result} />
        </div>
      ) : (
        <Card>
          <CardContent className="p-6 text-secondary">{copy.analysis.empty}</CardContent>
        </Card>
      )}
    </section>
  );
}
