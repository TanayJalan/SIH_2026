import { Link, Navigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";

import Breadcrumbs from "../components/Breadcrumbs";
import PageHeader from "../components/PageHeader";
import CaseCommittees from "../components/casefile/CaseCommittees";
import CaseCompliance from "../components/casefile/CaseCompliance";
import CaseDeficiencies from "../components/casefile/CaseDeficiencies";
import CaseDocuments from "../components/casefile/CaseDocuments";
import CaseFileHeader, { type RiskSummary } from "../components/casefile/CaseFileHeader";
import CaseInspection from "../components/casefile/CaseInspection";
import CaseOverview from "../components/casefile/CaseOverview";
import CaseSidebar from "../components/casefile/CaseSidebar";
import CaseTimeline from "../components/casefile/CaseTimeline";
import { CASE_STAGES, buildStageEvents } from "../components/casefile/stages";
import { WorkflowDialogHost } from "../components/workflow/WorkflowDialogHost";
import {
  Skeleton,
  StageTrack,
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
  type RiskLevel,
} from "../components/ui";
import { useAuth } from "../auth/AuthContext";
import {
  ApiError,
  getApplication,
  getApplicationCompliance,
  getWorkflowTimeline,
  listDeficiencies,
  type ComplianceRulePreview,
} from "../lib/api";
import { shortId } from "../lib/format";
import { applicationsLabelFor } from "../lib/roles";

const TABS = [
  { value: "overview", label: "Overview" },
  { value: "documents", label: "Documents" },
  { value: "compliance", label: "Compliance" },
  { value: "deficiencies", label: "Deficiencies" },
  { value: "inspection", label: "Inspection" },
  { value: "committees", label: "Committees" },
  { value: "timeline", label: "Timeline" },
];

function riskLevelFor(rules: ComplianceRulePreview[]): RiskLevel {
  if (rules.some((rule) => rule.severity === "CRITICAL")) {
    return "high";
  }
  if (rules.some((rule) => rule.severity === "HIGH")) {
    return "medium";
  }
  return "low";
}

export default function ApplicationDetailPage() {
  const { applicationId } = useParams<{ applicationId: string }>();
  const { user, token } = useAuth();

  const applicationQuery = useQuery({
    queryKey: ["application", applicationId],
    queryFn: () => getApplication(token ?? "", applicationId ?? ""),
    enabled: Boolean(token && applicationId),
    retry: false,
  });

  // Supporting case-file data; every read is role-scoped server-side.
  const timelineQuery = useQuery({
    queryKey: ["workflow-timeline", applicationId],
    queryFn: () => getWorkflowTimeline(token ?? "", applicationId ?? ""),
    enabled: Boolean(token && applicationId && applicationQuery.data),
    retry: false,
  });
  const deficienciesQuery = useQuery({
    queryKey: ["deficiencies", applicationId],
    queryFn: () => listDeficiencies(token ?? "", applicationId ?? ""),
    enabled: Boolean(token && applicationId && applicationQuery.data),
    retry: false,
  });
  const complianceQuery = useQuery({
    queryKey: ["compliance-preview", applicationId],
    queryFn: () => getApplicationCompliance(token ?? "", applicationId ?? ""),
    enabled: Boolean(token && applicationId && applicationQuery.data),
    retry: false,
  });

  if (!user) {
    return null;
  }

  if (!applicationId) {
    return <Navigate to="/applications" replace />;
  }

  const applicationsLabel = applicationsLabelFor(user.role);
  const application = applicationQuery.data;
  const title = application?.reference ?? `Application ${shortId(applicationId)}`;

  if (applicationQuery.isPending) {
    return (
      <>
        <Breadcrumbs
          items={[
            { label: applicationsLabel, to: "/applications" },
            { label: "Application" },
          ]}
        />
        <PageHeader
          eyebrow="Application record"
          title="Loading application"
          description="Retrieving the case record visible to your role."
        />
        <div className="space-y-4" role="status">
          <Skeleton className="h-40 w-full" />
          <Skeleton className="h-64 w-full" />
          <span className="sr-only">Loading application</span>
        </div>
      </>
    );
  }

  if (applicationQuery.isError || !application) {
    const message =
      applicationQuery.error instanceof ApiError
        ? applicationQuery.error.message
        : "This application could not be loaded.";
    return (
      <>
        <Breadcrumbs
          items={[
            { label: applicationsLabel, to: "/applications" },
            { label: "Application" },
          ]}
        />
        <PageHeader
          eyebrow="Application record"
          title="Application unavailable"
          description="The record may not exist, or it may be outside your permitted scope."
          actions={
            <Link
              to="/applications"
              className="inline-flex h-8 items-center gap-2 rounded-input border border-ink bg-surface px-3 text-13 font-medium text-ink hover:bg-paper"
            >
              <ArrowLeft aria-hidden="true" className="size-4" />
              Back to {applicationsLabel.toLowerCase()}
            </Link>
          }
        />
        <div className="rounded-panel border border-line bg-surface p-6">
          <p className="rounded-input border border-breach bg-breach-soft p-4 text-14 text-breach-strong">
            {message}
          </p>
        </div>
      </>
    );
  }

  const stageEvents = buildStageEvents(
    application,
    timelineQuery.data?.events ?? [],
    deficienciesQuery.data ?? [],
  );

  const failedRules = (complianceQuery.data?.rules ?? []).filter(
    (rule) => rule.status === "FAIL",
  );
  const risk: RiskSummary = {
    level: riskLevelFor(failedRules),
    reasons: failedRules.map((rule) => `${rule.name}: ${rule.message}`),
  };

  const officerRole =
    user.role === "SCRUTINY_COMMITTEE_MEMBER" || user.role === "SUPER_ADMIN";
  const regionalRole = user.role === "REGIONAL_OFFICER" || user.role === "SUPER_ADMIN";
  const institutionRole = user.role === "INSTITUTION_ADMIN";

  return (
    <WorkflowDialogHost application={application} token={token ?? ""}>
      <Breadcrumbs
        items={[
          { label: applicationsLabel, to: "/applications" },
          { label: title },
        ]}
      />

      <div className="mt-4 space-y-5">
        <CaseFileHeader
          application={application}
          token={token ?? ""}
          userRole={user.role}
          risk={risk}
        />

        <StageTrack
          stages={CASE_STAGES}
          current={application.current_stage}
          events={stageEvents}
          label="Application workflow stages"
          className="rounded-panel border border-line bg-surface p-5 sm:p-6"
        />

        <div className="grid min-w-0 grid-cols-1 gap-6 xl:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]">
          <div className="min-w-0">
            <Tabs defaultValue="overview">
              <TabsList aria-label="Case file sections">
                {TABS.map((tab) => (
                  <TabsTrigger key={tab.value} value={tab.value}>
                    {tab.label}
                  </TabsTrigger>
                ))}
              </TabsList>

              <TabsContent value="overview">
                <CaseOverview
                  application={application}
                  rules={complianceQuery.data?.rules ?? []}
                />
              </TabsContent>

              <TabsContent value="documents">
                <CaseDocuments applicationId={application.id} token={token ?? ""} />
              </TabsContent>

              <TabsContent value="compliance">
                <CaseCompliance
                  applicationId={application.id}
                  token={token ?? ""}
                  canRaiseDeficiency={officerRole}
                />
              </TabsContent>

              <TabsContent value="deficiencies">
                <CaseDeficiencies
                  applicationId={application.id}
                  token={token ?? ""}
                  canRespond={institutionRole}
                  canClose={officerRole}
                />
              </TabsContent>

              <TabsContent value="inspection">
                <CaseInspection
                  applicationId={application.id}
                  token={token ?? ""}
                  canSchedule={regionalRole}
                />
              </TabsContent>

              <TabsContent value="committees">
                <CaseCommittees
                  applicationId={application.id}
                  token={token ?? ""}
                  canSelect={
                    regionalRole ||
                    user.role === "REGULATION_BUREAU_OFFICER" ||
                    user.role === "SUPER_ADMIN"
                  }
                />
              </TabsContent>

              <TabsContent value="timeline">
                <CaseTimeline applicationId={application.id} token={token ?? ""} />
              </TabsContent>
            </Tabs>
          </div>

          <CaseSidebar application={application} token={token ?? ""} />
        </div>
      </div>
    </WorkflowDialogHost>
  );
}
