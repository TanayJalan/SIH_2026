import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip } from "recharts";
import { Clock, Building } from "lucide-react";

import {
  Button,
  EmptyState,
  Skeleton,
  Stat,
  StatusPill,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
  Tabs,
  TabsList,
  TabsTrigger,
  RiskBadge,
  SlaRing,
} from "../ui";
import { useAuth } from "../../auth/AuthContext";
import {
  getRegulationBureauDashboard,
  type ReportFilters,
} from "@/lib/api";
import { humanizeEnum, formatDate } from "@/lib/format";
import PageHeader from "../PageHeader";

const STAGE_ORDER: WorkflowStage[] = [
  "APPLICATION",
  "DOCUMENT_VERIFICATION",
  "SCRUTINY",
  "DEFICIENCY",
  "INSPECTION",
  "COMMITTEE_REVIEW",
  "DECISION",
  "COMPLETED",
];

function slaState(dueAt: string | null): "ok" | "watch" | "breach" {
  if (!dueAt) return "ok";
  const due = new Date(dueAt).getTime();
  const now = new Date().getTime();
  const days = (due - now) / 86_400_000;
  if (days < 0) return "breach";
  if (days <= 3) return "watch";
  return "ok";
}

function riskFor(entry: { status: string; days_overdue: number | null }): "low" | "medium" | "high" {
  if (entry.days_overdue != null && entry.days_overdue > 0) return "high";
  if (entry.status === "DEFICIENCY_COMMUNICATED") return "high";
  if (entry.status === "SCRUTINY" || entry.status === "RE_SCRUTINY") return "medium";
  return "low";
}

function statusPillTone(status: string): "compliant" | "watch" | "breach" | "info" | "neutral" {
  const toneMap: Record<string, "compliant" | "watch" | "breach" | "info" | "neutral"> = {
    APPEAL_WINDOW: "watch",
    SECURITY_DEPOSIT_PENDING: "watch",
    DRAFT: "neutral",
    SUBMITTED: "info",
    SCRUTINY: "watch",
    DEFICIENCY_COMMUNICATED: "breach",
    INSTITUTION_COMPLIANCE: "watch",
    RE_SCRUTINY: "watch",
    EVC_CONSTITUTED: "info",
    EVC_DONE: "info",
    REGULATION_BUREAU_OBSERVATIONS: "watch",
    EC_DECISION: "watch",
    COUNCIL_RATIFICATION: "watch",
    LOA_ISSUED: "compliant",
    LOD_ISSUED: "breach",
    LOR_ISSUED: "breach",
    SAC_REVIEW: "watch",
    COUNCIL_FINAL: "watch",
    REGIONAL_ENDORSEMENT: "watch",
    FINAL_LOA: "compliant",
    FINAL_LOD: "breach",
    FINAL_LOR: "breach",
    ACTIVE_LOA: "compliant",
    ACTIVE_EOA: "compliant",
    CANCELLED: "breach",
    WITHDRAWN: "neutral",
    SELF_DISCLOSURE_CHECK: "info",
    RANDOM_EVC: "info",
    COMPLIANCE_WINDOW: "watch",
    EC_LISTING: "watch",
    EOA_ISSUED: "compliant",
    SPEAKING_ORDER: "watch",
    SHC_HEARING: "watch",
    CLOSED: "neutral",
  };
  return toneMap[status] ?? "neutral";
}

export default function OfficerDashboard() {
  const { user, token } = useAuth();
  const [filterStage, setFilterStage] = useState<string>("all");

  const filters: ReportFilters = {};

  const dashboardQuery = useQuery({
    queryKey: ["reports", "regulation-bureau", filters],
    queryFn: () => getRegulationBureauDashboard(token ?? "", filters),
    enabled: Boolean(token),
    retry: false,
  });

  if (!user) return null;

  const dashboard = dashboardQuery.data;
  const loading = dashboardQuery.isPending;

  const overdue = (dashboard?.overdue ?? []).filter(
    (entry) =>
      filterStage === "all" || entry.current_stage === filterStage,
  );

  const stageCounts = new Map<string, number>();
  for (const entry of dashboard?.by_stage ?? []) {
    stageCounts.set(entry.stage, entry.count);
  }

  // Precompute queue content to avoid nested ternaries in JSX.
  let queueContent: React.ReactNode;
  if (loading) {
    queueContent = (
      <div className="p-6" role="status">
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} className="h-12 w-full" />
        ))}
      </div>
    );
  } else if (overdue.length === 0) {
    queueContent = (
      <div className="p-6">
        <EmptyState
          message="No queue entries match the current stage filter."
          action={<Button variant="secondary" size="sm">Refresh</Button>}
        />
      </div>
    );
  } else {
    queueContent = (
      <Table density="dense">
        <TableHeader>
          <TableRow>
            <TableHead>Application</TableHead>
            <TableHead className="text-right">Institution</TableHead>
            <TableHead className="text-right">Status</TableHead>
            <TableHead className="text-right">Stage</TableHead>
            <TableHead className="text-right">SLA</TableHead>
            <TableHead className="text-right">Risk</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {overdue.map((entry) => {
            const state = slaState(entry.sla_due_at);
            const daysLeft = entry.days_overdue != null ? -entry.days_overdue : null;
            const risk = riskFor(entry);
            const slastringValue =
              daysLeft != null
                ? Math.max(0, Math.min(100, 100 - Math.abs(daysLeft) * 10))
                : 0;
            const slaLabel =
              daysLeft != null
                ? daysLeft <= 0
                  ? `${Math.abs(daysLeft)} overdue`
                  : `${daysLeft} left`
                : "—";
            return (
              <TableRow key={entry.application_id}>
                <TableCell className="text-ink">
                  <div className="flex items-center gap-2">
                    <Building className="size-3.5 text-ink-500" />
                    <div className="min-w-0">
                      <span className="text-13 font-medium text-ink truncate">
                        {entry.portal_application_no ?? shortId(entry.application_id)}
                      </span>
                      <p className="text-[10px] text-ink-500 truncate">
                        {entry.institution_name}
                      </p>
                    </div>
                  </div>
                </TableCell>
                <TableCell className="text-right text-13 text-ink-700 truncate max-w-[120px]">
                  {entry.institution_name}
                </TableCell>
                <TableCell className="text-right">
                  <StatusPill status={statusPillTone(entry.status)}>
                    {humanizeEnum(entry.status)}
                  </StatusPill>
                </TableCell>
                <TableCell className="text-right text-[11px] text-ink-500">
                  {humanizeEnum(entry.current_stage)}
                </TableCell>
                <TableCell className="text-right">
                  <div className="flex items-center gap-2">
                    <SlaRing
                      value={slastringValue}
                      daysLeft={daysLeft ?? 0}
                      state={state}
                      className="size-7"
                    />
                    <span className="text-[10px] font-medium">{slaLabel}</span>
                  </div>
                </TableCell>
                <TableCell className="text-right">
                  <RiskBadge level={risk} />
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    );
  }

  // Precompute workload content.
  let workloadContent: React.ReactNode;
  if (loading) {
    workloadContent = (
      <div className="p-6" role="status">
        <Skeleton className="h-48 w-full" />
      </div>
    );
  } else {
    workloadContent = (
      <div className="p-5">
        <ResponsiveContainer width="100%" height={260}>
          <BarChart
            data={STAGE_ORDER.map((stage) => ({
              stage: humanizeEnum(stage),
              count: stageCounts.get(stage) ?? 0,
            }))}
          >
            <XAxis dataKey="stage" tick={{ fontSize: 11 }} />
            <YAxis type="number" dataKey="count" hide />
            <Tooltip
              cursor={{ fill: "var(--ink-200)" }}
              content={({ active, payload }: any) => {
                if (active && payload && payload.length) {
                  const entry = payload[0].payload;
                  return (
                    <div className="rounded-input border border-line bg-surface p-2 text-ink">
                      <p className="text-11 font-medium">{entry.stage}</p>
                      <p className="text-10 text-ink-500">
                        {entry.count} application{entry.count === 1 ? "" : "s"}
                      </p>
                    </div>
                  );
                }
                return null;
              }}
            />
            <Bar dataKey="count" fill="var(--saffron)" radius={[0, 4, 4, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    );
  }

  // Precompute EVC content.
  let evcContent: React.ReactNode;
  if (loading) {
    evcContent = (
      <div className="p-6" role="status">
        <Skeleton className="h-12 w-full" />
        <Skeleton className="h-12 w-2/3 mt-2" />
      </div>
    );
  } else if ((dashboard?.upcoming_evc_dates ?? []).length === 0) {
    evcContent = (
      <div className="p-6">
        <EmptyState
          message="No Expert Visit Committee visits scheduled."
          action={<Button variant="secondary" size="sm">Refresh</Button>}
        />
      </div>
    );
  } else {
    evcContent = (
      <Table density="dense">
        <TableHeader>
          <TableRow>
            <TableHead>Institution</TableHead>
            <TableHead className="text-right">Application</TableHead>
            <TableHead className="text-right">Scheduled</TableHead>
            <TableHead className="text-right">Status</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {(dashboard?.upcoming_evc_dates ?? []).map((evc) => (
            <TableRow key={evc.inspection_id}>
              <TableCell className="text-ink truncate max-w-[150px]">
                {evc.institution_name}
              </TableCell>
              <TableCell className="text-right text-13 text-ink-700 truncate max-w-[100px]">
                {evc.portal_application_no ?? shortId(evc.application_id)}
              </TableCell>
              <TableCell className="text-right text-13 text-ink-700">
                {formatDate(evc.scheduled_on)}
              </TableCell>
              <TableCell className="text-right">
                <StatusPill
                  status={evc.status === "SCHEDULED" ? "info" : "compliant"}
                >
                  {humanizeEnum(evc.status)}
                </StatusPill>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    );
  }

  return (
    <>
      <PageHeader
        eyebrow="Officer dashboard"
        title="My queue"
        description="Applications awaiting your action, sorted by risk and SLA. Queue entries come from the workflow state machine."
        actions={
          <Button
            variant="secondary"
            size="sm"
            onClick={() => void dashboardQuery.refetch()}
            disabled={loading}
          >
            Refresh
          </Button>
        }
      />

      {/* Quiet stat row */}
      <section className="mb-6 grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat
          figure={String(dashboard?.total_in_queue ?? 0)}
          caption="Applications in queue"
          delta="Not withdrawn, not terminal"
        />
        <Stat
          figure={String(dashboard?.overdue_count ?? 0)}
          caption="Over SLA"
          delta="Past the stage due date"
          deltaTone={(dashboard?.overdue_count ?? 0) > 0 ? "negative" : "neutral"}
        />
        <Stat
          figure={String(dashboard?.awaiting_institution_compliance ?? 0)}
          caption="Awaiting institution compliance"
          delta="Institution must respond"
        />
        <Stat
          figure={
            dashboard?.average_handling_days == null
              ? "—"
              : dashboard.average_handling_days.toFixed(1)
          }
          caption="Avg handling days"
          delta="Submitted → decision"
        />
      </section>

      {/* My queue table */}
      <section className="mb-6 rounded-panel border border-line bg-surface">
        <div className="border-b border-line px-5 py-4 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <Clock className="size-4 text-ink-500" />
            <div>
              <h2 className="font-serif text-18 font-semibold text-ink">My queue</h2>
              <p className="mt-1 text-12 text-ink-500">
                Sort by risk, then SLA. Click a row to open the case file.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-11 font-medium text-ink-500">Stage</span>
            <Tabs
              value={filterStage}
              onValueChange={setFilterStage}
              className="bg-transparent border-none"
            >
              <TabsList>
                <TabsTrigger value="all">All stages</TabsTrigger>
                {STAGE_ORDER.map((stage) => (
                  <TabsTrigger key={stage} value={stage}>
                    {humanizeEnum(stage)}
                  </TabsTrigger>
                ))}
              </TabsList>
            </Tabs>
          </div>
        </div>
        {queueContent}
      </section>

      {/* Workload by stage + upcoming EVCs */}
      <section className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-2">
        <section className="min-w-0 rounded-panel border border-line bg-surface">
          <div className="border-b border-line px-5 py-4">
            <h2 className="font-serif text-18 font-semibold text-ink">
              Workload by stage
            </h2>
            <p className="mt-1 text-12 text-ink-500">
              Applications currently at each stage
            </p>
          </div>
          {workloadContent}
        </section>

        <section className="min-w-0 rounded-panel border border-line bg-surface">
          <div className="border-b border-line px-5 py-4 flex items-center justify-between">
            <div>
              <h2 className="font-serif text-18 font-semibold text-ink">
                Upcoming EVCs
              </h2>
              <p className="mt-1 text-12 text-ink-500">
                Expert Visit Committee visits scheduled
              </p>
            </div>
          </div>
          {evcContent}
        </section>
      </section>
    </>
  );
}

type WorkflowStage =
  | "APPLICATION"
  | "DOCUMENT_VERIFICATION"
  | "SCRUTINY"
  | "DEFICIENCY"
  | "INSPECTION"
  | "COMMITTEE_REVIEW"
  | "DECISION"
  | "COMPLETED";

function shortId(value: string): string {
  return value.slice(0, 8).toUpperCase();
}
