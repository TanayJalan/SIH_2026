import * as React from "react";

import { cn } from "@/lib/utils";

export type StatusPillTone =
  | "compliant"
  | "watch"
  | "breach"
  | "info"
  | "neutral";

const statusStyles: Record<
  StatusPillTone,
  { container: string; dot: string; label: string }
> = {
  compliant: {
    container: "bg-ok-soft text-ok-strong",
    dot: "bg-ok",
    label: "Compliant",
  },
  watch: {
    container: "bg-watch-soft text-watch-strong",
    dot: "bg-watch",
    label: "Watch",
  },
  breach: {
    container: "bg-breach-soft text-breach-strong",
    dot: "bg-breach",
    label: "Breach",
  },
  info: {
    container: "bg-info-soft text-info-strong",
    dot: "bg-info",
    label: "In progress",
  },
  neutral: {
    container: "bg-neutral-soft text-neutral-strong",
    dot: "bg-neutral",
    label: "Not started",
  },
};

export interface StatusPillProps extends React.HTMLAttributes<HTMLSpanElement> {
  status: StatusPillTone;
}

export function StatusPill({
  status,
  className,
  children,
  ...props
}: StatusPillProps) {
  const style = statusStyles[status];

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-pill px-2.5 py-1 text-12 font-medium",
        style.container,
        className,
      )}
      {...props}
    >
      <span
        aria-hidden="true"
        className={cn("size-1.5 shrink-0 rounded-pill", style.dot)}
      />
      {children ?? style.label}
    </span>
  );
}
