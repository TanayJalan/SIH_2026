import { useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { Button, ScoreGauge, Skeleton, StatusPill, type ScoreBand } from "../ui";
import { useWorkflowActions, type WorkflowPrefill } from "../workflow/WorkflowDialogHost";
import {
  ApiError,
  getApplicationCompliance,
  type ComplianceRulePreview,
} from "@/lib/api";

const RESULT_TONES: Record<string, "compliant" | "breach" | "neutral"> = {
  PASS: "compliant",
  FAIL: "breach",
  NOT_ASSESSED: "neutral",
};

const SEVERITY_ORDER: Record<string, number> = {
  CRITICAL: 0,
  HIGH: 1,
  MEDIUM: 2,
  LOW: 3,
};

function categoryForRule(rule: ComplianceRulePreview): WorkflowPrefill["category"] {
  const category = rule.category.toLowerCase();
  if (category.includes("faculty")) {
    return "FACULTY";
  }
  if (category.includes("finance")) {
    return "FINANCE";
  }
  if (category.includes("infrastructure")) {
    return "INFRASTRUCTURE";
  }
  if (category.includes("document")) {
    return "DOCUMENT";
  }
  return "OTHER";
}

function requirement(rule: ComplianceRulePreview): string {
  const phrases: Record<string, string> = {
    "<": "below",
    "<=": "at most",
    "=": "equal to",
    ">=": "at least",
    ">": "above",
    "!=": "different from",
  };
  const phrase = phrases[rule.operator] ?? rule.operator;
  return `${phrase} ${rule.threshold.toLocaleString("en-IN")}${rule.unit ? ` ${rule.unit}` : ""}`;
}

function observed(rule: ComplianceRulePreview): string {
  if (rule.observed_value === null) {
    return "—";
  }
  return `${rule.observed_value.toLocaleString("en-IN")}${rule.unit ? ` ${rule.unit}` : ""}`;
}

export default function CaseCompliance({
  applicationId,
  token,
  canRaiseDeficiency,
}: {
  applicationId: string;
  token: string;
  canRaiseDeficiency: boolean;
}) {
  const [showPassed, setShowPassed] = useState(false);
  const { findAction, openAction } = useWorkflowActions();

  const complianceQuery = useQuery({
    queryKey: ["compliance-preview", applicationId],
    queryFn: () => getApplicationCompliance(token, applicationId),
    enabled: Boolean(token && applicationId),
    retry: false,
  });

  if (complianceQuery.isPending) {
    return (
      <section className="rounded-panel border border-line bg-surface p-5 sm:p-6" role="status">
        <div className="flex items-center justify-between gap-4">
          <div className="min-w-0 flex-1 space-y-2">
            <Skeleton className="h-6 w-48" />
            <Skeleton className="h-4 w-96 max-w-full" />
          </div>
          <Skeleton className="h-24 w-32" />
        </div>
        <div className="mt-6 space-y-3">
          {[0, 1, 2].map((item) => (
            <Skeleton key={item} className="h-10 w-full" />
          ))}
        </div>
        <span className="sr-only">Loading compliance evaluation</span>
      </section>
    );
  }

  if (complianceQuery.isError || !complianceQuery.data) {
    return (
      <section className="rounded-panel border border-line bg-surface p-5 sm:p-6">
        <h2 className="font-serif text-20 font-semibold text-ink">Compliance</h2>
        <p className="mt-4 rounded-input border border-breach bg-breach-soft p-3 text-13 text-breach-strong">
          {complianceQuery.error instanceof ApiError
            ? complianceQuery.error.message
            : "The compliance evaluation could not be loaded."}
        </p>
      </section>
    );
  }

  const preview = complianceQuery.data;
  const band: ScoreBand = preview.outcome === "PASS" ? "compliant" : "watch";
  const failed = preview.rules.filter((rule) => rule.status === "FAIL");
  const notAssessed = preview.rules.filter((rule) => rule.status === "NOT_ASSESSED");
  const passed = preview.rules.filter((rule) => rule.status === "PASS");
  const ordered = failed
    .slice()
    .sort(
      (a, b) =>
        SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity] ||
        a.category.localeCompare(b.category),
    )
    .concat(notAssessed, showPassed ? passed : []);
  const raiseAction = findAction("communicate_deficiency");

  return (
    <section className="rounded-panel border border-line bg-surface p-5 sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <h2 className="font-serif text-20 font-semibold text-ink">Compliance</h2>
          <p className="mt-1 text-13 text-ink-500">
            Configured AICTE norms evaluated against the submitted case data.
            Thresholds are illustrative and editable by administrators.
          </p>
        </div>
        <ScoreGauge
          value={preview.score}
          band={band}
          className="shrink-0"
        />
      </div>

      <p className="mt-3 flex flex-wrap items-center gap-2 text-12 text-ink-500">
        <StatusPill status={RESULT_TONES.PASS}>{preview.passed_count} passed</StatusPill>
        <StatusPill status={RESULT_TONES.FAIL}>{failed.length} failed</StatusPill>
        {notAssessed.length > 0 ? (
          <StatusPill status={RESULT_TONES.NOT_ASSESSED}>
            {notAssessed.length} not assessed
          </StatusPill>
        ) : null}
        <span>Evaluated {new Date(preview.evaluated_at).toLocaleString("en-IN")}</span>
      </p>

      {failed.length === 0 && notAssessed.length === 0 ? (
        <p className="mt-4 rounded-input border border-line bg-paper p-4 text-13 text-ink-700">
          Every configured norm is currently met.
        </p>
      ) : ordered.length === 0 ? null : (
        <div className="mt-4 overflow-x-auto rounded-panel border border-line">
          <table className="w-full min-w-[720px] text-left text-13">
            <caption className="sr-only">Rule-by-rule compliance results</caption>
            <thead>
              <tr className="border-b border-line bg-paper">
                <th scope="col" className="px-4 py-2.5 font-semibold text-ink-700">Rule</th>
                <th scope="col" className="px-4 py-2.5 font-semibold text-ink-700">Required</th>
                <th scope="col" className="px-4 py-2.5 font-semibold text-ink-700">Observed</th>
                <th scope="col" className="px-4 py-2.5 font-semibold text-ink-700">Severity</th>
                <th scope="col" className="px-4 py-2.5 font-semibold text-ink-700">Result</th>
                <th scope="col" className="px-4 py-2.5 text-right font-semibold text-ink-700">
                  <span className="sr-only">Actions</span>
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line bg-surface">
              {ordered.map((rule) => (
                <tr key={rule.code} className={rule.status === "FAIL" ? "bg-breach-soft/40" : undefined}>
                  <td className="px-4 py-3 align-top">
                    <p className="font-medium text-ink">{rule.name}</p>
                    <p className="mt-0.5 text-12 leading-5 text-ink-500">{rule.message}</p>
                  </td>
                  <td className="px-4 py-3 align-top text-ink-700">{requirement(rule)}</td>
                  <td className="px-4 py-3 align-top tabular-nums text-ink-700">{observed(rule)}</td>
                  <td className="px-4 py-3 align-top">
                    <StatusPill status={rule.severity === "LOW" ? "watch" : "breach"}>
                      {rule.severity}
                    </StatusPill>
                  </td>
                  <td className="px-4 py-3 align-top">
                    <StatusPill status={RESULT_TONES[rule.status]}>
                      {rule.status === "NOT_ASSESSED" ? "Not assessed" : rule.status}
                    </StatusPill>
                  </td>
                  <td className="px-4 py-3 text-right align-top">
                    {rule.status === "FAIL" &&
                    canRaiseDeficiency &&
                    raiseAction ? (
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() =>
                          openAction(raiseAction, {
                            category: categoryForRule(rule),
                            description: `${rule.name}: ${rule.message}`,
                          })
                        }
                      >
                        Draft deficiency
                      </Button>
                    ) : null}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {passed.length > 0 ? (
        <div className="mt-3">
          <Button
            variant="quiet"
            size="sm"
            aria-pressed={showPassed}
            onClick={() => setShowPassed((current) => !current)}
          >
            {showPassed ? "Hide passed rules" : `Show passed rules (${passed.length})`}
          </Button>
        </div>
      ) : null}
    </section>
  );
}
