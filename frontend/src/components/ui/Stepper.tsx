import { Check } from "lucide-react";

import { cn } from "@/lib/utils";

export interface StepperStep {
  id: string;
  label: string;
  description?: string;
}

export interface StepperProps {
  steps: StepperStep[];
  /** Zero-based index of the current step. */
  current: number;
  label?: string;
  className?: string;
}

export function Stepper({
  steps,
  current,
  label = "Progress",
  className,
}: StepperProps) {
  return (
    <ol
      aria-label={label}
      className={cn(
        "flex flex-col md:flex-row md:items-start",
        className,
      )}
    >
      {steps.map((step, index) => {
        const completed = index < current;
        const isCurrent = index === current;
        const state = completed
          ? "completed"
          : isCurrent
            ? "current"
            : "future";

        return (
          <li
            key={step.id}
            aria-current={isCurrent ? "step" : undefined}
            className="relative flex flex-1 gap-3 pb-6 last:pb-0 md:flex-col md:items-center md:gap-0 md:pb-0 md:text-center"
          >
            {index < steps.length - 1 ? (
              <span
                aria-hidden="true"
                className={cn(
                  "absolute left-4 top-8 h-[calc(100%-2rem)] w-px md:left-1/2 md:top-4 md:h-px md:w-full",
                  completed ? "bg-ink-300" : "bg-line",
                )}
              />
            ) : null}
            <span
              className={cn(
                "relative z-10 flex size-8 shrink-0 items-center justify-center rounded-input border text-13 font-semibold",
                completed && "border-ink bg-ink text-surface",
                isCurrent && "border-info bg-info-soft text-info-strong",
                !completed && !isCurrent && "border-line bg-surface text-ink-500",
              )}
            >
              {completed ? (
                <>
                  <Check aria-hidden="true" className="size-4" />
                  <span className="sr-only">Completed</span>
                </>
              ) : (
                index + 1
              )}
            </span>
            <span className="pt-0.5 md:pt-3">
              <span
                className={cn(
                  "block text-13 font-medium",
                  state === "future" ? "text-ink-500" : "text-ink",
                )}
              >
                {step.label}
              </span>
              {step.description ? (
                <span className="mt-0.5 block text-12 text-ink-500">
                  {step.description}
                </span>
              ) : null}
            </span>
          </li>
        );
      })}
    </ol>
  );
}
