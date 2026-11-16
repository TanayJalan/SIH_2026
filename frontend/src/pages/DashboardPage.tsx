import { Suspense, lazy, type ComponentType } from "react";
import { Link } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import PageLoader from "../components/PageLoader";
import { Button } from "../components/ui";
import { Role } from "../lib/api";
import { ROLE_LABELS } from "../lib/roles";
import PageHeader from "../components/PageHeader";

/*
 * Dashboards are split per role so the charting library loads only for the
 * roles that actually render charts.
 */
const RegionalDashboard = lazy(() => import("../components/dashboard/RegionalDashboard"));
const OfficerDashboard = lazy(() => import("../components/dashboard/OfficerDashboard"));
const InstitutionDashboard = lazy(
  () => import("../components/dashboard/InstitutionDashboard"),
);

const DASHBOARD_BY_ROLE: Partial<Record<Role, ComponentType>> = {
  REGIONAL_OFFICER: RegionalDashboard,
  SUPER_ADMIN: RegionalDashboard,
  REGULATION_BUREAU_OFFICER: OfficerDashboard,
  SCRUTINY_COMMITTEE_MEMBER: OfficerDashboard,
  INSTITUTION_ADMIN: InstitutionDashboard,
};

export default function DashboardPage() {
  const { user } = useAuth();

  if (!user) {
    return null;
  }

  const Dashboard = DASHBOARD_BY_ROLE[user.role];
  if (!Dashboard) {
    return (
      <>
        <PageHeader
          eyebrow="Dashboard"
          title={ROLE_LABELS[user.role]}
          description="Role-specific view of your applications, compliance position and statutory deadlines."
        />
        <section className="mx-auto max-w-2xl rounded-panel border border-line bg-surface p-8 text-center">
          <p className="text-12 font-semibold uppercase tracking-[0.18em] text-ink-500">
            No reporting dashboard
          </p>
          <h2 className="mt-3 font-serif text-24 font-semibold text-ink">
            Your committee works from the case queue
          </h2>
          <p className="mt-3 text-14 leading-5 text-ink-700">
            {ROLE_LABELS[user.role]} does not have a consolidated reporting dashboard. Open the
            queue to see the cases referred to your committee, or review recent alerts.
          </p>
          <div className="mt-6 flex flex-wrap justify-center gap-2">
            <Button asChild>
              <Link to="/applications">Open case queue</Link>
            </Button>
            <Button asChild variant="secondary">
              <Link to="/alerts">Review alerts</Link>
            </Button>
          </div>
        </section>
      </>
    );
  }

  return (
    <Suspense fallback={<PageLoader label="Loading dashboard" />}>
      <Dashboard />
    </Suspense>
  );
}
