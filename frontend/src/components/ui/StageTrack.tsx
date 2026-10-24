import { AlertTriangle, Check } from "lucide-react";

import { cn } from "@/lib/utils";

export interface StageTrackStage {
  id: string;
  label: string;
}

export interface StageTrackEvent {
  stage: string;
  at?: string;
  blocked?: boolean;
}

export interface StageTrackProps {
  stages: StageTrackStage[];
  current: string;
  events?: StageTrackEvent[];
  label?: string;
  className?: string;
}

type StageState = "completed" | "current" | "blocked" | "future";

export function StageTrack({
  stages,
  current,
  events = [],
  label = "Application stages",
  className,
}: StageTrackProps) {
  const eventByStage = new Map(events.map((event) => [event.stage, event]));

  return (
    <ol
      aria-label={label}
      className={cn(
        "flex flex-col md:flex-row md:items-start",
        className,
      )}
    >
      {stages.map((stage, index) => {
        const event = eventByStage.get(stage.id);
        const state: StageState = event?.blocked
          ? "blocked"
          : stage.id === current
            ? "current"
            : event?.at
              ? "completed"
              : "future";
        const meta =
          state === "completed"
            ? (event?.at ?? "Completed")
            : state === "blocked"
              ? event?.at
                ? `Deficiency raised · ${event.at}`
                : "Deficiency raised"
              : state === "current"
                ? (event?.at ?? "In progress")
                : null;

        return (
          <li
            key={stage.id}
            aria-current={stage.id === current ? "step" : undefined}
            className="relative flex flex-1 gap-3 pb-6 last:pb-0 md:flex-col md:items-center md:gap-0 md:pb-0 md:text-center"
          >
            {index < stages.length - 1 ? (
              <span
                aria-hidden="true"
                className={cn(
                  "absolute left-4 top-8 h-[calc(100%-1rem)] w-px transition-colors duration-300 md:left-1/2 md:top-4 md:h-px md:w-full",
                  state === "completed" ? "bg-ink-300" : "bg-line",
                )}
              />
            ) : null}
            <span className="relative z-10 flex size-8 shrink-0 items-center justify-center">
              {state === "current" ? (
                <span
                  aria-hidden="true"
                  className="absolute -inset-1 rounded-input border border-info motion-safe:animate-pulse"
                />
              ) : null}
              <span
                className={cn(
                  "flex size-8 items-center justify-center rounded-input border text-13 font-semibold transition-colors duration-300",
                  state === "completed" && "border-ink bg-ink text-surface",
                  state === "current" &&
                    "border-info bg-info-soft text-info-strong",
                  state === "blocked" &&
                    "border-breach bg-breach-soft text-breach-strong",
                  state === "future" &&
                    "border-line bg-surface text-ink-500",
                )}
              >
                {state === "completed" ? (
                  <>
                    <Check aria-hidden="true" className="size-4" />
                    <span className="sr-only">Completed</span>
                  </>
                ) : state === "blocked" ? (
                  <>
                    <AlertTriangle aria-hidden="true" className="size-4" />
                    <span className="sr-only">Blocked</span>
                  </>
                ) : (
                  index + 1
                )}
              </span>
            </span>
            <span className="pt-0.5 md:pt-3">
              <span
                className={cn(
                  "block text-13 font-medium transition-colors duration-300",
                  state === "future" && "text-ink-500",
                  state === "blocked" && "text-breach-strong",
                  (state === "completed" || state === "current") && "text-ink",
                )}
              >
                {stage.label}
              </span>
              {meta ? (
                <span
                  className={cn(
                    "mt-0.5 block text-12 transition-colors duration-300",
                    state === "blocked"
                      ? "text-breach-strong"
                      : state === "current"
                        ? "text-info-strong"
                        : "text-ink-500",
                  )}
                >
                  {meta}
                </span>
              ) : null}
            </span>
          </li>
        );
      })}
    </ol>
  );
}
