import { Route, Routes } from "react-router-dom";

import AppLayout from "./components/AppLayout";
import ProtectedRoute from "./components/ProtectedRoute";
import RequireRoles from "./components/RequireRoles";
import { AUDIT_LOG_ROLES } from "./lib/roles";
import AlertRulesPage from "./pages/AlertRulesPage";
import AlertsPage from "./pages/AlertsPage";
import ApplicationDetailPage from "./pages/ApplicationDetailPage";
import ApplicationWizardPage from "./pages/ApplicationWizardPage";
import ApplicationsPage from "./pages/ApplicationsPage";
import AuditLogsPage from "./pages/AuditLogsPage";
import ComplianceAdminPage from "./pages/ComplianceAdminPage";
import DesignSystemPage from "./pages/DesignSystemPage";
import LoginPage from "./pages/LoginPage";
import NewApplicationPage from "./pages/NewApplicationPage";
import NotFoundPage from "./pages/NotFoundPage";
import OverviewPage from "./pages/OverviewPage";
import ProfilePage from "./pages/ProfilePage";

export default function App() {
  return (
    <Routes>
      <Route path="/dev/ui" element={<DesignSystemPage />} />
      <Route path="/login" element={<LoginPage />} />

      <Route element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
          <Route index element={<OverviewPage />} />
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
              <RequireRoles roles={["SUPER_ADMIN", "REGIONAL_HEAD"]}>
                <ComplianceAdminPage />
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
  );
}
