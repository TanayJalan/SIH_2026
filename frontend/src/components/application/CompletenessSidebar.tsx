import { CheckCircle2, Circle, FileText } from "lucide-react";

import { ProgressBar, Skeleton } from "@/components/ui";
import {
  stepForChecklistSection,
  type WizardStepId,
} from "@/lib/application";
import type { ApplicationChecklist } from "@/lib/api";
import { cn } from "@/lib/utils";

interface CompletenessSidebarProps {
  checklist: ApplicationChecklist | undefined;
  loading: boolean;
  currentStep: WizardStepId;
  onNavigate: (step: WizardStepId) => void;
}

export default function CompletenessSidebar({
  checklist,
  loading,
  currentStep,
  onNavigate,
}: CompletenessSidebarProps) {
  if (loading || !checklist) {
    return (
      <section
        className="rounded-panel border border-line bg-surface p-5"
        aria-label="Application completeness"
      >
        <Skeleton className="h-4 w-28" />
        <Skeleton className="mt-4 h-9 w-20" />
        <Skeleton className="mt-4 h-2 w-full" />
        <div className="mt-5 space-y-3">
          {[0, 1, 2, 3].map((item) => (
            <Skeleton key={item} className="h-8 w-full" />
          ))}
        </div>
      </section>
    );
  }

  const mandatoryDocs = checklist.documents.filter((document) => document.mandatory);
  const uploadedDocs = mandatoryDocs.filter((document) => document.uploaded).length;
  const progressStatus =
    checklist.percentage === 100 ? "ok" : checklist.percentage >= 60 ? "watch" : "info";

  return (
    <section
      className="rounded-panel border border-line bg-surface p-5"
      aria-label="Application completeness"
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-12 font-semibold uppercase tracking-[0.12em] text-ink-500">
            Completeness
          </p>
          <p className="mt-2 font-serif text-32 font-semibold leading-none text-ink">
            {checklist.percentage}%
          </p>
        </div>
        <span
          className={cn(
            "rounded-pill px-2.5 py-1 text-12 font-medium",
            checklist.can_submit
              ? "bg-ok-soft text-ok-strong"
              : "bg-watch-soft text-watch-strong",
          )}
        >
          {checklist.can_submit ? "Ready" : "Draft"}
        </span>
      </div>

      <p className="mt-2 text-12 text-ink-500">
        {checklist.completed_items} of {checklist.required_items} required items complete
      </p>
      <ProgressBar
        label="Submission readiness"
        value={checklist.percentage}
        status={progressStatus}
        showValue={false}
        className="mt-4"
      />

      <div className="mt-5 space-y-1">
        {checklist.sections.map((section) => {
          const step = stepForChecklistSection(section.key);
          return (
            <button
              key={section.key}
              type="button"
              onClick={() => onNavigate(step)}
              className={cn(
                "flex w-full items-start gap-2.5 rounded-input px-2 py-2 text-left transition-colors hover:bg-paper focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus",
                currentStep === step && "bg-paper",
              )}
            >
              {section.complete ? (
                <CheckCircle2
                  aria-hidden="true"
                  className="mt-0.5 size-4 shrink-0 text-ok"
                />
              ) : (
                <Circle
                  aria-hidden="true"
                  className="mt-0.5 size-4 shrink-0 text-ink-300"
                />
              )}
              <span className="min-w-0">
                <span className="block text-13 font-medium text-ink">
                  {section.label}
                </span>
                {!section.complete ? (
                  <span className="mt-0.5 block text-12 text-ink-500">
                    {section.missing_fields.length} field
                    {section.missing_fields.length === 1 ? "" : "s"} missing
                  </span>
                ) : null}
              </span>
            </button>
          );
        })}
      </div>

      <button
        type="button"
        onClick={() => onNavigate("documents")}
        className={cn(
          "mt-3 flex w-full items-center justify-between gap-3 rounded-input border-t border-line px-2 pt-4 text-left transition-colors hover:bg-paper focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus",
          currentStep === "documents" && "bg-paper",
        )}
      >
        <span className="flex items-center gap-2 text-13 font-medium text-ink">
          <FileText aria-hidden="true" className="size-4 text-ink-500" />
          Documents
        </span>
        <span className="text-12 tabular-nums text-ink-500">
          {uploadedDocs}/{mandatoryDocs.length}
        </span>
      </button>

      <p className="mt-4 border-t border-line pt-4 text-11 leading-4 text-ink-500">
        The percentage counts required form fields and mandatory documents. Optional
        documents do not block submission.
      </p>
    </section>
  );
}
