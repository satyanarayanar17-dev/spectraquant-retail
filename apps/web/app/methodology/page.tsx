import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Factor Methodology — SpectraQuant Retail",
  description:
    "How SpectraQuant computes momentum, value, quality, low-volatility, and size factor scores for Indian equities.",
};

export default function MethodologyPage() {
  return (
    <article className="prose prose-invert max-w-3xl space-y-10">
      <div>
        <p className="text-xs uppercase tracking-[0.24em] text-tertiary">Methodology</p>
        <h2 className="mt-2 text-3xl font-semibold text-primary">Factor methodology</h2>
        <p className="mt-2 text-sm text-secondary">
          How SpectraQuant computes and back-tests the five factor return series for the NSE
          universe.
        </p>
      </div>

      <section className="space-y-4">
        <h3 className="text-xl font-semibold text-primary">Overview</h3>
        <p className="text-sm text-secondary leading-relaxed">
          SpectraQuant decomposes Indian equity portfolio returns into five systematic factors:
          momentum, value, quality, low-volatility, and size. Each factor is constructed as a
          long-only return series on the NSE universe, rebalanced monthly. Factor scores are
          cross-sectionally ranked and z-scored within the investable universe on each scoring date.
        </p>
      </section>

      <section className="space-y-4">
        <h3 className="text-xl font-semibold text-primary">Factors defined</h3>
        <div className="space-y-3 text-sm text-secondary leading-relaxed">
          <p>
            <span className="font-medium text-primary">Momentum</span> — 12-month total return
            excluding the most recent month (12-1 momentum), consistent with academic literature on
            price continuation. Computed from adjusted close prices sourced from the NSE Bhavcopy.
          </p>
          <p>
            <span className="font-medium text-primary">Value</span> — composite of up to three
            inputs: earnings yield (E/P), book-to-price (B/P), and EV/EBITDA inverse. At least two
            inputs are required to produce a score; a single-input result is set to NULL. Fundamental
            data is sourced from public filings via yfinance. Coverage on mid-cap EV/EBITDA is
            approximately 70%.
          </p>
          <p>
            <span className="font-medium text-primary">Quality</span> — return on equity (ROE),
            gross profit margin, and debt-to-equity ratio combined into a single z-scored composite.
            Higher is better.
          </p>
          <p>
            <span className="font-medium text-primary">Low-volatility</span> — inverse of
            annualised 252-day realised volatility computed from daily log returns. Lower realised
            volatility maps to a higher factor score.
          </p>
          <p>
            <span className="font-medium text-primary">Size</span> — inverse log market
            capitalisation as of the scoring date. Smaller stocks receive a higher size factor score,
            consistent with the Fama-French small-minus-big construction.
          </p>
        </div>
      </section>

      <section className="space-y-4">
        <h3 className="text-xl font-semibold text-primary">Trading calendar</h3>
        <p className="text-sm text-secondary leading-relaxed">
          All date arithmetic uses the NSE trading calendar via{" "}
          <code className="font-mono text-xs bg-surface-elevated px-1 py-0.5 rounded">
            pandas_market_calendars.get_calendar(&quot;XNSE&quot;)
          </code>
          . Scores are computed on the last trading day of each calendar month. Return series are
          chain-linked across monthly rebalances.
        </p>
      </section>

      <section className="space-y-4">
        <h3 className="text-xl font-semibold text-primary">Attribution model</h3>
        <p className="text-sm text-secondary leading-relaxed">
          Portfolio factor attribution is estimated via OLS regression of portfolio returns against
          the five factor return series. Standard errors are computed using a Newey-West
          heteroskedasticity and autocorrelation consistent (HAC) estimator. The condition number of
          the factor covariance matrix is reported; a condition number above 30 triggers a
          collinearity warning, indicating that individual beta estimates should be interpreted with
          caution. The combined R² of the model remains the most reliable summary statistic in such
          cases.
        </p>
      </section>

      <section className="space-y-4">
        <h3 className="text-xl font-semibold text-primary">Data history and back-test disclosures</h3>
        <p className="text-sm text-secondary leading-relaxed">
          The factor return series presented in this product begins on{" "}
          {process.env.NEXT_PUBLIC_BACKFILL_START_DATE ?? "April 21, 2023"}.
          Return data before this date does not exist in the SpectraQuant system.
          Factor scores and returns for the period from{" "}
          {process.env.NEXT_PUBLIC_BACKFILL_START_DATE ?? "April 21, 2023"} to the
          present were computed retrospectively using historical price and fundamental
          data. Back-tested factor returns are subject to look-ahead bias, overfitting,
          and other limitations not present in live returns. Past factor performance
          does not guarantee future results.
        </p>
      </section>

      <section className="space-y-4">
        <h3 className="text-xl font-semibold text-primary">Disclaimer</h3>
        <p className="text-sm text-secondary leading-relaxed">
          All information presented by SpectraQuant is for informational and analytical purposes
          only. Nothing on this platform constitutes investment advice or a solicitation to transact
          in any security. Factor exposures and attribution outputs describe historical statistical
          relationships and do not imply any future outcome.
        </p>
      </section>
    </article>
  );
}
