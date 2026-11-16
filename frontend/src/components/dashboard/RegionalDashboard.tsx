import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  BarChart,
  Bar,
  Cell,
  LabelList,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { Building, IndianRupee } from "lucide-react";

import {
  Button,
  EmptyState,
  ErrorState,
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

const BAND_FILLS: Record<string, string> = {
  RED: "var(--breach)",
  AMBER: "var(--watch)",
  GREEN: "var(--ok)",
};

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

  // Needs attention: individual institutions, RED first then lowest score.
  const needsAttention = [...institutions]
    .filter((inst) => inst.status !== "GREEN")
    .sort((a, b) => {
      const rank = (status: string) =>
        status === "RED" ? 0 : status === "AMBER" ? 1 : 2;
      return rank(a.status) - rank(b.status) || a.score - b.score;
    })
    .slice(0, 8);

  const escalationByInstitution = new Map(
    (dashboard?.escalations ?? []).map((e) => [e.institution_name, e.level]),
  );

  if (dashboardQuery.isError) {
    return (
      <>
        <PageHeader
          eyebrow="Regional dashboard"
          title="Regional oversight"
          description="Applications, compliance and SLA position across institutions in your scope. Figures come from SQL aggregations over configured rules."
        />
        <ErrorState
          error={dashboardQuery.error}
          message="The regional dashboard could not be loaded. Check the API connection and try again."
          onRetry={() => void dashboardQuery.refetch()}
        />
      </>
    );
  }

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
      <section className="mb-6 grid grid-cols-1 items-start gap-6 xl:grid-cols-[minmax(0,1fr)_420px]">
        <section className="min-w-0 rounded-panel border border-line bg-surface">
          <div className="flex items-start justify-between gap-3 border-b border-line px-5 py-4">
            <div className="min-w-0">
              <h2 className="font-serif text-20 font-semibold text-ink">
                Institutional compliance
              </h2>
              <p className="mt-1 text-12 text-ink-500">
                Tile-coloured by compliance RAG.
              </p>
            </div>
            <div className="hidden shrink-0 text-right sm:block">
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
                  <TableHead className="text-right">Attention</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {needsAttention.map((inst) => {
                  const level = escalationByInstitution.get(inst.name);
                  const daysOverdue = level != null ? level * 7 : null;
                  const reason = reasonForStatus(inst.status);
                  return (
                    <TableRow key={inst.institution_id}>
                      <TableCell className="text-ink">
                        <div className="flex items-center gap-2">
                          <Building className="size-3.5 text-ink-500" />
                          <span className="text-13 font-medium">{inst.name}</span>
                        </div>
                        <p className="text-[10px] text-ink-500">
                          {inst.state} · {inst.region}
                        </p>
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex justify-end">
                          <StatusPill
                            status={COMPLIANCE_TONES[inst.status] ?? "neutral"}
                            className="whitespace-nowrap"
                          >
                            {reason}
                          </StatusPill>
                        </div>
                        <p className="mt-1 whitespace-nowrap text-[10px] text-ink-700">
                          <span className="font-medium">APH 7.13</span>
                          {daysOverdue != null ? (
                            <>
                              {" · "}
                              <span className="font-semibold text-breach-strong">
                                {daysOverdue} days overdue
                              </span>
                            </>
                          ) : null}
                        </p>
                        {level != null && (
                          <p className="text-[10px] leading-tight text-ink-500">
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
      <section className="grid grid-cols-1 gap-6 md:grid-cols-2 xl:grid-cols-3">
        {/* Funnel */}
        <section className="min-w-0 rounded-panel border border-line bg-surface">
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
              <div
                role="img"
                aria-label={`Funnel, applications by stage: ${
                  (dashboard?.funnel ?? [])
                    .map((entry) => `${entry.stage} ${entry.count}`)
                    .join(", ") || "no data"
                }`}
              >
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={dashboard?.funnel ?? []} layout="vertical">
                    <XAxis type="number" dataKey="count" hide domain={[0, "dataMax + 2"]} />
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
                    <Bar dataKey="count" fill="var(--saffron)" radius={[0, 4, 4, 0]} isAnimationActive={false}>
                      <LabelList
                        dataKey="count"
                        position="right"
                        className="fill-ink-700"
                        fontSize={11}
                        fontWeight={600}
                      />
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <div className="mt-3 flex justify-end text-[10px] text-ink-500">
                Bar length = applications at that stage
              </div>
            </div>
          )}
        </section>

        {/* Top violation codes */}
        <section className="min-w-0 rounded-panel border border-line bg-surface">
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
              <div
                role="img"
                aria-label={`Top violation codes, penal actions: ${
                  (dashboard?.top_violation_codes ?? [])
                    .slice(0, 6)
                    .map((entry) => `APH 7.4(${entry.code}) ${entry.count}`)
                    .join(", ") || "no data"
                }`}
              >
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart
                    data={(dashboard?.top_violation_codes ?? []).slice(0, 6)}
                    layout="vertical"
                  >
                    <XAxis type="number" dataKey="count" hide domain={[0, "dataMax + 2"]} />
                    <YAxis
                      type="category"
                      dataKey="code"
                      tick={{ fontSize: 11, fill: "var(--ink-500)" }}
                      tickFormatter={(value: string) => `APH 7.4(${value})`}
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
                    <Bar dataKey="count" fill="var(--breach)" radius={[0, 4, 4, 0]} isAnimationActive={false}>
                      <LabelList
                        dataKey="count"
                        position="right"
                        className="fill-ink-700"
                        fontSize={11}
                        fontWeight={600}
                      />
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <div className="mt-3 flex justify-end text-[10px] text-ink-500">
                Most frequent penal-action codes
              </div>
            </div>
          )}
        </section>

        {/* Compliance histogram */}
        <section className="min-w-0 rounded-panel border border-line bg-surface">
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
              <div
                role="img"
                aria-label={`Compliance histogram, institutions by latest score: ${histogramBins(
                  institutions,
                )
                  .map((entry) => `${entry.band} ${entry.count}`)
                  .join(", ")}`}
              >
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
                    <Bar dataKey="count" radius={[0, 4, 4, 0]} isAnimationActive={false}>
                      {histogramBins(institutions).map((entry) => (
                        <Cell key={entry.band} fill={BAND_FILLS[entry.band]} />
                      ))}
                      <LabelList
                        dataKey="count"
                        position="right"
                        className="fill-ink-700"
                        fontSize={11}
                        fontWeight={600}
                      />
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <div className="mt-3 flex justify-end text-[10px] text-ink-500">
                Latest compliance RAG band per institution
              </div>
            </div>
          )}
        </section>

        {/* Appeals + Deposits panels */}
        <section className="min-w-0 rounded-panel border border-line bg-surface">
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
              <div className="flex flex-wrap gap-x-3 gap-y-1 text-11 text-ink-700">
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

        <section className="min-w-0 rounded-panel border border-line bg-surface md:col-span-2 xl:col-span-2">
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
            <Table density="dense" className="table-fixed sm:table-auto">
              <TableHeader>
                <TableRow>
                  <TableHead>Institution</TableHead>
                  <TableHead className="w-[92px] text-right sm:w-auto">Status</TableHead>
                  <TableHead className="w-[78px] text-right sm:w-auto">Due</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(dashboard?.security_deposits_pending ?? []).map((d) => (
                  <TableRow key={d.application_id}>
                    <TableCell className="text-ink">
                      <div className="flex min-w-0 items-center gap-2">
                        <IndianRupee className="size-3.5 shrink-0 text-ink-500" />
                        <span className="min-w-0 break-words text-13 font-medium">
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
                      <span className="block text-12 font-medium leading-tight text-ink sm:text-13">
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
    { band: "RED", count: red, order: 0 },
    { band: "AMBER", count: amber, order: 1 },
    { band: "GREEN", count: green, order: 2 },
  ].sort((a, b) => a.order - b.order);
}
