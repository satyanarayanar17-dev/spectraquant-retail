import { FACTORS, type FactorName } from "@/lib/factors";
import type { FactorScoresLatestResponse, HoldingInput } from "@/lib/api";

export function parseHoldingsCsv(raw: string): HoldingInput[] {
  const rows = raw
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);

  if (rows.length === 0) {
    return [];
  }

  const [headerLine, ...dataLines] = rows;
  const header = headerLine
    .split(",")
    .map((column) => column.trim().toLowerCase());
  const hasPriceColumns = header.includes("qty") && header.includes("avg_price");
  const hasWeightColumns = header.includes("weight");

  if (!header.includes("symbol") || (!hasPriceColumns && !hasWeightColumns)) {
    throw new Error("CSV requires symbol plus qty/avg_price or weight columns.");
  }

  return dataLines.map((line) => {
    const values = line.split(",").map((value) => value.trim());
    const row = Object.fromEntries(header.map((key, index) => [key, values[index]]));

    return {
      symbol: (row.symbol ?? "").toUpperCase(),
      qty: row.qty ? Number(row.qty) : undefined,
      avg_price: row.avg_price ? Number(row.avg_price) : undefined,
      weight: row.weight ? Number(row.weight) : undefined
    };
  });
}

export function normalizeHoldingsWeights(holdings: HoldingInput[]) {
  const withWeights = holdings.every((holding) => typeof holding.weight === "number");
  const totals = holdings.map((holding) => {
    if (withWeights) {
      return holding.weight ?? 0;
    }
    return (holding.qty ?? 0) * (holding.avg_price ?? 0);
  });

  const total = totals.reduce((sum, value) => sum + value, 0);
  if (total === 0) {
    throw new Error("Total holding weight is zero.");
  }

  return holdings.map((holding, index) => ({
    symbol: holding.symbol.toUpperCase(),
    weight: totals[index] / total
  }));
}

export function computeClientExposures(
  holdings: HoldingInput[],
  factorScores: FactorScoresLatestResponse
) {
  const weights = normalizeHoldingsWeights(holdings);
  const weightMap = Object.fromEntries(weights.map((holding) => [holding.symbol, holding.weight]));

  return FACTORS.map((factor) => ({
    factor,
    value: Object.entries(factorScores.scores).reduce((sum, [symbol, scores]) => {
      return sum + (weightMap[symbol] ?? 0) * (scores[factor] ?? 0);
    }, 0)
  }));
}

export function mergeFactorSeries(
  responses: Array<{ factor: FactorName; dates: string[]; values: number[] }>
) {
  const bucket = new Map<string, Partial<Record<FactorName, number>>>();

  responses.forEach((response) => {
    response.dates.forEach((date, index) => {
      const entry = bucket.get(date) ?? {};
      entry[response.factor] = response.values[index];
      bucket.set(date, entry);
    });
  });

  return Array.from(bucket.entries())
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([date, values]) => ({
      date,
      ...FACTORS.reduce<Record<FactorName, number | null>>(
        (acc, factor) => ({
          ...acc,
          [factor]: values[factor] ?? null
        }),
        {
          momentum: null,
          value: null,
          quality: null,
          low_vol: null,
          size: null,
          composite: null
        }
      )
    }));
}
