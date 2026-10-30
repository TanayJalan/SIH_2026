import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Scale } from "lucide-react";

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
  if (rule.operator === "EXISTS") {
    return "must be present";
  }
  if (rule.operator === "DATE_NOT_EXPIRED") {
    return "must be valid on the evaluation date";
  }
  if (rule.operator === "BETWEEN") {
    return `between ${rule.threshold.toLocaleString("en-IN")} and ${(
      rule.threshold_max ?? rule.threshold
    ).toLocaleString("en-IN")}${rule.unit ? ` ${rule.unit}` : ""}`;
  }
  if (rule.operator === "RATIO" || rule.operator === "SUM" || rule.operator === "COUNT") {
    const comparison =
      typeof rule.explanation?.comparison === "string"
        ? rule.explanation.comparison
        : ">=";
    const phrases: Record<string, string> = {
      "<": "below",
      "<=": "at most",
      "=": "equal to",
      ">=": "at least",
      ">": "above",
      "!=": "different from",
    };
    return `${phrases[comparison] ?? comparison} ${rule.threshold.toLocaleString("en-IN")}${
      rule.unit ? ` ${rule.unit}` : ""
    }`;
  }
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

function PenalActions({ rule }: { rule: ComplianceRulePreview }) {
  if (rule.penal_action_suggestions.length === 0) {
    return null;
  }
  return (
    <div className="mt-2 rounded-input border border-line bg-paper p-2.5">
      <p className="flex items-center gap-1.5 text-12 font-medium text-ink">
        <Scale aria-hidden="true" className="size-3.5 text-ink-500" />
        Suggestion · penal action under APH 7.3
      </p>
      <ul className="mt-1 space-y-1 text-12 leading-5 text-ink-700">
        {rule.penal_action_suggestions.map((suggestion) => (
          <li key={`${rule.code}-${suggestion.violation_code}`}>
            {suggestion.action_label} · {suggestion.violation_code} ({suggestion.apH_clause})
          </li>
        ))}
      </ul>
      <p className="mt-1 text-12 text-ink-500">
        A show-cause notice, hearing and speaking order are mandatory before any action is
        imposed.
      </p>
    </div>
  );
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
        Number(b.mandatory) - Number(a.mandatory) ||
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
            Each rule cites the APH clause it implements. Thresholds are editable
            configuration; illustrative rows are project-only demo values.
          </p>
        </div>
        <ScoreGauge
          value={preview.score}
          band={band}
          className="shrink-0"
        />
      </div>

      <div
        className={`mt-3 rounded-input border px-3 py-2 text-12 leading-5 ${
          preview.nil_deficiency
            ? "border-ok bg-ok-soft text-ok-strong"
            : "border-watch bg-watch-soft text-watch-strong"
        }`}
      >
        <p className="font-semibold">{preview.banner}</p>
        <p className="mt-0.5">
          {preview.mandatory_failed_count} mandatory failure(s) ·{" "}
          {preview.mandatory_missing_count} mandatory unassessed
        </p>
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
          Every mandatory requirement is assessed and met.
        </p>
      ) : ordered.length === 0 ? null : (
        <div className="mt-4 overflow-x-auto rounded-panel border border-line">
          <table className="w-full min-w-[840px] text-left text-13">
            <caption className="sr-only">Rule-by-rule compliance results</caption>
            <thead>
              <tr className="border-b border-line bg-paper">
                <th scope="col" className="px-4 py-2.5 font-semibold text-ink-700">Rule</th>
                <th scope="col" className="px-4 py-2.5 font-semibold text-ink-700">Clause</th>
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
                    <div className="mt-1 flex flex-wrap items-center gap-1.5">
                      {!rule.mandatory ? (
                        <span className="rounded-pill bg-neutral-soft px-2 py-0.5 text-11 text-ink-700">
                          Advisory
                        </span>
                      ) : null}
                      {rule.illustrative ? (
                        <span className="rounded-pill bg-watch-soft px-2 py-0.5 text-11 text-watch-strong">
                          Illustrative, not an AICTE norm
                        </span>
                      ) : null}
                      {rule.needs_verification ? (
                        <span className="rounded-pill bg-watch-soft px-2 py-0.5 text-11 text-watch-strong">
                          Needs verification
                        </span>
                      ) : null}
                    </div>
                    {rule.status === "FAIL" ? <PenalActions rule={rule} /> : null}
                  </td>
                  <td className="px-4 py-3 align-top text-12 text-ink-700">{rule.apH_clause}</td>
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

      <p className="mt-4 border-t border-line pt-3 text-11 leading-5 text-ink-500">
        A Nil Deficiency result requires every mandatory rule to pass or be assessed. Rows marked
        illustrative are project-only demo thresholds, not AICTE norms. Verify every figure against
        the current AICTE Approval Process Handbook before relying on it.
      </p>
    </section>
  );
}
