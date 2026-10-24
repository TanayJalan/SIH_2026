import { cn } from "@/lib/utils";

export type SlaState = "ok" | "watch" | "breach";

const stateLabels: Record<SlaState, string> = {
  ok: "on track",
  watch: "watch",
  breach: "breach",
};

const ringStyles: Record<SlaState, string> = {
  ok: "stroke-ok",
  watch: "stroke-watch",
  breach: "stroke-breach",
};

export interface SlaRingProps {
  /** Percentage of the SLA window that has elapsed, from 0 to 100. */
  value: number;
  daysLeft: number;
  state: SlaState;
  label?: string;
  className?: string;
}

const RADIUS = 16;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

export function SlaRing({
  value,
  daysLeft,
  state,
  label,
  className,
}: SlaRingProps) {
  const elapsed = Math.max(0, Math.min(100, value));
  const offset = CIRCUMFERENCE * (1 - elapsed / 100);

  return (
    <span
      role="img"
      aria-label={
        label ??
        `${daysLeft} ${daysLeft === 1 ? "day" : "days"} left, ${stateLabels[state]}`
      }
      className={cn("inline-flex size-10 items-center justify-center", className)}
    >
      <svg
        viewBox="0 0 40 40"
        aria-hidden="true"
        className="size-10"
        focusable="false"
      >
        <circle
          cx="20"
          cy="20"
          r={RADIUS}
          fill="none"
          strokeWidth="3"
          className="stroke-ink-100"
        />
        <circle
          cx="20"
          cy="20"
          r={RADIUS}
          fill="none"
          strokeWidth="3"
          strokeLinecap="round"
          strokeDasharray={CIRCUMFERENCE}
          strokeDashoffset={offset}
          transform="rotate(-90 20 20)"
          className={ringStyles[state]}
        />
        <text
          x="20"
          y="20"
          textAnchor="middle"
          dominantBaseline="central"
          className="fill-ink text-12 font-semibold tabular-nums"
        >
          {daysLeft}
        </text>
      </svg>
    </span>
  );
}
