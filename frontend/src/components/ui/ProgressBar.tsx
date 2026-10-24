import * as React from "react";

import { cn } from "@/lib/utils";

export type ProgressStatus = "ok" | "watch" | "breach" | "info";

const fillStyles: Record<ProgressStatus, string> = {
  ok: "bg-ok",
  watch: "bg-watch",
  breach: "bg-breach",
  info: "bg-info",
};

export interface ProgressBarProps {
  label: string;
  value: number;
  status?: ProgressStatus;
  showValue?: boolean;
  className?: string;
}

export function ProgressBar({
  label,
  value,
  status = "info",
  showValue = true,
  className,
}: ProgressBarProps) {
  const labelId = React.useId();
  const clamped = Math.max(0, Math.min(100, Math.round(value)));

  return (
    <div className={cn("w-full", className)}>
      <div className="mb-1.5 flex items-center justify-between gap-3">
        <span id={labelId} className="text-13 font-medium text-ink-700">
          {label}
        </span>
        {showValue ? (
          <span className="text-12 tabular-nums text-ink-500">{clamped}%</span>
        ) : null}
      </div>
      <div
        role="progressbar"
        aria-labelledby={labelId}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={clamped}
        className="h-2 w-full overflow-hidden rounded-input bg-ink-100"
      >
        <div
          className={cn(
            "h-full rounded-input transition-[width]",
            fillStyles[status],
          )}
          style={{ width: `${clamped}%` }}
        />
      </div>
    </div>
  );
}
