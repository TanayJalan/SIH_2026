import type { ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";

import { Skeleton, StatusPill, type StatusPillTone } from "../ui";
import { useWorkflowActions } from "../workflow/WorkflowDialogHost";
import {
  ApiError,
  getAlerts,
  getApplicationCompliance,
  listApplicationDocuments,
  type AllowedAction,
  type ApplicationDetail,
  type CompliancePreview,
  type WorkflowAction,
} from "@/lib/api";
import { formatDate } from "@/lib/format";

const OWNER_FOR_ACTION: Partial<Record<WorkflowAction, string>> = {
  submit: "Institution admin",
  pay_ter: "Institution admin",
  assign_scrutiny: "Regulation Bureau officer",
  scrutiny_recommend: "Scrutiny Committee",
  communicate_deficiency: "Scrutiny Committee",
  submit_compliance: "Institution admin",
  re_scrutiny_verify: "Scrutiny Committee",
  constitute_evc: "Regional Officer",
  submit_evc_video: "Expert Visit Committee",
  evc_report: "Expert Visit Committee",
  observations: "Regulation Bureau officer",
  list_for_ec: "Regulation Bureau officer",
  ec_decide: "Executive Committee",
  council_ratification: "Council secretariat",
  issue_letter: "Regulation Bureau officer",
  issue_loa: "Regulation Bureau officer",
  issue_eoa: "Regulation Bureau officer",
  issue_lod: "Regulation Bureau officer",
  issue_lor: "Regulation Bureau officer",
  file_appeal: "Institution admin",
  sac_recommend: "Standing Appellate Committee",
  send_back: "Standing Appellate Committee",
  council_final: "Council",
  endorse_decision: "Regional Officer",
  pay_security_deposit: "Institution admin",
  apply_deposit_penalty: "Regulation Bureau officer",
  finalize_no_appeal: "Regulation Bureau officer",
  expire_loa: "System (scheduled job)",
  shc_hearing: "Standing Hearing Committee",
  run_self_disclosure_check: "Regulation Bureau officer",
  reopen_once: "Regulation Bureau officer",
  withdraw_application: "Institution admin",
};

const SEVERITY_WEIGHT: Record<string, number> = {
  CRITICAL: 1,
  HIGH: 0.8,
  MEDIUM: 0.55,
  LOW: 0.3,
};

const SEVERITY_ORDER: Record<string, number> = {
  CRITICAL: 0,
  HIGH: 1,
  MEDIUM: 2,
  LOW: 3,
};

const SEVERITY_PILL_TONE: Record<string, StatusPillTone> = {
  CRITICAL: "breach",
  HIGH: "breach",
  MEDIUM: "watch",
  LOW: "neutral",
};

const SEVERITY_BAR_CLASS: Record<string, string> = {
  CRITICAL: "bg-breach",
  HIGH: "bg-breach",
  MEDIUM: "bg-watch",
  LOW: "bg-watch",
};

interface RiskFactor {
  code: string;
  name: string;
  severity: string;
  relativeImpact: number;
}

interface RiskExplanation {
  messages: string[];
  factors: RiskFactor[];
}

function Panel({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <section className="rounded-panel border border-line bg-surface p-5">
      <h2 className="font-serif text-18 font-semibold text-ink">{title}</h2>
      <div className="mt-3">{children}</div>
    </section>
  );
}

function computeRiskExplanation(
  preview: CompliancePreview | undefined,
): RiskExplanation | null {
  if (!preview) {
    return null;
  }
  const failed = preview.rules
    .filter((rule) => rule.status === "FAIL")
    .sort(
      (a, b) =>
        SEVERITY_ORDER[a.severity] - SEVERITY_ORDER[b.severity] ||
        a.category.localeCompare(b.category),
    );
  const factors: RiskFactor[] = failed
    .map((rule) => {
      const weight = SEVERITY_WEIGHT[rule.severity] ?? 0.3;
      const threshold = Math.abs(rule.threshold) || 1;
      const deviation =
        rule.observed_value === null
          ? 1
          : Math.min(
              1,
              Math.abs(rule.observed_value - rule.threshold) / threshold,
            );
      const magnitude = weight * 0.7 + deviation * 0.3;
      return {
        code: rule.code,
        name: rule.name,
        severity: rule.severity,
        relativeImpact: magnitude,
      };
    })
    .slice(0, 5);
  const maxValue = factors[0]?.relativeImpact || 1;
  return {
    messages: failed.map((rule) => rule.message),
    factors: factors.map((factor) => ({
      ...factor,
      relativeImpact: Math.max(
        12,
        Math.round((factor.relativeImpact / maxValue) * 100),
      ),
    })),
  };
}

function NextStepPanel({
  application,
  actions,
}: {
  application: ApplicationDetail;
  actions: AllowedAction[];
}) {
  if (application.is_withdrawn) {
    return (
      <Panel title="Next step">
        <p className="text-13 leading-5 text-ink-700">
          This application was withdrawn by the institution. The case is closed
          and its workflow history is preserved.
        </p>
      </Panel>
    );
  }
  const primary =
    actions.find((action) => action.tone === "primary") ?? actions[0];
  if (!primary) {
    return (
      <Panel title="Next step">
        <p className="text-13 leading-5 text-ink-700">
          {application.current_stage === "COMPLETED"
            ? "The application has reached its final decision. No further workflow step is pending."
            : "No workflow step is available to your role right now. Another role owns the next action."}
        </p>
      </Panel>
    );
  }
  return (
    <Panel title="Next step">
      <dl className="space-y-3 text-13">
        <div>
          <dt className="text-12 font-medium text-ink-500">What must happen</dt>
          <dd className="mt-0.5 font-medium text-ink">{primary.label}</dd>
        </div>
        <p className="text-12 leading-5 text-ink-700">{primary.description}</p>
        <div className="flex flex-wrap items-center gap-x-6 gap-y-2 border-t border-line pt-3">
          <div>
            <dt className="text-12 font-medium text-ink-500">Owner</dt>
            <dd className="mt-0.5 text-ink">
              {OWNER_FOR_ACTION[primary.action] ?? "Case officer"}
            </dd>
          </div>
          <div>
            <dt className="text-12 font-medium text-ink-500">Due</dt>
            <dd className="mt-0.5 tabular-nums text-ink">
              {application.sla_due_at
                ? formatDate(application.sla_due_at)
                : "No SLA clock running"}
            </dd>
          </div>
        </div>
      </dl>
    </Panel>
  );
}

function RiskExplanationPanel({
  explanation,
  pending,
  errorText,
}: {
  explanation: RiskExplanation | null;
  pending: boolean;
  errorText: string | null;
}) {
  if (pending) {
    return (
      <Panel title="Risk explanation">
        <div className="space-y-2" role="status">
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-3/4" />
          <span className="sr-only">Loading risk explanation</span>
        </div>
      </Panel>
    );
  }
  if (errorText) {
    return (
      <Panel title="Risk explanation">
        <p className="rounded-input border border-breach bg-breach-soft p-3 text-13 text-breach-strong">
          {errorText}
        </p>
      </Panel>
    );
  }
  if (!explanation || explanation.messages.length === 0) {
    return (
      <Panel title="Risk explanation">
        <p className="text-13 leading-5 text-ink-700">
          Every configured compliance norm is currently met, so no rule-based
          risk factors are flagged for this application.
        </p>
      </Panel>
    );
  }
  return (
    <Panel title="Risk explanation">
      <ul className="space-y-2 text-13 leading-5 text-ink-700">
        {explanation.messages.map((message) => (
          <li key={message}>{message}</li>
        ))}
      </ul>
      <p className="mt-4 text-11 font-semibold uppercase tracking-wide text-ink-500">
        Top contributing factors
      </p>
      <ul className="mt-2 space-y-2">
        {explanation.factors.map((factor) => (
          <li key={factor.code}>
            <div className="flex items-center justify-between gap-2">
              <span className="truncate text-12 font-medium text-ink">
                {factor.name}
              </span>
              <StatusPill status={SEVERITY_PILL_TONE[factor.severity]}>
                {factor.severity}
              </StatusPill>
            </div>
            <div
              role="img"
              aria-label={`${factor.name}: ${factor.relativeImpact}% relative impact`}
              className="mt-1 h-1.5 w-full overflow-hidden rounded-pill bg-paper transition-[width] duration-300"
            >
              <div
                className={`h-full rounded-pill ${SEVERITY_BAR_CLASS[factor.severity] ?? "bg-watch"}`}
                style={{ width: `${factor.relativeImpact}%` }}
              />
            </div>
          </li>
        ))}
      </ul>
      <p className="mt-3 text-11 leading-4 text-ink-500">
        Factors are derived from the configured rule engine on the server, not
        from free-form model output.
      </p>
    </Panel>
  );
}

function DocumentWaitingPanel({
  applicationId,
  token,
}: {
  applicationId: string;
  token: string;
}) {
  const documentsQuery = useQuery({
    queryKey: ["document-records", applicationId, "all"],
    queryFn: () => listApplicationDocuments(token, applicationId),
    enabled: Boolean(token && applicationId),
    retry: false,
  });

  const outstanding = (documentsQuery.data ?? []).filter(
    (document) =>
      document.is_latest &&
      document.superseded_by === null &&
      document.verification_status === "REJECTED",
  );
  if (outstanding.length === 0) {
    return null;
  }
  const due = outstanding
    .map((document) => document.deficiency_due_date)
    .filter((value): value is string => Boolean(value))
    .sort()[0];

  return (
    <Panel title="Document replacement">
      <p className="text-13 leading-5 text-ink-700">
        Waiting for the institution to re-upload {outstanding.length}{" "}
        {outstanding.length === 1 ? "document" : "documents"}
        {due ? ` (due ${formatDate(due)}` : " ("}
        {due ? ", APH 1.8f / 2.4)" : "APH 1.8f / 2.4)"}.
      </p>
      <dl className="mt-3 flex flex-wrap items-center gap-x-6 gap-y-2 border-t border-line pt-3 text-13">
        <div>
          <dt className="text-12 font-medium text-ink-500">Owner</dt>
          <dd className="mt-0.5 text-ink">Institution admin</dd>
        </div>
        <div>
          <dt className="text-12 font-medium text-ink-500">Due</dt>
          <dd className="mt-0.5 tabular-nums text-ink">
            {due ? formatDate(due) : "No deadline set"}
          </dd>
        </div>
      </dl>
    </Panel>
  );
}

function RelatedAlerts({
  applicationId,
  token,
}: {
  applicationId: string;
  token: string;
}) {
  const alertsQuery = useQuery({
    queryKey: ["alerts", "application", applicationId],
    queryFn: () => getAlerts(token, { pageSize: 50, applicationId }),
    enabled: Boolean(token && applicationId),
    retry: false,
  });

  const alerts = alertsQuery.data?.items ?? [];

  return (
    <Panel title="Related alerts">
      {alertsQuery.isPending ? (
        <div className="space-y-2" role="status">
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-2/3" />
          <span className="sr-only">Loading related alerts</span>
        </div>
      ) : alertsQuery.isError ? (
        <p className="text-13 text-ink-500">
          {alertsQuery.error instanceof ApiError
            ? alertsQuery.error.message
            : "Alerts could not be loaded."}
        </p>
      ) : alerts.length === 0 ? (
        <p className="text-13 leading-5 text-ink-700">
          No alert addressed to you references this application.
        </p>
      ) : (
        <ul className="space-y-2">
          {alerts.map((alert) => (
            <li
              key={alert.id}
              className="rounded-input border border-line bg-paper p-3"
            >
              <div className="flex flex-wrap items-center gap-2">
                <StatusPill status={SEVERITY_PILL_TONE[alert.severity] ?? "watch"}>
                  {alert.severity}
                </StatusPill>
                <span className="text-12 text-ink-500">
                  {formatDate(alert.created_at)}
                </span>
              </div>
              <p className="mt-1 text-13 font-medium text-ink">{alert.title}</p>
              <p className="mt-0.5 text-12 leading-5 text-ink-700">
                {alert.message}
              </p>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}

export default function CaseSidebar({
  application,
  token,
}: {
  application: ApplicationDetail;
  token: string;
}) {
  const { actions } = useWorkflowActions();
  const complianceQuery = useQuery({
    queryKey: ["compliance-preview", application.id],
    queryFn: () => getApplicationCompliance(token, application.id),
    enabled: Boolean(token && application.id),
    retry: false,
  });

  const toneRank = (tone: AllowedAction["tone"]) =>
    tone === "primary" ? 0 : tone === "secondary" ? 1 : 2;
  const sortedActions = actions
    .slice()
    .sort((a, b) => toneRank(a.tone) - toneRank(b.tone));
  const explanation = computeRiskExplanation(complianceQuery.data);
  const errorText = complianceQuery.isError
    ? complianceQuery.error instanceof ApiError
      ? complianceQuery.error.message
      : "The compliance evaluation could not be loaded."
    : null;

  return (
    <aside className="min-w-0 space-y-6 self-start xl:sticky xl:top-6">
      <NextStepPanel application={application} actions={sortedActions} />
      <DocumentWaitingPanel applicationId={application.id} token={token} />
      <RiskExplanationPanel
        explanation={explanation}
        pending={complianceQuery.isPending}
        errorText={errorText}
      />
      <RelatedAlerts applicationId={application.id} token={token} />
    </aside>
  );
}
