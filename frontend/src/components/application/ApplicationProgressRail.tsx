import { Check, ChevronRight } from "lucide-react";

import { ProgressBar } from "@/components/ui";
import type { WizardStep, WizardStepId } from "@/lib/application";
import { cn } from "@/lib/utils";

export type SaveState = "saved" | "pending" | "saving" | "error";

const timeFormatter = new Intl.DateTimeFormat("en-IN", {
  hour: "2-digit",
  minute: "2-digit",
});

function savedLabel(lastSavedAt: Date | null): string {
  if (!lastSavedAt) {
    return "Saved";
  }
  return `Saved ${timeFormatter.format(lastSavedAt)}`;
}

export function SaveStatus({
  state,
  error,
  lastSavedAt,
}: {
  state: SaveState;
  error: string | null;
  lastSavedAt: Date | null;
}) {
  if (state === "saving") {
    return (
      <span className="flex items-center gap-1.5 text-12 text-ink-500">
        <span
          aria-hidden="true"
          className="size-3.5 animate-spin rounded-full border-2 border-line border-t-info"
        />
        Saving…
      </span>
    );
  }
  if (state === "pending") {
    return <span className="text-12 text-ink-500">Unsaved changes</span>;
  }
  if (state === "error") {
    return (
      <span
        className="flex min-w-0 items-start gap-1.5 text-12 text-breach-strong"
        title={error ?? "Draft could not be saved"}
      >
        <span aria-hidden="true" className="mt-0.5 size-2 shrink-0 rounded-full bg-breach" />
        <span className="min-w-0">Save failed</span>
      </span>
    );
  }
  return (
    <span className="flex items-center gap-1.5 text-12 text-ink-500">
      <Check aria-hidden="true" className="size-3.5 text-ok-strong" />
      {savedLabel(lastSavedAt)}
    </span>
  );
}

interface ApplicationProgressRailProps {
  steps: WizardStep[];
  currentIndex: number;
  completion: Record<WizardStepId, boolean>;
  percentage: number;
  completedItems: number;
  requiredItems: number;
  saveState: SaveState;
  saveError: string | null;
  lastSavedAt: Date | null;
  onNavigate: (step: WizardStepId) => void;
}

export default function ApplicationProgressRail({
  steps,
  currentIndex,
  completion,
  percentage,
  completedItems,
  requiredItems,
  saveState,
  saveError,
  lastSavedAt,
  onNavigate,
}: ApplicationProgressRailProps) {
  return (
    <section
      aria-label="Application progress"
      className="rounded-panel border border-line bg-surface p-4"
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-12 font-semibold uppercase tracking-[0.12em] text-ink-500">
            Application
          </p>
          <p className="mt-1 text-14 font-semibold text-ink">Progress</p>
        </div>
        <span className="text-18 font-serif font-semibold tabular-nums text-ink">
          {percentage}%
        </span>
      </div>
      <ProgressBar
        label="Application completeness"
        value={percentage}
        status={percentage === 100 ? "ok" : "info"}
        showValue={false}
        className="mt-3"
      />
      <p className="mt-2 text-11 text-ink-500">
        {completedItems} of {requiredItems} required items complete
      </p>

      <div className="mt-4 border-t border-line pt-3">
        <SaveStatus state={saveState} error={saveError} lastSavedAt={lastSavedAt} />
      </div>

      <ol className="mt-4 space-y-0.5" aria-label="Application sections">
        {steps.map((step, index) => {
          const complete = completion[step.id];
          const current = index === currentIndex;
          return (
            <li key={step.id}>
              <button
                type="button"
                aria-current={current ? "step" : undefined}
                onClick={() => onNavigate(step.id)}
                className={cn(
                  "group flex w-full items-center gap-2.5 rounded-input px-2 py-2 text-left transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus",
                  current
                    ? "bg-paper text-ink"
                    : "text-ink-700 hover:bg-paper hover:text-ink",
                )}
              >
                <span
                  className={cn(
                    "flex size-6 shrink-0 items-center justify-center rounded-full border text-11 font-semibold tabular-nums",
                    complete
                      ? "border-ok bg-ok-soft text-ok-strong"
                      : current
                        ? "border-ink bg-ink text-surface"
                        : "border-line bg-surface text-ink-500",
                  )}
                >
                  {complete ? (
                    <Check aria-hidden="true" className="size-3.5" />
                  ) : (
                    index + 1
                  )}
                </span>
                <span className="min-w-0 flex-1 truncate text-12 font-medium">
                  {step.label}
                </span>
                <ChevronRight
                  aria-hidden="true"
                  className={cn(
                    "size-3.5 shrink-0 transition-opacity",
                    current ? "text-ink-300" : "text-transparent group-hover:text-ink-300",
                  )}
                />
              </button>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
