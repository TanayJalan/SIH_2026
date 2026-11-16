import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  CircleHelp,
  Info,
  XCircle,
  type LucideIcon,
} from "lucide-react";
import { Link } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import PageHeader from "../components/PageHeader";
import {
  Button,
  ErrorState,
  Skeleton,
  StatusPill,
  type StatusPillTone,
} from "../components/ui";
import {
  getEligibilityAdvisor,
  type EligibilityRoute,
  type EligibilityStatus,
} from "../lib/api";
import { formatDate } from "../lib/format";
import { cn } from "../lib/utils";

interface StatusMeta {
  tone: StatusPillTone;
  label: string;
  icon: LucideIcon;
  accent: string;
  iconClass: string;
}

/** Colour is never the only signal: every verdict also carries a word and an icon. */
const STATUS_META: Record<EligibilityStatus, StatusMeta> = {
  PASS: {
    tone: "compliant",
    label: "Meets the test",
    icon: CheckCircle2,
    accent: "border-ok",
    iconClass: "text-ok-strong",
  },
  UNKNOWN: {
    tone: "watch",
    label: "Needs evidence",
    icon: CircleHelp,
    accent: "border-watch",
    iconClass: "text-watch-strong",
  },
  FAIL: {
    tone: "breach",
    label: "Does not meet the test",
    icon: XCircle,
    accent: "border-breach",
    iconClass: "text-breach-strong",
  },
};

const ROUTE_BLURBS: Record<string, string> = {
  EXTENDED_EOA: "Three years' approval in one application",
  FN_OCI: "Supernumerary seats for foreign nationals and OCI students",
  OFF_CAMPUS: "One campus outside the main premises",
  WORKING_PROFESSIONAL: "An extra division for employed students",
  TFW: "Tuition Fee Waiver seats, by course",
};

function SummaryTile({
  status,
  count,
}: {
  status: EligibilityStatus;
  count: number;
}) {
  const meta = STATUS_META[status];
  const Icon = meta.icon;
  return (
    <div className="rounded-panel border border-line bg-surface p-4">
      <p className="flex items-center gap-1.5 text-12 font-medium text-ink-500">
        <Icon aria-hidden="true" className={cn("size-3.5", meta.iconClass)} />
        {meta.label}
      </p>
      <p className="mt-1 font-serif text-28 font-semibold tabular-nums text-ink">
        {count}
      </p>
    </div>
  );
}

function CriterionRow({
  label,
  clause,
  status,
  observed,
  required,
  detail,
  suggestion,
}: {
  label: string;
  clause: string;
  status: EligibilityStatus;
  observed: string | null;
  required: string | null;
  detail: string;
  suggestion: string | null;
}) {
  const meta = STATUS_META[status];
  const Icon = meta.icon;
  return (
    <li className="border-t border-line py-4 first:border-t-0 first:pt-0">
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
        <div className="min-w-0 flex-1">
          <p className="flex items-start gap-2 text-14 font-medium text-ink">
            <Icon
              aria-hidden="true"
              className={cn("mt-0.5 size-4 shrink-0", meta.iconClass)}
            />
            <span>{label}</span>
          </p>
          <p className="mt-1 pl-6 text-13 leading-5 text-ink-700">{detail}</p>
        </div>
        <StatusPill status={meta.tone} className="shrink-0">
          {meta.label}
        </StatusPill>
      </div>
      <dl className="mt-2 flex flex-wrap gap-x-6 gap-y-1 pl-6 text-12 text-ink-500">
        <div className="flex gap-1">
          <dt>On record:</dt>
          <dd className="font-medium text-ink-700">{observed ?? "Not recorded"}</dd>
        </div>
        <div className="flex gap-1">
          <dt>Required:</dt>
          <dd className="font-medium text-ink-700">{required ?? "—"}</dd>
        </div>
        <div className="flex gap-1">
          <dt>Clause:</dt>
          <dd className="font-medium text-ink-700">{clause}</dd>
        </div>
      </dl>
      {suggestion ? (
        <p className="mt-2 ml-6 rounded-input border border-watch bg-watch-soft px-3 py-2 text-12 leading-5 text-watch-strong">
          <span className="font-semibold">What would it take: </span>
          {suggestion}
        </p>
      ) : null}
    </li>
  );
}

function RouteCard({ route }: { route: EligibilityRoute }) {
  const meta = STATUS_META[route.status];
  const Icon = meta.icon;
  const start = route.application_type
    ? `/applications/new?type=${encodeURIComponent(route.application_type)}`
    : null;

  return (
    <section
      aria-labelledby={`route-${route.code}`}
      className={cn(
        "rounded-panel border border-line border-l-4 bg-surface p-5",
        meta.accent,
      )}
    >
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-2">
        <div className="min-w-0">
          <p className="text-12 font-medium text-ink-500">
            {ROUTE_BLURBS[route.code] ?? route.apH_clause} · {route.apH_clause}
          </p>
          <h2
            id={`route-${route.code}`}
            className="mt-1 flex items-center gap-2 text-16 font-semibold text-ink"
          >
            <Icon
              aria-hidden="true"
              className={cn("size-4 shrink-0", meta.iconClass)}
            />
            {route.label}
          </h2>
        </div>
        <StatusPill status={meta.tone}>{meta.label}</StatusPill>
      </div>

      <p className="mt-3 text-14 leading-5 text-ink-700">{route.summary}</p>

      <ul className="mt-4">
        {route.criteria.map((criterion) => (
          <CriterionRow
            key={criterion.code}
            label={criterion.label}
            clause={criterion.apH_clause}
            status={criterion.status}
            observed={criterion.observed}
            required={criterion.required}
            detail={criterion.detail}
            suggestion={criterion.suggestion}
          />
        ))}
      </ul>

      {route.notes.length > 0 ? (
        <ul className="mt-4 space-y-1.5 border-t border-line pt-3">
          {route.notes.map((note) => (
            <li key={note} className="flex gap-2 text-12 leading-5 text-ink-500">
              <Info aria-hidden="true" className="mt-0.5 size-3.5 shrink-0" />
              <span>{note}</span>
            </li>
          ))}
        </ul>
      ) : null}

      <div className="mt-4 flex flex-wrap items-center gap-3">
        {start ? (
          <Button asChild size="sm" variant={route.status === "PASS" ? "primary" : "secondary"}>
            <Link to={start}>
              Start this application
              <ArrowRight aria-hidden="true" className="size-4" />
            </Link>
          </Button>
        ) : (
          <p className="text-12 text-ink-500">
            No separate application is needed for this scheme.
          </p>
        )}
        {start && route.status !== "PASS" ? (
          <p className="text-12 text-ink-500">
            Scrutiny will test this route against the same clauses.
          </p>
        ) : null}
      </div>
    </section>
  );
}

export default function EligibilityAdvisorPage() {
  const { token } = useAuth();
  const advisorQuery = useQuery({
    queryKey: ["eligibility-advisor"],
    queryFn: () => getEligibilityAdvisor(token ?? ""),
    enabled: Boolean(token),
  });

  const advisor = advisorQuery.data;
  const counts: Record<EligibilityStatus, number> = {
    PASS: advisor?.routes.filter((route) => route.status === "PASS").length ?? 0,
    UNKNOWN: advisor?.routes.filter((route) => route.status === "UNKNOWN").length ?? 0,
    FAIL: advisor?.routes.filter((route) => route.status === "FAIL").length ?? 0,
  };

  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader
        eyebrow="Eligibility"
        title="Eligibility advisor"
        description="Which approval route your institution can take, the APH clause behind every test, and what would change the answer. Green means the test is met, amber means the evidence is missing, red means it is not met yet."
        actions={
          <Button asChild variant="secondary">
            <Link to="/applications/new">
              New application
              <ArrowRight aria-hidden="true" className="size-4" />
            </Link>
          </Button>
        }
      />

      {advisorQuery.isError ? (
        <ErrorState
          error={advisorQuery.error}
          message="The eligibility advisor could not be loaded."
          onRetry={() => advisorQuery.refetch()}
        />
      ) : advisorQuery.isPending ? (
        <div className="space-y-4" aria-busy="true">
          <div className="grid gap-3 sm:grid-cols-3">
            {[0, 1, 2].map((item) => (
              <Skeleton key={item} className="h-24 w-full" />
            ))}
          </div>
          {[0, 1, 2].map((item) => (
            <Skeleton key={item} className="h-64 w-full" />
          ))}
          <span className="sr-only">Loading the eligibility advisor</span>
        </div>
      ) : advisor ? (
        <div className="space-y-5">
          <div className="grid gap-3 sm:grid-cols-3">
            <SummaryTile status="PASS" count={counts.PASS} />
            <SummaryTile status="UNKNOWN" count={counts.UNKNOWN} />
            <SummaryTile status="FAIL" count={counts.FAIL} />
          </div>

          <p className="rounded-panel border border-line bg-surface px-4 py-3 text-12 leading-5 text-ink-500">
            <span className="font-medium text-ink-700">{advisor.institution_name}</span>{" "}
            · evidence checked against the simulated portal date of{" "}
            {formatDate(advisor.as_of)}. Thresholds come from the AICTE Approval
            Process Handbook clauses cited on each row; the evidence on file for the
            demo institutions is fictional.
          </p>

          {advisor.routes.length === 0 ? (
            <p className="flex items-center gap-2 rounded-panel border border-dashed border-line bg-paper px-4 py-8 text-14 text-ink-700">
              <AlertTriangle aria-hidden="true" className="size-4" />
              The advisor returned no routes. Check the institution record.
            </p>
          ) : (
            advisor.routes.map((route) => <RouteCard key={route.code} route={route} />)
          )}
        </div>
      ) : null}
    </div>
  );
}
