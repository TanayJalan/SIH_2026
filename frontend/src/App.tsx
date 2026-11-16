import { Suspense, lazy } from "react";
import { Route, Routes } from "react-router-dom";

import AppLayout from "./components/AppLayout";
import FullPageLoader from "./components/FullPageLoader";
import ProtectedRoute from "./components/ProtectedRoute";
import RequireRoles from "./components/RequireRoles";
import { AUDIT_LOG_ROLES } from "./lib/roles";

/*
 * Routes are split so the initial bundle carries only the shell and the page
 * being opened. Chart-heavy dashboards and the case file load on demand.
 */
const AlertRulesPage = lazy(() => import("./pages/AlertRulesPage"));
const AlertsPage = lazy(() => import("./pages/AlertsPage"));
const ApplicationDetailPage = lazy(() => import("./pages/ApplicationDetailPage"));
const ApplicationWizardPage = lazy(() => import("./pages/ApplicationWizardPage"));
const ApplicationsPage = lazy(() => import("./pages/ApplicationsPage"));
const AuditLogsPage = lazy(() => import("./pages/AuditLogsPage"));
const ComplianceAdminPage = lazy(() => import("./pages/ComplianceAdminPage"));
const DashboardPage = lazy(() => import("./pages/DashboardPage"));
const DesignSystemPage = lazy(() => import("./pages/DesignSystemPage"));
const EligibilityAdvisorPage = lazy(() => import("./pages/EligibilityAdvisorPage"));
const LoginPage = lazy(() => import("./pages/LoginPage"));
const NewApplicationPage = lazy(() => import("./pages/NewApplicationPage"));
const NotFoundPage = lazy(() => import("./pages/NotFoundPage"));
const OverviewPage = lazy(() => import("./pages/OverviewPage"));
const ProfilePage = lazy(() => import("./pages/ProfilePage"));

export default function App() {
  return (
    <Suspense fallback={<FullPageLoader label="Loading page" />}>
      <Routes>
        <Route path="/dev/ui" element={<DesignSystemPage />} />
        <Route path="/login" element={<LoginPage />} />

        <Route element={<ProtectedRoute />}>
          <Route element={<AppLayout />}>
            <Route index element={<OverviewPage />} />
            <Route path="dashboard" element={<DashboardPage />} />
            <Route path="applications" element={<ApplicationsPage />} />
            <Route
              path="applications/new"
              element={
                <RequireRoles roles={["INSTITUTION_ADMIN"]}>
                  <NewApplicationPage />
                </RequireRoles>
              }
            />
            <Route
              path="applications/:applicationId/edit"
              element={
                <RequireRoles roles={["INSTITUTION_ADMIN"]}>
                  <ApplicationWizardPage />
                </RequireRoles>
              }
            />
            <Route path="applications/:applicationId" element={<ApplicationDetailPage />} />
            <Route
              path="compliance"
              element={
                <RequireRoles roles={["SUPER_ADMIN", "REGIONAL_OFFICER"]}>
                  <ComplianceAdminPage />
                </RequireRoles>
              }
            />
            <Route
              path="eligibility"
              element={
                <RequireRoles roles={["INSTITUTION_ADMIN"]}>
                  <EligibilityAdvisorPage />
                </RequireRoles>
              }
            />
            <Route path="alerts" element={<AlertsPage />} />
            <Route
              path="alert-rules"
              element={
                <RequireRoles roles={["SUPER_ADMIN"]}>
                  <AlertRulesPage />
                </RequireRoles>
              }
            />
            <Route
              path="audit-logs"
              element={
                <RequireRoles roles={AUDIT_LOG_ROLES}>
                  <AuditLogsPage />
                </RequireRoles>
              }
            />
            <Route path="profile" element={<ProfilePage />} />
            <Route path="*" element={<NotFoundPage />} />
          </Route>
        </Route>

        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </Suspense>
  );
}
