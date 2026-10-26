import type { ApplicationStatus, WorkflowStage } from "@/lib/api";
import { cn } from "@/lib/utils";

const STAGES: { key: WorkflowStage; label: string }[] = [
  { key: "APPLICATION", label: "Application" },
  { key: "DOCUMENT_VERIFICATION", label: "Documents" },
  { key: "SCRUTINY", label: "Scrutiny" },
  { key: "INSPECTION", label: "Inspection" },
  { key: "COMMITTEE_REVIEW", label: "Committee" },
  { key: "DECISION", label: "Decision" },
];

const STAGE_INDEX: Record<WorkflowStage, number> = {
  APPLICATION: 0,
  DOCUMENT_VERIFICATION: 1,
  SCRUTINY: 2,
  DEFICIENCY: 2,
  INSPECTION: 3,
  COMMITTEE_REVIEW: 4,
  DECISION: 5,
  COMPLETED: 5,
};

const CLOSED_STATUSES: ApplicationStatus[] = [
  "APPROVED",
  "CONDITIONALLY_APPROVED",
  "REJECTED",
];

interface ApplicationStatusTrackerProps {
  status: ApplicationStatus;
  currentStage: WorkflowStage;
  portalApplicationNo: string | null;
  className?: string;
}

export default function ApplicationStatusTracker({
  status,
  currentStage,
  portalApplicationNo,
  className,
}: ApplicationStatusTrackerProps) {
  const currentIndex = STAGE_INDEX[currentStage] ?? 0;
  const isClosed = CLOSED_STATUSES.includes(status);
  const displayIndex = isClosed ? STAGES.length : currentIndex;

  return (
    <div className={cn("space-y-2", className)}>
      <p className="text-12 text-ink-500">
        Portal application number:{" "}
        <span className="font-medium text-ink-700">
          {portalApplicationNo ?? "Issued after final submission"}
        </span>
      </p>
      <ol className="flex items-center gap-1" aria-label="Application status tracker">
        {STAGES.map((stage, index) => {
          const complete = index < displayIndex;
          const current = !isClosed && index === currentIndex;
          return (
            <li key={stage.key} className="flex min-w-0 flex-1 items-center gap-1">
              <span
                aria-hidden="true"
                className={cn(
                  "size-2 shrink-0 rounded-full",
                  complete
                    ? "bg-ok"
                    : current
                      ? "bg-info ring-2 ring-info-soft"
                      : "bg-line",
                )}
              />
              {index < STAGES.length - 1 ? (
                <span
                  aria-hidden="true"
                  className={cn(
                    "h-px min-w-2 flex-1",
                    complete ? "bg-ok/60" : "bg-line",
                  )}
                />
              ) : null}
            </li>
          );
        })}
      </ol>
      <div className="flex justify-between text-12 uppercase tracking-[0.08em] text-ink-500">
        {STAGES.map((stage, index) => (
          <span
            key={stage.key}
            className={cn(
              "truncate",
              !isClosed && index === currentIndex && "font-semibold text-ink-700",
              index < displayIndex && "text-ok-strong",
            )}
          >
            {stage.label}
          </span>
        ))}
      </div>
    </div>
  );
}
