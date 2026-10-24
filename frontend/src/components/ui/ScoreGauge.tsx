import { cn } from "@/lib/utils";

export type ScoreBand = "compliant" | "watch" | "breach";

const bandLabels: Record<ScoreBand, string> = {
  compliant: "compliant",
  watch: "watch",
  breach: "breach",
};

const bandStrokes: Record<ScoreBand, string> = {
  compliant: "stroke-ok",
  watch: "stroke-watch",
  breach: "stroke-breach",
};

const arcPath = "M 20 96 A 80 80 0 0 1 180 96";

const bandMarks = [
  { from: 0, to: 60, className: "stroke-breach-band" },
  { from: 60, to: 80, className: "stroke-watch-band" },
  { from: 80, to: 100, className: "stroke-ok-band" },
];

export interface ScoreGaugeProps {
  value: number;
  band: ScoreBand;
  caption?: string;
  className?: string;
}

export function ScoreGauge({
  value,
  band,
  caption = "Compliance score",
  className,
}: ScoreGaugeProps) {
  const score = Math.max(0, Math.min(100, Math.round(value)));

  return (
    <div
      role="img"
      aria-label={`${caption}: ${score} out of 100, ${bandLabels[band]}`}
      className={cn("w-full max-w-[280px]", className)}
    >
      <svg
        viewBox="0 0 200 112"
        aria-hidden="true"
        focusable="false"
        className="h-auto w-full"
      >
        {bandMarks.map((mark) => (
          <path
            key={mark.from}
            d={arcPath}
            pathLength={100}
            fill="none"
            strokeWidth="12"
            strokeDasharray={`${mark.to - mark.from} 100`}
            strokeDashoffset={-mark.from}
            className={mark.className}
          />
        ))}
        <path
          d={arcPath}
          pathLength={100}
          fill="none"
          strokeWidth="12"
          strokeLinecap="round"
          strokeDasharray={`${score} 100`}
          className={bandStrokes[band]}
        />
        <text
          x="100"
          y="72"
          textAnchor="middle"
          className="fill-ink font-serif text-28 font-semibold tabular-nums"
        >
          {score}
        </text>
        <text
          x="100"
          y="92"
          textAnchor="middle"
          className="fill-ink-500 text-12"
        >
          {caption}
        </text>
      </svg>
    </div>
  );
}
