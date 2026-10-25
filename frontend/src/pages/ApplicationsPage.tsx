import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { RefreshCw, Plus, X } from "lucide-react";
import { Link, useSearchParams } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import ApplicationStatusBadge from "../components/ApplicationStatusBadge";
import EscalationBadge from "../components/EscalationBadge";
import PageHeader from "../components/PageHeader";
import {
  Button,
  EmptyState,
  Skeleton,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../components/ui";
import { ApiError, getApplications, type ApplicationRecord } from "../lib/api";
import { formatDate, humanizeEnum, shortId } from "../lib/format";
import {
  ROLE_SCOPE_DESCRIPTIONS,
  applicationsLabelFor,
} from "../lib/roles";

const PAGE_SIZE = 10;

function applicationHref(application: ApplicationRecord): string {
  return application.status === "DRAFT"
    ? `/applications/${application.id}/edit`
    : `/applications/${application.id}`;
}

function AppReference({ application }: { application: ApplicationRecord }) {
  return (
    <>
      <span className="block truncate text-14 font-semibold text-ink">
        {application.reference ?? `APP-${shortId(application.id)}`}
      </span>
      <span className="mt-0.5 block font-mono text-12 text-ink-500">
        {shortId(application.id)}
      </span>
    </>
  );
}

function DueDate({ application }: { application: ApplicationRecord }) {
  if (!application.sla_due_at) {
    return <span className="text-13 text-ink-500">—</span>;
  }
  const due = new Date(application.sla_due_at);
  const closed = ["APPROVED", "CONDITIONALLY_APPROVED", "REJECTED"].includes(
    application.status,
  );
  const overdue =
    due.getTime() < Date.now() && !closed && !application.is_withdrawn;
  return (
    <span className={overdue ? "text-13 font-medium text-breach-strong" : "text-13 text-ink-700"}>
      {formatDate(application.sla_due_at)}
      {overdue ? <span className="ml-1.5 text-12">Past due</span> : null}
    </span>
  );
}

function MobileApplicationCard({ application }: { application: ApplicationRecord }) {
  return (
    <li>
      <Link
        to={applicationHref(application)}
        className="block px-4 py-4 transition-colors hover:bg-paper sm:px-5"
      >
        <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <AppReference application={application} />
          </div>
          <div className="flex flex-wrap items-center gap-2 self-start">
            <ApplicationStatusBadge
              status={application.status}
              isWithdrawn={application.is_withdrawn}
            />
            {application.is_escalated ? <EscalationBadge /> : null}
          </div>
        </div>
        <p className="mt-2 text-14 text-ink">{application.institution.name}</p>
        <p className="mt-0.5 text-12 text-ink-500">
          {application.institution.state} · {application.institution.region}
        </p>
        <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-3 border-t border-line pt-3 text-12">
          <div>
            <dt className="text-ink-500">Type</dt>
            <dd className="mt-0.5 text-ink">
              {humanizeEnum(application.application_type)} · {application.academic_year}
            </dd>
          </div>
          <div>
            <dt className="text-ink-500">Stage</dt>
            <dd className="mt-0.5 text-ink">
              {humanizeEnum(application.current_stage)}
            </dd>
          </div>
          <div>
            <dt className="text-ink-500">SLA due</dt>
            <dd className="mt-0.5">
              <DueDate application={application} />
            </dd>
          </div>
          <div>
            <dt className="text-ink-500">Submitted</dt>
            <dd className="mt-0.5 text-ink">{formatDate(application.submitted_at)}</dd>
          </div>
        </dl>
      </Link>
    </li>
  );
}

export default function ApplicationsPage() {
  const { user, token } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
  const [page, setPage] = useState(1);

  const overdue = searchParams.get("overdue") === "1";
  const institutionId = searchParams.get("institution_id") ?? undefined;
  const institutionName = searchParams.get("institution") ?? undefined;
  const isScrutiny = user?.role === "SCRUTINY_COMMITTEE_MEMBER";
  const assignedToMe = isScrutiny && searchParams.get("assigned") !== "all";
  const sortDue =
    overdue || (isScrutiny && searchParams.get("sort") !== "recent");

  useEffect(() => {
    setPage(1);
  }, [overdue, institutionId, assignedToMe, sortDue]);

  const applicationsQuery = useQuery({
    queryKey: [
      "applications",
      { page, overdue, institutionId, assignedToMe, sortDue },
    ],
    queryFn: () =>
      getApplications(token ?? "", {
        page,
        pageSize: PAGE_SIZE,
        overdue,
        institutionId,
        assignedToMe,
        sort: sortDue ? "due" : "recent",
      }),
    enabled: Boolean(token),
  });

  if (!user) {
    return null;
  }

  const baseTitle = applicationsLabelFor(user.role);
  const title = overdue
    ? "Overdue applications"
    : institutionName
      ? "Filtered applications"
      : isScrutiny && assignedToMe
        ? "My scrutiny queue"
        : baseTitle;
  const description = overdue
    ? "Cases whose SLA due date has passed and that still need a decision. Sorted by the earliest due date."
    : institutionName
      ? `${institutionName}. ${ROLE_SCOPE_DESCRIPTIONS[user.role]}`
      : isScrutiny
        ? assignedToMe
          ? "Applications assigned to you, with the earliest SLA due first."
          : "All applications in your region, with the earliest SLA due first."
        : ROLE_SCOPE_DESCRIPTIONS[user.role];

  const data = applicationsQuery.data;
  const items = data?.items ?? [];
  const firstRow = data && data.total > 0 ? (data.page - 1) * data.page_size + 1 : 0;
  const lastRow = data ? Math.min(data.page * data.page_size, data.total) : 0;
  const hasFilter =
    overdue || Boolean(institutionId) || (isScrutiny && !assignedToMe);

  const clearFilters = () => {
    setSearchParams({});
    setPage(1);
  };

  const setFilter = (key: string, value: string | null) => {
    const next = new URLSearchParams(searchParams);
    if (value === null) {
      next.delete(key);
    } else {
      next.set(key, value);
    }
    setSearchParams(next);
    setPage(1);
  };

  return (
    <>
      <PageHeader
        eyebrow="Approval cases"
        title={title}
        description={description}
        actions={
          <>
            {user.role === "INSTITUTION_ADMIN" ? (
              <Button asChild size="sm">
                <Link to="/applications/new">
                  <Plus aria-hidden="true" className="size-4" />
                  New application
                </Link>
              </Button>
            ) : null}
            {hasFilter ? (
              <Button variant="quiet" size="sm" onClick={clearFilters}>
                <X aria-hidden="true" className="size-4" />
                Clear filter
              </Button>
            ) : null}
            <Button
              variant="secondary"
              size="sm"
              onClick={() => void applicationsQuery.refetch()}
              disabled={applicationsQuery.isFetching}
            >
              <RefreshCw
                aria-hidden="true"
                className={applicationsQuery.isFetching ? "size-4 animate-spin" : "size-4"}
              />
              Refresh
            </Button>
          </>
        }
      />

      {overdue || institutionName || isScrutiny ? (
        <div className="mb-5 flex flex-wrap items-center gap-2 rounded-panel border border-line bg-surface px-4 py-3 text-13 text-ink-700">
          <span className="font-medium text-ink">
            {isScrutiny ? "Queue view" : "Filtered view"}
          </span>
          {isScrutiny ? (
            <>
              <span className="rounded-pill bg-info-soft px-2.5 py-1 text-12 text-info-strong">
                {assignedToMe ? "My assignments" : "Regional queue"}
              </span>
              <div className="flex items-center gap-1">
                <Button
                  variant={assignedToMe ? "secondary" : "quiet"}
                  size="sm"
                  onClick={() => setFilter("assigned", null)}
                >
                  My queue
                </Button>
                <Button
                  variant={assignedToMe ? "quiet" : "secondary"}
                  size="sm"
                  onClick={() => setFilter("assigned", "all")}
                >
                  Regional queue
                </Button>
              </div>
              <span className="mx-1 hidden h-5 w-px bg-line sm:block" aria-hidden="true" />
              <span className="rounded-pill bg-paper px-2.5 py-1 text-12 text-ink-700">
                {sortDue ? "Due first" : "Most recent"}
              </span>
              <div className="flex items-center gap-1">
                <Button
                  variant={sortDue ? "secondary" : "quiet"}
                  size="sm"
                  onClick={() => setFilter("sort", null)}
                >
                  Due first
                </Button>
                <Button
                  variant={sortDue ? "quiet" : "secondary"}
                  size="sm"
                  onClick={() => setFilter("sort", "recent")}
                >
                  Recent
                </Button>
              </div>
            </>
          ) : null}
          {overdue ? (
            <span className="rounded-pill bg-watch-soft px-2.5 py-1 text-12 text-watch-strong">
              Overdue only
            </span>
          ) : null}
          {institutionName ? (
            <span className="max-w-full truncate rounded-pill bg-info-soft px-2.5 py-1 text-12 text-info-strong">
              {institutionName}
            </span>
          ) : null}
          <button
            type="button"
            onClick={clearFilters}
            className="ml-auto text-12 font-medium text-ink-700 underline-offset-4 hover:text-ink hover:underline"
          >
            Reset view
          </button>
        </div>
      ) : null}

      <section aria-label="Applications" className="min-w-0">
        {applicationsQuery.isPending ? (
          <div
            className="rounded-panel border border-line bg-surface p-4"
            role="status"
            aria-label="Loading applications"
          >
            <div className="space-y-3">
              {[0, 1, 2, 3, 4].map((item) => (
                <Skeleton key={item} className="h-12 w-full" />
              ))}
            </div>
            <span className="sr-only">Loading applications</span>
          </div>
        ) : applicationsQuery.isError ? (
          <div className="rounded-panel border border-line bg-surface p-6">
            <p className="rounded-input border border-breach bg-breach-soft p-4 text-14 text-breach-strong">
              {applicationsQuery.error instanceof ApiError
                ? applicationsQuery.error.message
                : "Applications could not be loaded. Check the API connection and try again."}
            </p>
            <Button
              variant="secondary"
              size="sm"
              className="mt-3"
              onClick={() => void applicationsQuery.refetch()}
            >
              Retry
            </Button>
          </div>
        ) : items.length === 0 ? (
          <EmptyState
            message={
              hasFilter
                ? "No applications match this filter. Clear it to see the records available to your role."
                : "No approval cases currently match your role and assignment scope."
            }
            action={
              hasFilter ? (
                <Button variant="secondary" size="sm" onClick={clearFilters}>
                  Clear filter
                </Button>
              ) : user.role === "INSTITUTION_ADMIN" ? (
                <Button asChild size="sm">
                  <Link to="/applications/new">
                    <Plus aria-hidden="true" className="size-4" />
                    Start an application
                  </Link>
                </Button>
              ) : (
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => void applicationsQuery.refetch()}
                >
                  Refresh
                </Button>
              )
            }
          />
        ) : (
          <>
            <div className="hidden min-w-0 min-[1400px]:block">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Reference</TableHead>
                    <TableHead>Institution</TableHead>
                    <TableHead>Type / year</TableHead>
                    <TableHead>Stage</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>SLA due</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {items.map((application) => (
                    <TableRow key={application.id}>
                      <TableCell className="whitespace-nowrap">
                        <Link
                          to={applicationHref(application)}
                          className="rounded-input underline-offset-4 hover:underline"
                        >
                          <AppReference application={application} />
                        </Link>
                      </TableCell>
                      <TableCell className="min-w-48">
                        <span className="block text-14 text-ink">
                          {application.institution.name}
                        </span>
                        <span className="mt-0.5 block text-12 text-ink-500">
                          {application.institution.state} · {application.institution.region}
                        </span>
                      </TableCell>
                      <TableCell className="whitespace-nowrap text-13 text-ink-700">
                        <span className="block">
                          {humanizeEnum(application.application_type)}
                        </span>
                        <span className="mt-0.5 block text-12 text-ink-500">
                          {application.academic_year}
                        </span>
                      </TableCell>
                      <TableCell className="whitespace-nowrap text-13 text-ink-700">
                        {humanizeEnum(application.current_stage)}
                      </TableCell>
                      <TableCell className="whitespace-nowrap">
                        <div className="flex flex-wrap items-center gap-2">
                          <ApplicationStatusBadge
                            status={application.status}
                            isWithdrawn={application.is_withdrawn}
                          />
                          {application.is_escalated ? <EscalationBadge /> : null}
                        </div>
                      </TableCell>
                      <TableCell className="whitespace-nowrap">
                        <DueDate application={application} />
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>

            <ul className="divide-y divide-line rounded-panel border border-line bg-surface min-[1400px]:hidden">
              {items.map((application) => (
                <MobileApplicationCard key={application.id} application={application} />
              ))}
            </ul>

            <div className="flex flex-col gap-3 border-t border-line px-1 py-4 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-12 text-ink-500">
                Showing {firstRow}–{lastRow} of {data?.total ?? 0} applications
              </p>
              <div className="flex items-center gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => setPage((current) => Math.max(1, current - 1))}
                  disabled={page <= 1}
                >
                  Previous
                </Button>
                <span className="min-w-24 text-center text-12 text-ink-700">
                  Page {data?.page ?? page} of {data?.pages ?? 0}
                </span>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => setPage((current) => current + 1)}
                  disabled={!data || page >= data.pages}
                >
                  Next
                </Button>
              </div>
            </div>
          </>
        )}
      </section>
    </>
  );
}
