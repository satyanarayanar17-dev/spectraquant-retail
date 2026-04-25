import copy from "@/lib/copy.json";

export const FACTORS = [
  "momentum",
  "value",
  "quality",
  "low_vol",
  "size",
  "composite",
] as const;

export type FactorName = (typeof FACTORS)[number];

export const FACTOR_LABELS: Record<FactorName, string> = copy.factors;

export const FACTOR_STROKES: Record<FactorName, string> = {
  momentum: "#5AC8FA",
  value: "#2DD4BF",
  quality: "#A78BFA",
  low_vol: "#FCD34D",
  size: "#F472B6",
  composite: "#94A3B8"
};

export const FACTOR_BAR_CLASSES: Record<FactorName, string> = {
  momentum: "bg-factor-momentum",
  value: "bg-factor-value",
  quality: "bg-factor-quality",
  low_vol: "bg-factor-low-vol",
  size: "bg-factor-size",
  composite: "bg-factor-composite"
};
