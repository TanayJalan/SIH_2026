import { useQuery } from "@tanstack/react-query";

import { cn } from "@/lib/utils";
import {
  Button,
  Skeleton,
  Stat,
  StatusPill,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../ui";
import { StageTrack } from "../ui/StageTrack";
import { ScoreGauge } from "../ui/ScoreGauge";
import { useAuth } from "../../auth/AuthContext";
import {
  getInstitutionDashboard,
  type InstitutionDashboard,
  type ReportFilters,
} from "@/lib/api";
import { formatDate, formatInr } from "@/lib/format";
import PageHeader from "../PageHeader";

const STAGE_LABELS: Record<string, string> = {
  APPLICATION: "Application",
  DOCUMENT_VERIFICATION: "Documents",
  SCRUTINY: "Scrutiny",
  DEFICIENCY: "Deficiency",
  INSPECTION: "Inspection",
  COMMITTEE_REVIEW: "Committee",
  DECISION: "Decision",
  COMPLETED: "Completed",
};

const STAGE_KEYS: string[] = [
  "APPLICATION",
  "DOCUMENT_VERIFICATION",
  "SCRUTINY",
  "DEFICIENCY",
  "INSPECTION",
  "COMMITTEE_REVIEW",
  "DECISION",
  "COMPLETED",
];

function stageForStatus(status: string): string {
  switch (status) {
    case "DRAFT":
    case "SUBMITTED":
      return "APPLICATION";
    case "SCRUTINY":
    case "DEFICIENCY_COMMUNICATED":
    case "INSTITUTION_COMPLIANCE":
    case "RE_SCRUTINY":
      return status === "DEFICIENCY_COMMUNICATED" || status === "INSTITUTION_COMPLIANCE"
        ? "DEFICIENCY"
        : "SCRUTINY";
    case "EVC_CONSTITUTED":
    case "EVC_DONE":
      return "INSPECTION";
    case "REGULATION_BUREAU_OBSERVATIONS":
    case "EC_DECISION":
    case "COUNCIL_RATIFICATION":
      return "COMMITTEE_REVIEW";
    case "LOA_ISSUED":
    case "EOA_ISSUED":
    case "LOD_ISSUED":
    case "LOR_ISSUED":
    case "APPEAL_WINDOW":
    case "SAC_REVIEW":
    case "COUNCIL_FINAL":
    case "REGIONAL_ENDORSEMENT":
      return "DECISION";
    case "FINAL_LOA":
    case "FINAL_LOD":
    case "FINAL_LOR":
    case "ACTIVE_LOA":
    case "ACTIVE_EOA":
    case "CANCELLED":
    case "WITHDRAWN":
      return "COMPLETED";
    default:
      return "APPLICATION";
  }
}

function scoreBand(score: number | null): "compliant" | "watch" | "breach" {
  if (score == null) return "compliant";
  if (score >= 80) return "compliant";
  if (score >= 60) return "watch";
  return "breach";
}

export default function InstitutionDashboard() {
  const { user, token } = useAuth();

  const filters: ReportFilters = {};

  const dashboardQuery = useQuery({
    queryKey: ["reports", "institution", filters],
    queryFn: () => getInstitutionDashboard(token ?? "", filters),
    enabled: Boolean(token && user?.institution_id),
    retry: false,
  });

  if (!user) return null;

  const dashboard = dashboardQuery.data;
  const loading = dashboardQuery.isPending;

  return (
    <>
      <PageHeader
        eyebrow="Institution dashboard"
        title={dashboard?.institution_name ?? "Your institution"}
        description="Progress tracker for your application: deficiencies, fees, documents and upcoming deadlines."
        actions={
          dashboard?.application_id ? (
            <Button
              asChild
              variant="secondary"
              size="sm"
              disabled={loading}
            >
              <a
                href={`/applications/${dashboard.application_id}`}
                className="inline-flex items-center gap-1.5"
              >
                Open case file
              </a>
            </Button>
          ) : null
        }
      />

      {/* StageTrack hero */}
      <section className="mb-6 rounded-panel border border-line bg-surface">
        <div className="px-5 py-4 border-b border-line">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="font-serif text-20 font-semibold text-ink">
                Application workflow
              </h2>
              <p className="mt-1 text-12 text-ink-500">
                Stage track from the configured workflow ({dashboard?.apH_clause ?? "APH 1.4"}).
              </p>
            </div>
            <div className="text-right">
              <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-ink-500">
                Portal application no.
              </p>
              <p className="text-14 font-serif font-semibold text-ink truncate max-w-[200px] block">
                {dashboard?.portal_application_no ?? "—"}
              </p>
            </div>
          </div>
        </div>
        <div className="px-5 py-5">
          {loading ? (
            <div className="space-y-4" role="status">
              <Skeleton className="h-6 w-3/4" />
              <Skeleton className="h-4 w-1/2 mt-2" />
              <span className="sr-only">Loading stage track</span>
            </div>
          ) : dashboard ? (
            <StageTrack
              stages={STAGE_KEYS.map((id) => ({
                id,
                label: STAGE_LABELS[id],
              }))}
              current={stageForStatus(dashboard.status)}
              events={[]}
              label="Application workflow stages"
              className=""
            />
          ) : null}
        </div>
      </section>

      <section className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* What you need to do */}
        <section className="col-span-1 lg:col-span-2 rounded-panel border border-line bg-surface">
          <div className="border-b border-line px-5 py-4 flex items-center justify-between">
            <h2 className="font-serif text-18 font-semibold text-ink">
              What you need to do
            </h2>
            <p className="mt-1 text-12 text-ink-500">
              Open deficiencies, expiring documents and fees due
            </p>
          </div>
          <div className="p-5 space-y-4">
            {/* Open deficiencies */}
            <div>
              <h3 className="text-13 font-semibold text-ink mb-3">
                Open deficiencies
                <span className="text-[10px] font-normal text-ink-500 ml-2">
                  (APH 2.3.3b)
                </span>
              </h3>
              {loading ? (
                <div className="space-y-2">
                  <Skeleton className="h-10 w-full" />
                  <Skeleton className="h-10 w-1/2" />
                </div>
              ) : dashboard?.open_deficiencies.length === 0 ? (
                <p className="text-12 text-ink-500">
                  No open deficiencies. <span className="text-ok-strong font-medium">Nil Deficiency position.</span>
                </p>
              ) : (
                <ul className="space-y-2">
                  {dashboard!.open_deficiencies.map((d) => (
                    <li
                      key={d.deficiency_id}
                      className="rounded-input border border-line bg-surface p-3"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2 mb-1">
                        <span className="text-[10px] font-semibold text-ink-700">
                          {d.category}
                        </span>
                        <StatusPill
                          status={
                            d.days_left != null && d.days_left <= 3
                              ? "breach"
                              : d.days_left != null && d.days_left <= 7
                                ? "watch"
                                : "info"
                          }
                        >
                          {d.days_left != null
                            ? `${d.days_left} day${d.days_left === 1 ? "" : "s"} left`
                            : "No due date"}
                        </StatusPill>
                      </div>
                      <p className="text-12 text-ink-700 truncate">
                        {d.description}
                      </p>
                      <p className="mt-1 text-[10px] text-ink-500">
                        Due {formatDate(d.due_date)} · {d.apH_clause}
                      </p>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {/* Expiring documents */}
            <div className="mt-5">
              <h3 className="text-13 font-semibold text-ink mb-3">
                Documents expiring
                <span className="text-[10px] font-normal text-ink-500 ml-2">
                  (APH 6.17h)
                </span>
              </h3>
              {loading ? (
                <div className="space-y-2">
                  <Skeleton className="h-10 w-full" />
                  <Skeleton className="h-10 w-1/2" />
                </div>
              ) : dashboard?.expiring_documents.length === 0 ? (
                <p className="text-12 text-ink-500">
                  No documents expiring within 60 days.
                </p>
              ) : (
                <ul className="space-y-2">
                  {dashboard!.expiring_documents.map((d) => (
                    <li key={d.document_id} className="rounded-input border border-line bg-surface p-3">
                      <div className="flex flex-wrap items-center justify-between gap-2 mb-1">
                        <span className="text-[10px] font-semibold text-ink-700">
                          {d.doc_type}
                        </span>
                        <span
                          className={cn(
                            "text-[10px] font-medium rounded-input px-1.5 py-0.5",
                            (d.days_left != null && d.days_left <= 7)
                              ? "bg-breach-soft text-breach-strong"
                              : "bg-info-soft text-info-strong",
                          )}
                        >
                          {d.days_left != null
                            ? `${d.days_left} day${d.days_left === 1 ? "" : "s"} left`
                            : "No expiry"}
                        </span>
                      </div>
                      <p className="text-12 text-ink-700 truncate">{d.filename}</p>
                      <p className="mt-1 text-[10px] text-ink-500">
                        Expires {formatDate(d.expiry_date ?? d.valid_until)} ·
                        {d.apH_clause}
                      </p>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            {/* Fees */}
            <div className="mt-5">
              <h3 className="text-13 font-semibold text-ink mb-3">
                Fees
                <span className="text-[10px] font-normal text-ink-500 ml-2">
                  (APH 4)
                </span>
              </h3>
              <div className="grid grid-cols-2 gap-3 mb-2">
                <Stat
                  figure={formatInr(dashboard?.fees.total_paise ?? 0)}
                  caption="Total TER"
                  delta="TER amount"
                />
                <Stat
                  figure={formatInr(dashboard?.fees.due_paise ?? 0)}
                  caption="Due"
                  delta="Amount payable"
                  deltaTone={(dashboard?.fees.due_paise ?? 0) > 0 ? "negative" : "neutral"}
                />
              </div>
              <div className="grid grid-cols-2 gap-2">
                <Stat
                  figure={formatInr(dashboard?.fees.paid_paise ?? 0)}
                  caption="Paid"
                  delta="TER paid"
                />
                <Stat
                  figure={formatInr(dashboard?.fees.refunded_paise ?? 0)}
                  caption="Refunded"
                  delta="Refunded to you"
                />
              </div>
            </div>
          </div>
        </section>

        {/* Compliance score + how to improve + deadlines */}
        <section className="col-span-1 lg:col-span-1 rounded-panel border border-line bg-surface p-5">
          <div className="border-b border-line px-0 py-0">
            <div className="px-5 py-4 flex items-center justify-between">
              <div>
                <h2 className="font-serif text-18 font-semibold text-ink">
                  Compliance score
                </h2>
                <p className="mt-1 text-12 text-ink-500">
                  Latest compliance evaluation · {dashboard?.apH_clause ?? "APH 1.4"}
                </p>
              </div>
            </div>
          </div>
          <div className="p-5 space-y-5">
            <div className="flex flex-col lg:flex-row lg:items-center gap-6">
              <div className="flex-1 max-w-[260px]">
                {loading ? (
                  <Skeleton className="h-40 w-full" />
                ) : (
                  <ScoreGauge
                    value={dashboard?.compliance_score ?? 0}
                    band={scoreBand(dashboard?.compliance_score ?? null)}
                    caption="Compliance score"
                    className="w-full max-w-[260px]"
                  />
                )}
              </div>
              <div className="flex-1">
                <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-ink-500 mb-3">
                  How to improve
                </p>
                {loading ? (
                  <div className="space-y-2">
                    <Skeleton className="h-10 w-3/4" />
                    <Skeleton className="h-10 w-1/2" />
                  </div>
                ) : dashboard?.top_failing_rules.length === 0 ? (
                  <p className="text-12 text-ink-500">
                    No failing mandatory rules. Your compliance position is strong.
                  </p>
                ) : (
                  <ul className="space-y-3">
                    {dashboard!.top_failing_rules.map((rule) => (
                      <li key={rule.code} className="rounded-input border border-line bg-surface p-3">
                        <div className="flex items-center justify-between gap-2 mb-1">
                          <span className="text-[10px] font-semibold text-ink-700">
                            {rule.code}
                          </span>
                          <span className="text-[10px] font-medium text-breach-strong">
                            FAIL
                          </span>
                        </div>
                        <p className="text-12 text-ink-700 truncate">
                          {rule.name}
                        </p>
                        <p className="mt-1 text-[10px] text-ink-500">
                          {rule.message ?? "No detail recorded."}
                        </p>
                        {rule.fix_text ? (
                          <p className="mt-1 text-[10px] text-ink-500">
                            <span className="font-semibold text-ink-700">Fix:</span>{" "}
                            {rule.fix_text}
                          </p>
                        ) : null}
                        <p className="mt-1 text-[10px] text-ink-500">
                          {rule.apH_clause}
                        </p>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            </div>

            {/* Upcoming deadlines */}
            <div className="mt-5 border-t border-line pt-5">
              <h3 className="text-13 font-semibold text-ink mb-3">
                Upcoming deadlines
                <span className="text-[10px] font-normal text-ink-500 ml-2">
                  (APH 5)
                </span>
              </h3>
              {loading ? (
                <div className="space-y-2">
                  <Skeleton className="h-10 w-full" />
                  <Skeleton className="h-10 w-1/2" />
                </div>
              ) : dashboard?.upcoming_deadlines.length === 0 ? (
                <p className="text-12 text-ink-500">
                  No upcoming academic-calendar deadlines in scope.
                </p>
              ) : (
                <Table density="dense">
                  <TableHeader>
                    <TableRow>
                      <TableHead>Deadline</TableHead>
                      <TableHead className="text-right">Due</TableHead>
                      <TableHead className="text-right">Days left</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {dashboard!.upcoming_deadlines.map((d) => (
                      <TableRow key={d.key}>
                        <TableCell className="text-ink">
                          {d.label}
                          <p className="mt-0.5 text-[10px] text-ink-500">
                            {d.apH_clause}
                          </p>
                        </TableCell>
                        <TableCell className="text-right text-13 text-ink-700">
                          {formatDate(d.due_on)}
                        </TableCell>
                        <TableCell className="text-right">
                          <span
                            className={cn(
                              "text-11 font-medium rounded-input px-1.5 py-0.5",
                              (d.days_left != null && d.days_left <= 7)
                                ? "bg-breach-soft text-breach-strong"
                                : "bg-info-soft text-info-strong",
                            )}
                          >
                            {d.days_left != null
                              ? `${d.days_left} day${d.days_left === 1 ? "" : "s"} left`
                              : "—"}
                          </span>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </div>
          </div>
        </section>
      </section>
    </>
  );
}
