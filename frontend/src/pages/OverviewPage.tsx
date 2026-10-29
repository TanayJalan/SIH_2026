import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Plus } from "lucide-react";

import { useAuth } from "../auth/AuthContext";
import ApplicationStatusBadge from "../components/ApplicationStatusBadge";
import ApplicationStatusTracker from "../components/application/ApplicationStatusTracker";
import EscalationBadge from "../components/EscalationBadge";
import PageHeader from "../components/PageHeader";
import UpcomingDeadlinesCard from "../components/dashboard/UpcomingDeadlinesCard";
import { Button, EmptyState, Skeleton, Stat } from "../components/ui";
import { getApplications, type UserProfile } from "../lib/api";
import { formatDate, humanizeEnum, shortId } from "../lib/format";
import {
  AUDIT_LOG_ROLES,
  ROLE_LABELS,
  ROLE_SCOPE_DESCRIPTIONS,
  applicationsLabelFor,
} from "../lib/roles";

function accessScope(user: UserProfile): { value: string; detail: string } {
  switch (user.role) {
    case "SUPER_ADMIN":
      return { value: "All institutions", detail: "System-wide access" };
    case "REGIONAL_OFFICER":
      return { value: user.region ?? "No region", detail: "Regional oversight" };
    case "REGULATION_BUREAU_OFFICER":
      return { value: "All regions", detail: "Scrutiny and process oversight" };
    case "SCRUTINY_COMMITTEE_MEMBER":
      return {
        value: user.region ?? user.institution?.name ?? "Assigned cases",
        detail: "Assignment and regional scope",
      };
    case "EVC_MEMBER":
      return {
        value: user.region ?? user.institution?.name ?? "Assigned cases",
        detail: "Applications with your inspections",
      };
    case "SHC_MEMBER":
      return { value: "Hearing cases", detail: "Cases referred to the SHC" };
    case "SAC_MEMBER":
      return { value: "Appeal cases", detail: "Appeals referred to the SAC" };
    case "EXECUTIVE_COMMITTEE_MEMBER":
      return { value: "Committee cases", detail: "Cases referred to the EC" };
    case "COMPLAINT_SCRUTINY_MEMBER":
      return { value: "Complaint cases", detail: "Complaints referred to the SCSC" };
    case "INSTITUTION_ADMIN":
      return {
        value: user.institution?.name ?? "No institution",
        detail: user.institution?.state ?? "Own institution",
      };
  }
}

export default function OverviewPage() {
  const { user, token } = useAuth();
  const applicationsQuery = useQuery({
    queryKey: ["applications", "overview"],
    queryFn: () => getApplications(token ?? "", { page: 1, pageSize: 5 }),
    enabled: Boolean(token),
  });

  if (!user) {
    return null;
  }

  const applications = applicationsQuery.data?.items ?? [];
  const scope = accessScope(user);
  const canViewAuditLogs = AUDIT_LOG_ROLES.includes(user.role);
  const applicationsLabel = applicationsLabelFor(user.role);

  return (
    <>
      <PageHeader
        eyebrow="Dashboard"
        title="Welcome back"
        description={ROLE_SCOPE_DESCRIPTIONS[user.role]}
        actions={
          user.role === "INSTITUTION_ADMIN" ? (
            <div className="flex flex-wrap items-center gap-2">
              <Button asChild variant="secondary">
                <Link to="/applications">{applicationsLabel}</Link>
              </Button>
              <Button asChild>
                <Link to="/applications/new">
                  <Plus aria-hidden="true" className="size-4" />
                  Start application
                </Link>
              </Button>
            </div>
          ) : (
            <Button asChild>
              <Link to="/applications">{applicationsLabel}</Link>
            </Button>
          )
        }
      />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
        <Stat
          caption="Applications in view"
          figure={applicationsQuery.data ? String(applicationsQuery.data.total) : "—"}
          delta="Results permitted by your role and scope"
        />
        <Stat
          caption="Signed-in role"
          figure={ROLE_LABELS[user.role]}
          delta={
            user.role === "SUPER_ADMIN"
              ? "All regions"
              : user.region
                ? `Region: ${user.region}`
                : "No region assigned"
          }
        />
        <Stat
          caption="Access scope"
          figure={scope.value}
          delta={scope.detail}
        />
      </div>

      <div className="mt-6 grid grid-cols-1 items-start gap-6 xl:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
        <section className="min-w-0 rounded-panel border border-line bg-surface">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-5 py-4">
            <div>
              <h2 className="font-serif text-20 font-semibold text-ink">Recent applications</h2>
              <p className="mt-1 text-12 text-ink-500">
                Latest records your account is permitted to see
              </p>
            </div>
            <Link
              to="/applications"
              className="inline-flex items-center gap-1.5 whitespace-nowrap text-12 font-medium text-ink-700 underline-offset-4 hover:text-ink hover:underline"
            >
              View all
              <ArrowRight aria-hidden="true" className="size-3.5" />
            </Link>
          </div>

          {applicationsQuery.isPending ? (
            <div className="space-y-3 p-5" role="status">
              {[0, 1, 2].map((item) => (
                <Skeleton key={item} className="h-12 w-full" />
              ))}
              <span className="sr-only">Loading applications</span>
            </div>
          ) : applicationsQuery.isError ? (
            <div className="p-5">
              <p className="rounded-input border border-breach bg-breach-soft p-3 text-13 text-breach-strong">
                Applications could not be loaded. Check the API connection and try again.
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
          ) : applications.length === 0 ? (
            <div className="p-5">
              <EmptyState
                message="No records currently match your role and assignment scope."
                action={
                  user.role === "INSTITUTION_ADMIN" ? (
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
            </div>
          ) : (
            <ul className="divide-y divide-line">
              {applications.map((application) => (
                <li key={application.id}>
                  <Link
                    to={
                      application.status === "DRAFT"
                        ? `/applications/${application.id}/edit`
                        : `/applications/${application.id}`
                    }
                    className="flex flex-col gap-3 px-5 py-4 transition-colors hover:bg-paper sm:flex-row sm:items-center sm:justify-between"
                  >
                    <div className="min-w-0">
                      <p className="truncate text-14 font-semibold text-ink">
                        {application.reference ?? `Application ${shortId(application.id)}`}
                      </p>
                      <p className="mt-1 truncate text-12 text-ink-500">
                        {application.institution.name} ·{" "}
                        {humanizeEnum(application.application_type)} · {application.academic_year}
                      </p>
                      <ApplicationStatusTracker
                        className="mt-3 max-w-xl"
                        status={application.status}
                        currentStage={application.current_stage}
                        portalApplicationNo={application.portal_application_no}
                      />
                    </div>
                    <div className="flex shrink-0 items-center gap-3">
                      <ApplicationStatusBadge status={application.status} />
                      {application.is_escalated ? <EscalationBadge /> : null}
                      <span className="text-12 text-ink-500">
                        {formatDate(application.submitted_at)}
                      </span>
                    </div>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>

        <aside className="min-w-0 space-y-6">
          {user.role === "INSTITUTION_ADMIN" ? (
            <UpcomingDeadlinesCard token={token ?? ""} />
          ) : null}
          <section className="rounded-panel border border-line bg-surface p-5">
            <p className="text-12 font-semibold uppercase tracking-[0.12em] text-ink-500">
              Role-based access
            </p>
            <h2 className="mt-2 font-serif text-20 font-semibold text-ink">
              {ROLE_LABELS[user.role]}
            </h2>
            <p className="mt-2 text-13 leading-5 text-ink-700">
              {ROLE_SCOPE_DESCRIPTIONS[user.role]}
            </p>
            <dl className="mt-4 space-y-3 border-t border-line pt-4 text-12">
              <div className="flex items-center justify-between gap-3">
                <dt className="text-ink-500">Account</dt>
                <dd className="truncate font-medium text-ink">{user.email}</dd>
              </div>
              <div className="flex items-center justify-between gap-3">
                <dt className="text-ink-500">Status</dt>
                <dd className="font-medium text-ok-strong">
                  {user.is_active ? "Active" : "Inactive"}
                </dd>
              </div>
              {user.institution ? (
                <div className="flex items-center justify-between gap-3">
                  <dt className="text-ink-500">Institution</dt>
                  <dd className="truncate text-right font-medium text-ink">
                    {user.institution.name}
                  </dd>
                </div>
              ) : null}
            </dl>
          </section>

          {canViewAuditLogs ? (
            <section className="rounded-panel border border-line bg-ink p-5 text-surface">
              <p className="text-12 font-semibold uppercase tracking-[0.12em] text-ink-100">
                Oversight
              </p>
              <h2 className="mt-2 font-serif text-20 font-semibold">Audit trail</h2>
              <p className="mt-2 text-13 leading-5 text-ink-100">
                Review authentication and write-action records within your permitted scope.
              </p>
              <Button asChild variant="secondary" size="sm" className="mt-4 border-surface/30 bg-transparent text-surface hover:bg-surface/10">
                <Link to="/audit-logs">Open audit logs</Link>
              </Button>
            </section>
          ) : (
            <section className="rounded-panel border border-watch bg-watch-soft p-5">
              <p className="text-12 font-semibold uppercase tracking-[0.12em] text-watch-strong">
                Session
              </p>
              <p className="mt-2 text-13 leading-5 text-watch-strong">
                Your access token is valid for eight hours. Sign out when you finish working on a
                shared device.
              </p>
            </section>
          )}
        </aside>
      </div>
    </>
  );
}
