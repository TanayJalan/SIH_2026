import * as React from "react";

import { cn } from "@/lib/utils";

export type RiskLevel = "low" | "medium" | "high";

const riskStyles: Record<RiskLevel, { className: string; label: string }> = {
  low: {
    className: "bg-ok-soft text-ok-strong",
    label: "Low risk",
  },
  medium: {
    className: "bg-watch-soft text-watch-strong",
    label: "Medium risk",
  },
  high: {
    className: "bg-breach-soft text-breach-strong",
    label: "High risk",
  },
};

export interface RiskBadgeProps
  extends React.HTMLAttributes<HTMLSpanElement> {
  level: RiskLevel;
}

export function RiskBadge({
  level,
  className,
  children,
  ...props
}: RiskBadgeProps) {
  const style = riskStyles[level];

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-input px-2 py-0.5 text-12 font-medium",
        style.className,
        className,
      )}
      {...props}
    >
      {children ?? style.label}
    </span>
  );
}
