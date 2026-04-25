import copy from "@/lib/copy.json";

export function DisclaimerBanner() {
  return (
    <div className="rounded-lg border border-info/30 bg-info/10 px-4 py-3 text-sm text-primary">
      {copy.disclaimer.banner}
    </div>
  );
}
