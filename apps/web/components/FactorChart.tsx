"use client";

import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";

import copy from "@/lib/copy.json";
import {
  FACTORS,
  FACTOR_BAR_CLASSES,
  FACTOR_LABELS,
  FACTOR_STROKES,
  type FactorName,
} from "@/lib/factors";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

type ChartPoint = {
  date: string;
} & Partial<Record<FactorName, number | null>>;

type FactorChartProps = {
  data: ChartPoint[];
};

const axisFormatter = new Intl.DateTimeFormat("en-IN", {
  timeZone: "Asia/Kolkata",
  month: "short",
  year: "2-digit"
});

function formatDateLabel(value: string) {
  return axisFormatter.format(new Date(`${value}T00:00:00Z`));
}

type TooltipEntry = {
  dataKey: FactorName;
  value: number;
};

type FactorTooltipProps = {
  active?: boolean;
  payload?: TooltipEntry[];
  label?: string;
};

function FactorTooltip({ active, payload, label }: FactorTooltipProps) {
  if (!active || !payload?.length || !label) {
    return null;
  }

  return (
    <div className="rounded-lg border border-border-subtle bg-surface-2 px-3 py-2 shadow-xl">
      <p className="mb-2 text-xs uppercase tracking-[0.12em] text-tertiary">
        {formatDateLabel(label)}
      </p>
      <div className="space-y-1">
        {payload.map((entry) => (
          <div key={entry.dataKey} className="flex items-center justify-between gap-3 text-sm">
            <span className="flex items-center gap-2">
              <span className={`h-2 w-2 rounded-full ${FACTOR_BAR_CLASSES[entry.dataKey]}`} />
              {FACTOR_LABELS[entry.dataKey]}
            </span>
            <span className="font-mono text-primary">{entry.value.toFixed(4)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export function FactorChart({ data }: FactorChartProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{copy.dashboard.title}</CardTitle>
        <CardDescription>{copy.dashboard.subtitle}</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="h-[360px]">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data}>
              <CartesianGrid
                strokeDasharray="3 3"
                stroke="hsl(var(--border-subtle))"
                vertical={false}
              />
              <XAxis
                dataKey="date"
                tickFormatter={formatDateLabel}
                tick={{ fill: "hsl(var(--text-tertiary))", fontSize: 12 }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                tick={{ fill: "hsl(var(--text-tertiary))", fontSize: 12 }}
                axisLine={false}
                tickLine={false}
                width={72}
              />
              <Tooltip content={<FactorTooltip />} />
              <Legend />
              {FACTORS.map((factor) => (
                <Line
                  key={factor}
                  dataKey={factor}
                  name={FACTOR_LABELS[factor]}
                  type="monotone"
                  stroke={FACTOR_STROKES[factor]}
                  strokeWidth={2}
                  dot={false}
                  activeDot={{ r: 4 }}
                  isAnimationActive
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
        <p className="text-xs text-tertiary">{copy.dashboard.footnote}</p>
      </CardContent>
    </Card>
  );
}
