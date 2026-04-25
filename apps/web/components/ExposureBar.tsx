import { FACTOR_BAR_CLASSES, FACTOR_LABELS, type FactorName } from "@/lib/factors";
import { cn } from "@/lib/utils";

type ExposureBarProps = {
  factor: FactorName;
  value: number;
};

const WIDTH_CLASSES = [
  "w-0",
  "w-[8%]",
  "w-[16%]",
  "w-[24%]",
  "w-[32%]",
  "w-[40%]",
  "w-[48%]",
  "w-[56%]",
  "w-[64%]",
  "w-[72%]",
  "w-[80%]",
  "w-[88%]",
  "w-full"
];

function widthClass(value: number) {
  const bucket = Math.min(WIDTH_CLASSES.length - 1, Math.round(Math.abs(value) * 4));
  return WIDTH_CLASSES[bucket];
}

export function ExposureBar({ factor, value }: ExposureBarProps) {
  const positive = value >= 0;
  const formatted = `${value >= 0 ? "+" : ""}${value.toFixed(2)}`;

  return (
    <div className="grid grid-cols-[112px_1fr_72px] items-center gap-4">
      <span className="text-sm font-medium text-secondary">{FACTOR_LABELS[factor]}</span>
      <div className="relative h-4 rounded-full bg-surface-2">
        <div className="absolute inset-y-0 left-1/2 w-px bg-border-strong" />
        <div
          className={cn(
            "absolute inset-y-0 rounded-full",
            FACTOR_BAR_CLASSES[factor],
            widthClass(value),
            positive ? "left-1/2 rounded-l-none" : "right-1/2 rounded-r-none"
          )}
        />
      </div>
      <span className="font-mono text-sm text-primary">{formatted}</span>
    </div>
  );
}
