import { cn } from "@/lib/utils";

export type StatDeltaTone = "positive" | "negative" | "neutral";

export interface StatProps {
  figure: string;
  caption: string;
  delta: string;
  deltaTone?: StatDeltaTone;
  className?: string;
}

const deltaStyles: Record<StatDeltaTone, string> = {
  positive: "text-ok-strong",
  negative: "text-breach-strong",
  neutral: "text-ink-500",
};

export function Stat({
  figure,
  caption,
  delta,
  deltaTone = "neutral",
  className,
}: StatProps) {
  return (
    <div
      className={cn(
        "rounded-panel border border-line bg-surface p-4",
        className,
      )}
    >
      <p className="text-12 font-medium text-ink-500">{caption}</p>
      <p className="mt-1 font-serif text-28 font-semibold tabular-nums text-ink">
        {figure}
      </p>
      <p className={cn("mt-1 text-12 font-medium", deltaStyles[deltaTone])}>
        {delta}
      </p>
    </div>
  );
}
