import { FACTORS, type FactorName } from "@/lib/factors";

export type HoldingInput = {
  symbol: string;
  qty?: number;
  avg_price?: number;
  weight?: number;
};

export type FactorReturnsResponse = {
  factor: FactorName;
  dates: string[];
  values: number[];
};

export type FactorScoresLatestResponse = {
  score_date: string;
  scores: Record<string, Partial<Record<FactorName, number>>>;
};

export type PortfolioUploadRequest = {
  name?: string;
  holdings: HoldingInput[];
};

export type PortfolioUploadResponse = {
  portfolio_id: string;
};

export type PortfolioResponse = {
  id: string;
  name: string;
  holdings: HoldingInput[];
};

export type FactorBeta = {
  beta: number;
  se: number;
  ci_low: number;
  ci_high: number;
  pvalue: number;
  significant: boolean;
  contribution_bps: number;
};

export type AttributionResult = {
  alpha: number;
  alpha_pvalue: number;
  alpha_ci_low: number;
  alpha_ci_high: number;
  betas: Record<string, FactorBeta>;
  r_squared: number;
  adj_r_squared: number;
  n_obs: number;
  condition_number: number;
  collinearity_warning: boolean;
  hac_lags: number;
  window_days: number;
  residual_series: number[];
};

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ??
  process.env.NEXT_PUBLIC_API_BASE_URL ??
  "http://localhost:8000";

type ApiFetchOptions = {
  method?: "GET" | "POST";
  token: string;
  body?: unknown;
};

async function apiFetch<T>(path: string, options: ApiFetchOptions): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: options.method ?? "GET",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${options.token}`
    },
    body: options.body ? JSON.stringify(options.body) : undefined,
    cache: "no-store"
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(errorText || `Request failed with status ${response.status}`);
  }

  return (await response.json()) as T;
}

export async function getFactorReturns(
  factor: FactorName,
  days: number,
  token: string
) {
  return apiFetch<FactorReturnsResponse>(
    `/api/v1/factors/returns?factor=${factor}&days=${days}`,
    { token }
  );
}

export async function getDashboardFactorSeries(token: string, days = 252) {
  return Promise.all(FACTORS.map((factor) => getFactorReturns(factor, days, token)));
}

export async function getLatestFactorScores(symbols: string[], token: string) {
  const params = new URLSearchParams({ symbols: symbols.join(",") });
  return apiFetch<FactorScoresLatestResponse>(
    `/api/v1/factors/scores/latest?${params.toString()}`,
    { token }
  );
}

export async function uploadPortfolio(
  payload: PortfolioUploadRequest,
  token: string
) {
  return apiFetch<PortfolioUploadResponse>("/api/v1/portfolio/upload", {
    method: "POST",
    token,
    body: payload
  });
}

export async function getPortfolio(portfolioId: string, token: string) {
  return apiFetch<PortfolioResponse>(`/api/v1/portfolio/${portfolioId}`, { token });
}

export async function runAnalysis(
  portfolioId: string,
  token: string,
  windowDays = 252
) {
  return apiFetch<AttributionResult>("/api/v1/analysis/run", {
    method: "POST",
    token,
    body: {
      portfolio_id: portfolioId,
      window_days: windowDays
    }
  });
}
