import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { Building, IndianRupee } from "lucide-react";

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
} from "../ui";
import {
  getRegionalDashboard,
  type RegionalDashboard,
  type ReportFilters,
} from "@/lib/api";
import { useAuth } from "../../auth/AuthContext";
import { humanizeEnum, formatDate, shortId } from "@/lib/format";
import PageHeader from "../PageHeader";
import { IndiaTileMap, type TileMetric } from "./IndiaTileMap";

const COMPLIANCE_TONES: Record<string, "compliant" | "watch" | "breach"> = {
  GREEN: "compliant",
  AMBER: "watch",
  RED: "breach",
};

function statValue(value: number | null): string {
  return value == null ? "—" : String(value);
}

function avgDays(stages: { average_days: number }[]): number {
  if (stages.length === 0) return 0;
  return stages.reduce((sum, s) => sum + s.average_days, 0) / stages.length;
}

function redCount(institutions: { status: string }[]): number {
  return institutions.filter((i) => i.status === "RED").length;
}

function reasonForStatus(status: string): string {
  if (status === "RED") return "Compliance RED";
  if (status === "AMBER") return "Compliance AMBER";
  return "Watch";
}

function statusPillForSecurityDeposit(status: string): "compliant" | "watch" | "breach" {
  if (status === "PAID") return "compliant";
  if (status === "PENALTY_10") return "watch";
  return "breach";
}

export default function RegionalDashboard() {
  const { user, token } = useAuth();
  const [metric, setMetric] = useState<TileMetric>("compliance");
  const [selectedState, setSelectedState] = useState<string | null>(null);

  const filters: ReportFilters = {};

  const dashboardQuery = useQuery({
    queryKey: ["reports", "regional", filters],
    queryFn: () => getRegionalDashboard(token ?? "", filters),
    enabled: Boolean(token),
    retry: false,
  });

  if (!user) return null;

  const dashboard = dashboardQuery.data;
  const loading = dashboardQuery.isPending;

  const totalApplications = dashboard?.total_applications ?? 0;
  const avgDaysToDecision = dashboard ? avgDays(dashboard.average_days_per_stage) : 0;
  const slaBreach = dashboard?.sla_breach;
  const institutions = dashboard?.institutions_by_compliance ?? [];
  const institutionsInRed = redCount(institutions);

  // Needs attention: institutions ordered by non-GREEN count then lowest score.
  const byState = new Map<
    string,
    {
      name: string;
      state: string;
      region: string;
      score: number;
      status: string;
      count: number;
      red: number;
      amber: number;
      green: number;
    }
  >();
  for (const inst of institutions) {
    const current = byState.get(inst.state) ?? {
      name: inst.name,
      state: inst.state,
      region: inst.region,
      score: 0,
      status: inst.status,
      count: 0,
      red: 0,
      amber: 0,
      green: 0,
    };
    current.count += 1;
    current.score += inst.score;
    current.status = inst.status;
    if (inst.status === "RED") current.red += 1;
    else if (inst.status === "AMBER") current.amber += 1;
    else if (inst.status === "GREEN") current.green += 1;
    byState.set(inst.state, current);
  }
  const needsAttention = Array.from(byState.values())
    .map((inst) => ({
      ...inst,
      avgScore: inst.count ? inst.score / inst.count : 0,
      nonGreen: inst.red + inst.amber,
    }))
    .sort((a, b) => b.nonGreen - a.nonGreen || a.avgScore - b.avgScore)
    .slice(0, 8);

  const escalationByInstitution = new Map(
    (dashboard?.escalations ?? []).map((e) => [e.institution_name, e.level]),
  );

  return (
    <>
      <PageHeader
        eyebrow="Regional dashboard"
        title="Regional oversight"
        description="Applications, compliance and SLA position across institutions in your scope. Figures come from SQL aggregations over configured rules."
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
          figure={statValue(totalApplications)}
          caption="Applications in progress"
          delta="All tracks and statuses"
        />
        <Stat
          figure={avgDaysToDecision.toFixed(1)}
          caption="Avg days to decision"
          delta="Per stage, across stages"
          deltaTone={avgDaysToDecision > 30 ? "negative" : "neutral"}
        />
        <Stat
          figure={statValue(slaBreach?.breached ?? null)}
          caption="SLA breaches"
          delta={`${slaBreach?.breach_rate ?? 0}% of tracked`}
          deltaTone={slaBreach?.breach_rate ?? 0 > 20 ? "negative" : "neutral"}
        />
        <Stat
          figure={statValue(institutionsInRed)}
          caption="Institutions in RED"
          delta="Compliance monitoring"
          deltaTone={institutionsInRed > 0 ? "negative" : "neutral"}
        />
      </section>

      {/* Main grid: tile map + needs attention */}
      <section className="mb-6 grid grid-cols-1 gap-6 md:grid-cols-[1fr_340px]">
        <section className="min-w-0 rounded-panel border border-line bg-surface">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-5 py-4">
            <div>
              <h2 className="font-serif text-20 font-semibold text-ink">
                Institutional compliance
              </h2>
              <p className="mt-1 text-12 text-ink-500">
                Tile-coloured by compliance RAG.
              </p>
            </div>
            <div className="text-right">
              <p className="text-10 font-semibold uppercase tracking-[0.12em] text-ink-500">
                Institutions
              </p>
              <p className="text-14 font-serif font-semibold text-ink">
                {institutions.length}
              </p>
            </div>
          </div>
          {loading ? (
            <div className="p-6" role="status">
              <Skeleton className="h-48 w-full" />
              <Skeleton className="h-4 w-1/3 mt-2" />
              <span className="sr-only">Loading tile map</span>
            </div>
          ) : (
            <IndiaTileMap
              data={institutions}
              metric={metric}
              onMetricChange={setMetric}
              selectedState={selectedState}
              onSelectState={setSelectedState}
            />
          )}
        </section>

        <section className="min-w-0 rounded-panel border border-line bg-surface">
          <div className="border-b border-line px-5 py-4">
            <h2 className="font-serif text-18 font-semibold text-ink">
              Needs attention
            </h2>
            <p className="mt-1 text-12 text-ink-500">
              Ordered by non-GREEN institutions, then lowest average score.
            </p>
          </div>
          {loading || needsAttention.length === 0 ? (
            <div className="p-6">
              {loading ? (
                <>
                  <Skeleton className="h-10 w-full" />
                  <Skeleton className="h-10 w-3/4 mt-2" />
                </>
              ) : (
                <EmptyState
                  message="No institutions need attention in the current scope."
                  action={<Button variant="secondary" size="sm">Refresh</Button>}
                />
              )}
            </div>
          ) : (
            <Table density="dense">
              <TableHeader>
                <TableRow>
                  <TableHead>Institution</TableHead>
                  <TableHead className="text-right">Reason</TableHead>
                  <TableHead className="text-right">Days overdue</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {needsAttention.map((inst) => {
                  const level = escalationByInstitution.get(inst.name);
                  const daysOverdue = level != null ? level * 7 : null;
                  const reason = reasonForStatus(inst.status);
                  return (
                    <TableRow key={inst.state}>
                      <TableCell className="text-ink">
                        <div className="flex items-center gap-2">
                          <Building className="size-3.5 text-ink-500" />
                          <span className="text-13 font-medium">{inst.name}</span>
                        </div>
                        <p className="text-[10px] text-ink-500">
                          {inst.state} · {inst.region}
                        </p>
                      </TableCell>
                      <TableCell className="text-right text-13 text-ink-700">
                        <div className="flex items-end gap-2">
                          <StatusPill
                            status={COMPLIANCE_TONES[inst.status] ?? "neutral"}
                          >
                            {reason}
                          </StatusPill>
                          <span className="text-[10px] font-medium text-ink-700">
                            APH 7.13
                          </span>
                        </div>
                      </TableCell>
                      <TableCell className="text-right">
                        {daysOverdue != null ? (
                          <div className="flex items-end gap-1">
                            <span className="text-13 font-semibold text-breach-strong">
                              {daysOverdue}
                            </span>
                            <span className="text-[10px] text-ink-500">days</span>
                          </div>
                        ) : (
                          <span className="text-[10px] text-ink-500">—</span>
                        )}
                        {level != null && (
                          <p className="text-[9px] text-ink-400 mt-0.5">
                            Escalation level {level} (illustrative)
                          </p>
                        )}
                      </TableCell>
                    </TableRow>
                  );
                })}
              </TableBody>
            </Table>
          )}
        </section>
      </section>

      {/* Charts row */}
      <section className="grid grid-cols-1 gap-6 md:grid-cols-3 lg:grid-cols-4">
        {/* Funnel */}
        <section className="min-w-0 rounded-panel border border-line bg-surface col-span-2 md:col-span-2 lg:col-span-1">
          <div className="border-b border-line px-5 py-4 flex items-center justify-between">
            <h2 className="font-serif text-18 font-semibold text-ink">Funnel</h2>
            <p className="text-11 text-ink-500">Submitted → LoA / EoA</p>
          </div>
          {loading ? (
            <div className="p-6" role="status">
              {[0, 1, 2].map((i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          ) : (
            <div className="p-5">
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={dashboard?.funnel ?? []} layout="vertical">
                  <XAxis type="number" dataKey="count" hide />
                  <YAxis
                    type="category"
                    dataKey="stage"
                    tick={{ fontSize: 11, fill: "var(--ink-500)" }}
                    axisLine={false}
                    tickLine={false}
                  />
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
              <div className="mt-3 flex justify-end text-[10px] text-ink-500">
                Bar length = applications at that stage
              </div>
            </div>
          )}
        </section>

        {/* Top violation codes */}
        <section className="min-w-0 rounded-panel border border-line bg-surface col-span-2 md:col-span-2 lg:col-span-1">
          <div className="border-b border-line px-5 py-4">
            <h2 className="font-serif text-18 font-semibold text-ink">
              Top violation codes
            </h2>
            <p className="mt-1 text-12 text-ink-500">APH 7.4 penal actions</p>
          </div>
          {loading ? (
            <div className="p-6" role="status">
              {[0, 1, 2].map((i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          ) : (
            <div className="p-5">
              <ResponsiveContainer width="100%" height={220}>
                <BarChart
                  data={(dashboard?.top_violation_codes ?? []).slice(0, 6)}
                  layout="vertical"
                >
                  <XAxis type="number" dataKey="count" hide />
                  <YAxis
                    type="category"
                    dataKey="code"
                    tick={{ fontSize: 11, fill: "var(--ink-500)" }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <Tooltip
                    cursor={{ fill: "var(--ink-200)" }}
                    content={({ active, payload }: any) => {
                      if (active && payload && payload.length) {
                        const entry = payload[0].payload;
                        return (
                          <div className="rounded-input border border-line bg-surface p-2 text-ink">
                            <p className="text-11 font-medium">
                              Violation {entry.code}
                            </p>
                            <p className="text-10 text-ink-500">
                              {entry.count} action{entry.count === 1 ? "" : "s"}
                            </p>
                          </div>
                        );
                      }
                      return null;
                    }}
                  />
                  <Bar dataKey="count" fill="var(--breach)" radius={[0, 4, 4, 0]} />
                </BarChart>
              </ResponsiveContainer>
              <div className="mt-3 flex justify-end text-[10px] text-ink-500">
                Most frequent penal-action codes
              </div>
            </div>
          )}
        </section>

        {/* Compliance histogram */}
        <section className="min-w-0 rounded-panel border border-line bg-surface col-span-2 md:col-span-2 lg:col-span-1">
          <div className="border-b border-line px-5 py-4">
            <h2 className="font-serif text-18 font-semibold text-ink">
              Compliance histogram
            </h2>
            <p className="mt-1 text-12 text-ink-500">
              Institutions by latest score
            </p>
          </div>
          {loading ? (
            <div className="p-6" role="status">
              {[0, 1, 2].map((i) => (
                <Skeleton key={i} className="h-10 w-full" />
              ))}
            </div>
          ) : (
            <div className="p-5">
              <ResponsiveContainer width="100%" height={220}>
                <BarChart
                  data={histogramBins(institutions)}
                  layout="vertical"
                >
                  <XAxis type="number" dataKey="count" hide />
                  <YAxis
                    type="category"
                    dataKey="band"
                    tick={{ fontSize: 11, fill: "var(--ink-500)" }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <Tooltip
                    cursor={{ fill: "var(--ink-200)" }}
                    content={({ active, payload }: any) => {
                      if (active && payload && payload.length) {
                        const entry = payload[0].payload;
                        return (
                          <div className="rounded-input border border-line bg-surface p-2 text-ink">
                            <p className="text-11 font-medium">{entry.band}</p>
                            <p className="text-10 text-ink-500">
                              {entry.count} institution{entry.count === 1 ? "" : "s"}
                            </p>
                          </div>
                        );
                      }
                      return null;
                    }}
                  />
                  <Bar
                    dataKey="count"
                    fill="var(--saffron)"
                    radius={[0, 4, 4, 0]}
                  />
                </BarChart>
              </ResponsiveContainer>
              <div className="mt-3 flex justify-end text-[10px] text-ink-500">
                <span>RED</span>{" <80 · "}<span>AMBER 80–89 · </span><span>GREEN ≥ 90</span>
              </div>
            </div>
          )}
        </section>

        {/* Appeals + Deposits panels */}
        <section className="min-w-0 rounded-panel border border-line bg-surface col-span-2 md:col-span-2 lg:col-span-1">
          <div className="border-b border-line px-5 py-4">
            <h2 className="font-serif text-18 font-semibold text-ink">Appeals</h2>
            <p className="mt-1 text-12 text-ink-500">
              Single appeal window outcomes (APH 1.11)
            </p>
          </div>
          <div className="p-5 grid grid-cols-2 gap-3">
            <div className="rounded-input border border-line bg-surface p-3">
              <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-ink-500 mb-2">
                Filed
              </p>
              <p className="text-20 font-serif font-semibold text-ink">
                {dashboard?.appeals.filed ?? 0}
              </p>
            </div>
            <div className="rounded-input border border-line bg-surface p-3">
              <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-ink-500 mb-2">
                Within deadline
              </p>
              <p className="text-20 font-serif font-semibold text-ink">
                {dashboard?.appeals.within_deadline ?? 0}
              </p>
            </div>
            <div className="rounded-input border border-line bg-surface p-3 col-span-2">
              <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-ink-500 mb-2">
                SAC recommendation
              </p>
              <div className="flex gap-3 text-11 text-ink-700">
                <span>
                  Recommend{" "}
                  <span className="text-ink-500">{dashboard?.appeals.sac_recommend ?? 0}</span>
                </span>
                <span>
                  Not recommend{" "}
                  <span className="text-ink-500">{dashboard?.appeals.sac_not_recommend ?? 0}</span>
                </span>
                <span>
                  Send back{" "}
                  <span className="text-ink-500">{dashboard?.appeals.sac_send_back ?? 0}</span>
                </span>
              </div>
              <p className="mt-2 text-[10px] text-ink-500">
                Council:{" "}
                <span className="font-medium text-ink">
                  {dashboard?.appeals.council_allowed ?? 0} allowed
                </span>{" "}
                <span className="text-ink-500">·</span>{" "}
                <span className="font-medium text-ink">
                  {dashboard?.appeals.council_dismissed ?? 0} dismissed
                </span>
              </p>
              <p className="mt-1 text-[10px] text-ink-500">
                Appeal windows closing in 3 days:{""}
                <span className="font-medium text-ink">
                  {dashboard?.appeal_windows_closing_3_days ?? 0}
                </span>
              </p>
            </div>
          </div>
        </section>

        <section className="min-w-0 rounded-panel border border-line bg-surface col-span-2 md:col-span-2 lg:col-span-1">
          <div className="border-b border-line px-5 py-4">
            <h2 className="font-serif text-18 font-semibold text-ink">
              Security Deposits
            </h2>
            <p className="mt-1 text-12 text-ink-500">Pending with penalty status</p>
          </div>
          {loading ? (
            <div className="p-6" role="status">
              <Skeleton className="h-48 w-full" />
            </div>
          ) : dashboard?.security_deposits_pending?.length === 0 ? (
            <div className="p-6">
              <EmptyState
                message="No Security Deposits pending in the current scope."
                action={<Button variant="secondary" size="sm">Refresh</Button>}
              />
            </div>
          ) : (
            <Table density="dense">
              <TableHeader>
                <TableRow>
                  <TableHead>Institution</TableHead>
                  <TableHead className="text-right">Status</TableHead>
                  <TableHead className="text-right">Due</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(dashboard?.security_deposits_pending ?? []).map((d) => (
                  <TableRow key={d.application_id}>
                    <TableCell className="text-ink">
                      <div className="flex items-center gap-2">
                        <IndianRupee className="size-3.5 text-ink-500" />
                        <span className="truncate text-13 font-medium">
                          {d.institution_name}
                        </span>
                      </div>
                      <p className="text-[10px] text-ink-500">
                        {d.portal_application_no ?? shortId(d.application_id)}
                      </p>
                    </TableCell>
                    <TableCell className="text-right">
                      <StatusPill
                        status={statusPillForSecurityDeposit(d.status)}
                      >
                        {humanizeEnum(d.status)}
                      </StatusPill>
                      {d.penalty_percent != null && (
                        <p className="mt-0.5 text-[10px] text-ink-500">
                          {d.penalty_percent}% penalty
                        </p>
                      )}
                    </TableCell>
                    <TableCell className="text-right">
                      <span className="text-13 font-medium text-ink">
                        {formatDate(d.due_on)}
                      </span>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </section>
      </section>
    </>
  );
}

function histogramBins(
  institutions: { score: number; status: string }[],
): { band: string; count: number }[] {
  const red = institutions.filter((i) => i.status === "RED").length;
  const amber = institutions.filter((i) => i.status === "AMBER").length;
  const green = institutions.filter((i) => i.status === "GREEN").length;
  return [
    { band: "RED (< 80)", count: red, order: 0 },
    { band: "AMBER (80–89)", count: amber, order: 1 },
    { band: "GREEN (≥ 90)", count: green, order: 2 },
  ].sort((a, b) => a.order - b.order);
}
