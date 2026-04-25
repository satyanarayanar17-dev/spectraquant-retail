"use client";

import { ChangeEvent, FormEvent, useMemo, useState } from "react";

import copy from "@/lib/copy.json";
import { computeClientExposures, parseHoldingsCsv } from "@/lib/portfolio";
import { getLatestFactorScores, uploadPortfolio, type HoldingInput } from "@/lib/api";
import type { FactorName } from "@/lib/factors";
import { useRequiredSession } from "@/lib/use-required-session";
import { DisclaimerBanner } from "@/components/DisclaimerBanner";
import { ExposureBar } from "@/components/ExposureBar";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Textarea } from "@/components/ui/textarea";

export default function PortfolioPage() {
  const { loading, token } = useRequiredSession();
  const [portfolioName, setPortfolioName] = useState("Core holdings");
  const [manualRows, setManualRows] = useState("");
  const [holdings, setHoldings] = useState<HoldingInput[]>([]);
  const [status, setStatus] = useState<"idle" | "loading" | "error">("idle");
  const [message, setMessage] = useState<string | null>(null);
  const [exposures, setExposures] = useState<Array<{ factor: FactorName; value: number }>>([]);

  const previewRows = useMemo(
    () => holdings.map((holding) => ({ ...holding, symbol: holding.symbol.toUpperCase() })),
    [holdings]
  );

  function updateFromRawText(raw: string) {
    setManualRows(raw);
    try {
      const parsed = parseHoldingsCsv(raw);
      setHoldings(parsed);
      setMessage(null);
    } catch (error) {
      if (raw.trim().length === 0) {
        setHoldings([]);
        setMessage(null);
        return;
      }
      setMessage(error instanceof Error ? error.message : copy.portfolio.error);
    }
  }

  async function handleFileUpload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }
    const text = await file.text();
    updateFromRawText(text);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token || holdings.length === 0) {
      return;
    }

    setStatus("loading");
    setMessage(null);

    try {
      const upload = await uploadPortfolio(
        {
          name: portfolioName,
          holdings
        },
        token
      );

      const factorScores = await getLatestFactorScores(
        holdings.map((holding) => holding.symbol.toUpperCase()),
        token
      );
      const nextExposures = computeClientExposures(holdings, factorScores);
      setExposures(nextExposures);
      window.localStorage.setItem("sq:lastPortfolioId", upload.portfolio_id);
      setMessage(`${copy.portfolio.successPrefix} ${upload.portfolio_id}`);
      setStatus("idle");
    } catch (error) {
      setStatus("error");
      setMessage(error instanceof Error ? error.message : copy.portfolio.error);
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
          {copy.portfolio.eyebrow}
        </p>
        <h2 className="mt-2 text-3xl font-semibold text-primary">{copy.portfolio.title}</h2>
        <p className="mt-2 max-w-2xl text-sm text-secondary">{copy.portfolio.subtitle}</p>
      </div>

      <DisclaimerBanner />

      <div className="grid gap-6 lg:grid-cols-[1.15fr_0.85fr]">
        <Card>
          <CardHeader>
            <CardTitle>{copy.portfolio.title}</CardTitle>
            <CardDescription>{copy.portfolio.subtitle}</CardDescription>
          </CardHeader>
          <CardContent>
            <form className="space-y-4" onSubmit={handleSubmit}>
              <div className="space-y-2">
                <Label htmlFor="portfolio-name">{copy.portfolio.nameLabel}</Label>
                <Input
                  id="portfolio-name"
                  value={portfolioName}
                  onChange={(event) => setPortfolioName(event.target.value)}
                  placeholder={copy.portfolio.namePlaceholder}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="manual-entry">{copy.portfolio.manualLabel}</Label>
                <p className="text-sm text-secondary">{copy.portfolio.manualHelper}</p>
                <Textarea
                  id="manual-entry"
                  value={manualRows}
                  onChange={(event) => updateFromRawText(event.target.value)}
                  placeholder={copy.portfolio.manualPlaceholder}
                />
              </div>

              <div className="space-y-2">
                <Label htmlFor="portfolio-file">{copy.portfolio.fileLabel}</Label>
                <p className="text-sm text-secondary">{copy.portfolio.fileHelper}</p>
                <Input
                  id="portfolio-file"
                  type="file"
                  accept=".csv,text/csv"
                  onChange={handleFileUpload}
                />
              </div>

              <Button type="submit" disabled={status === "loading" || holdings.length === 0}>
                {status === "loading" ? copy.portfolio.submitting : copy.portfolio.submit}
              </Button>

              {message ? (
                <p className={status === "error" ? "text-sm text-neg" : "text-sm text-secondary"}>
                  {message}
                </p>
              ) : null}
            </form>
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>{copy.portfolio.previewTitle}</CardTitle>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Symbol</TableHead>
                    <TableHead>Qty</TableHead>
                    <TableHead>Avg price</TableHead>
                    <TableHead>Weight</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {previewRows.map((holding) => (
                    <TableRow key={`${holding.symbol}-${holding.qty ?? holding.weight ?? 0}`}>
                      <TableCell className="font-mono">{holding.symbol}</TableCell>
                      <TableCell className="font-mono">{holding.qty ?? "—"}</TableCell>
                      <TableCell className="font-mono">
                        {holding.avg_price ? holding.avg_price.toFixed(2) : "—"}
                      </TableCell>
                      <TableCell className="font-mono">
                        {holding.weight ? holding.weight.toFixed(4) : "—"}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>{copy.portfolio.exposuresTitle}</CardTitle>
              <CardDescription>{copy.portfolio.exposuresSubtitle}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {exposures.length > 0 ? (
                exposures.map((entry) => (
                  <ExposureBar key={entry.factor} factor={entry.factor} value={entry.value} />
                ))
              ) : (
                <p className="text-sm text-secondary">{copy.portfolio.exposuresSubtitle}</p>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </section>
  );
}
