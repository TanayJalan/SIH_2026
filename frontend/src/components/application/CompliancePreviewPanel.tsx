import {
  CheckCircle2,
  CircleHelp,
  Loader2,
  RefreshCw,
  ShieldCheck,
  TriangleAlert,
  XCircle,
} from "lucide-react";

import { ProgressBar, Skeleton } from "@/components/ui";
import type {
  CompliancePreview,
  ComplianceRuleStatus,
  Severity,
} from "@/lib/api";
import { cn } from "@/lib/utils";

const STATUS_META: Record<
  ComplianceRuleStatus,
  { label: string; className: string; Icon: typeof CheckCircle2 }
> = {
  PASS: {
    label: "Pass",
    className: "text-ok-strong",
    Icon: CheckCircle2,
  },
  FAIL: {
    label: "Fail",
    className: "text-breach-strong",
    Icon: XCircle,
  },
  NOT_ASSESSED: {
    label: "Awaiting",
    className: "text-ink-500",
    Icon: CircleHelp,
  },
};

const SEVERITY_STYLES: Record<Severity, string> = {
  CRITICAL: "bg-breach-soft text-breach-strong",
  HIGH: "bg-watch-soft text-watch-strong",
  MEDIUM: "bg-info-soft text-info-strong",
  LOW: "bg-paper text-ink-500",
};

const OUTCOME_META = {
  PASS: {
    label: "On track",
    description: "Every assessed rule currently passes.",
    className: "border-ok bg-ok-soft text-ok-strong",
  },
  ATTENTION: {
    label: "Needs attention",
    description: "One or more assessed rules currently fail.",
    className: "border-watch bg-watch-soft text-watch-strong",
  },
  INCOMPLETE: {
    label: "Awaiting data",
    description: "Complete more fields to assess every rule.",
    className: "border-line bg-paper text-ink-700",
  },
} as const;

interface CompliancePreviewPanelProps {
  preview: CompliancePreview | undefined;
  loading: boolean;
  fetching: boolean;
  error: boolean;
  onRetry: () => void;
}

function formatCount(count: number, label: string): string {
  return `${count} ${label}`;
}

export default function CompliancePreviewPanel({
  preview,
  loading,
  fetching,
  error,
  onRetry,
}: CompliancePreviewPanelProps) {
  if (loading && !preview) {
    return (
      <section
        aria-label="Live compliance preview"
        className="rounded-panel border border-line bg-surface p-5"
      >
        <div className="flex items-center gap-2">
          <ShieldCheck aria-hidden="true" className="size-4 text-ink-500" />
          <p className="text-13 font-semibold text-ink">Live compliance preview</p>
        </div>
        <Skeleton className="mt-4 h-3 w-28" />
        <Skeleton className="mt-3 h-8 w-20" />
        <Skeleton className="mt-4 h-2 w-full" />
        <div className="mt-5 space-y-4">
          {[0, 1, 2, 3].map((item) => (
            <div key={item}>
              <Skeleton className="h-3 w-2/3" />
              <Skeleton className="mt-2 h-3 w-full" />
            </div>
          ))}
        </div>
      </section>
    );
  }

  if (error && !preview) {
    return (
      <section
        aria-label="Live compliance preview"
        className="rounded-panel border border-line bg-surface p-5"
      >
        <div className="flex items-center gap-2">
          <ShieldCheck aria-hidden="true" className="size-4 text-ink-500" />
          <p className="text-13 font-semibold text-ink">Live compliance preview</p>
        </div>
        <p className="mt-4 text-12 leading-5 text-ink-700">
          The preview could not be evaluated for the current values. Correct any highlighted
          field and it will update automatically.
        </p>
        <button
          type="button"
          onClick={onRetry}
          className="mt-3 inline-flex items-center gap-1.5 text-12 font-medium text-ink-700 underline-offset-4 hover:text-ink hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
        >
          <RefreshCw aria-hidden="true" className="size-3.5" />
          Try again
        </button>
      </section>
    );
  }

  if (!preview || preview.rules.length === 0) {
    return (
      <section
        aria-label="Live compliance preview"
        className="rounded-panel border border-line bg-surface p-5"
      >
        <div className="flex items-center gap-2">
          <ShieldCheck aria-hidden="true" className="size-4 text-ink-500" />
          <p className="text-13 font-semibold text-ink">Live compliance preview</p>
        </div>
        <p className="mt-3 text-12 leading-5 text-ink-700">
          No active compliance rules are configured. Add rules in the database to preview
          outcomes while completing the draft.
        </p>
      </section>
    );
  }

  const outcome = OUTCOME_META[preview.outcome];
  const progressStatus =
    preview.outcome === "PASS" ? "ok" : preview.outcome === "ATTENTION" ? "breach" : "watch";

  return (
    <section
      aria-label="Live compliance preview"
      className="rounded-panel border border-line bg-surface p-5"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <ShieldCheck aria-hidden="true" className="size-4 text-ink-500" />
          <p className="text-13 font-semibold text-ink">Live compliance preview</p>
        </div>
        {fetching ? (
          <Loader2
            aria-label="Refreshing compliance preview"
            className="size-3.5 animate-spin text-ink-500"
          />
        ) : null}
      </div>

      {error ? (
        <p className="mt-3 rounded-input border border-watch bg-watch-soft p-2.5 text-11 leading-4 text-watch-strong">
          Preview paused for values the API cannot evaluate. Correct any highlighted field and
          the preview will resume automatically.
        </p>
      ) : null}

      <div
        aria-live="polite"
        className={cn(
          "mt-3 flex items-center justify-between gap-2 rounded-input border px-3 py-2",
          outcome.className,
        )}
      >
        <div>
          <p className="text-12 font-semibold">{outcome.label}</p>
          <p className="mt-0.5 text-11 opacity-90">{outcome.description}</p>
        </div>
        <span className="text-20 font-serif font-semibold tabular-nums">{preview.score}%</span>
      </div>

      <div
        className={cn(
          "mt-2 rounded-input border px-3 py-2 text-11 leading-4",
          preview.nil_deficiency
            ? "border-ok bg-ok-soft text-ok-strong"
            : "border-watch bg-watch-soft text-watch-strong",
        )}
      >
        <p className="font-semibold">{preview.banner}</p>
        <p className="mt-0.5">
          {preview.mandatory_failed_count} mandatory failure(s) ·{" "}
          {preview.mandatory_missing_count} mandatory unassessed
        </p>
      </div>

      <ProgressBar
        label="Assessed rules passing"
        value={preview.score}
        status={progressStatus}
        showValue={false}
        className="mt-3"
      />
      <p className="mt-2 text-11 leading-4 text-ink-500">
        {formatCount(preview.passed_count, "passing")} ·{" "}
        {formatCount(preview.failed_count, "failing")} ·{" "}
        {formatCount(preview.not_assessed_count, "awaiting data")}
      </p>

      <ul className="mt-4 divide-y divide-line border-t border-line">
        {preview.rules.map((rule) => {
          const status = STATUS_META[rule.status];
          const StatusIcon = status.Icon;
          return (
            <li key={rule.code} className="py-3">
              <div className="flex items-start gap-2">
                <StatusIcon
                  aria-hidden="true"
                  className={cn("mt-0.5 size-3.5 shrink-0", status.className)}
                />
                <div className="min-w-0 flex-1">
                  <div className="flex items-start justify-between gap-2">
                    <p className="text-12 font-medium leading-4 text-ink">{rule.name}</p>
                    <span
                      className={cn(
                        "shrink-0 rounded-pill px-1.5 py-0.5 text-10 font-semibold uppercase tracking-wide",
                        SEVERITY_STYLES[rule.severity],
                      )}
                    >
                      {rule.severity}
                    </span>
                  </div>
                  <p className="mt-1 text-11 leading-4 text-ink-500">{rule.message}</p>
                  <div className="mt-1 flex flex-wrap items-center gap-1.5 text-10">
                    <span className="rounded-pill border border-line bg-paper px-1.5 py-0.5 text-ink-700">
                      {rule.apH_clause}
                    </span>
                    {rule.illustrative ? (
                      <span className="rounded-pill bg-watch-soft px-1.5 py-0.5 text-watch-strong">
                        Illustrative, not an AICTE norm
                      </span>
                    ) : null}
                    {rule.needs_verification ? (
                      <span className="rounded-pill bg-paper px-1.5 py-0.5 text-ink-500">
                        Needs verification
                      </span>
                    ) : null}
                    {rule.penal_action_suggestions.length > 0 ? (
                      <span className="rounded-pill bg-paper px-1.5 py-0.5 text-ink-500">
                        {rule.penal_action_suggestions.length} suggested APH 7.3 action
                        {rule.penal_action_suggestions.length === 1 ? "" : "s"}
                      </span>
                    ) : null}
                  </div>
                  <p className={cn("mt-1 text-11 font-medium", status.className)}>
                    {status.label}
                  </p>
                </div>
              </div>
            </li>
          );
        })}
      </ul>

      <p className="mt-4 border-t border-line pt-3 text-10 leading-4 text-ink-500">
        Each rule carries the APH clause it implements. Thresholds are editable configuration;
        rows marked illustrative are project-only demo values, not AICTE norms. Verify every
        figure against the current AICTE Approval Process Handbook.
      </p>
      {preview.failed_count > 0 ? (
        <p className="mt-2 flex items-start gap-1.5 text-11 leading-4 text-watch-strong">
          <TriangleAlert aria-hidden="true" className="mt-0.5 size-3.5 shrink-0" />
          Compliance findings are advisory at this stage; resolve blocking items before
          submitting.
        </p>
      ) : null}
    </section>
  );
}
