import { Navigate } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import RegionalDashboard from "../components/dashboard/RegionalDashboard";
import OfficerDashboard from "../components/dashboard/OfficerDashboard";
import InstitutionDashboard from "../components/dashboard/InstitutionDashboard";
import { Role } from "../lib/api";
import { ROLE_LABELS } from "../lib/roles";
import PageHeader from "../components/PageHeader";

const DASHBOARD_BY_ROLE: Record<Role, React.ElementType> = {
  REGIONAL_OFFICER: RegionalDashboard,
  SUPER_ADMIN: RegionalDashboard,
  REGULATION_BUREAU_OFFICER: OfficerDashboard,
  SCRUTINY_COMMITTEE_MEMBER: OfficerDashboard,
  EVC_MEMBER: OfficerDashboard,
  SHC_MEMBER: OfficerDashboard,
  SAC_MEMBER: OfficerDashboard,
  EXECUTIVE_COMMITTEE_MEMBER: OfficerDashboard,
  COMPLAINT_SCRUTINY_MEMBER: OfficerDashboard,
  INSTITUTION_ADMIN: InstitutionDashboard,
};

export default function DashboardPage() {
  const { user } = useAuth();

  if (!user) {
    return null;
  }

  const Dashboard = DASHBOARD_BY_ROLE[user.role];
  if (!Dashboard) {
    return <Navigate to="/" replace />;
  }

  return (
    <>
      <PageHeader
        eyebrow="Dashboard"
        title={ROLE_LABELS[user.role]}
        description="Role-specific view of your applications, compliance position and statutory deadlines."
      />
      <Dashboard />
    </>
  );
}
