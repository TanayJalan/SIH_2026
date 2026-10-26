import { useEffect, useMemo, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertCircle,
  ArrowLeft,
  ArrowRight,
  CheckCircle2,
  CreditCard,
  Download,
  FileWarning,
  Loader2,
  Lock,
  Send,
  ShieldAlert,
} from "lucide-react";
import type { ReactNode } from "react";
import { Link, Navigate, useNavigate, useParams } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import ApplicationProgressRail, {
  SaveStatus,
  type SaveState,
} from "../components/application/ApplicationProgressRail";
import CompliancePreviewPanel from "../components/application/CompliancePreviewPanel";
import DeficiencyReportPanel from "../components/application/DeficiencyReportPanel";
import DocumentChecklist from "../components/application/DocumentChecklist";
import DocumentVerificationBadge from "../components/application/DocumentVerificationBadge";
import ProgramEditor from "../components/application/ProgramEditor";
import SubmissionSuccessPanel from "../components/application/SubmissionSuccessPanel";
import ApplicationStatusBadge from "../components/ApplicationStatusBadge";
import Breadcrumbs from "../components/Breadcrumbs";
import PageHeader from "../components/PageHeader";
import {
  Button,
  DatePicker,
  Input,
  ProgressBar,
  Select,
  Skeleton,
  useToast,
} from "../components/ui";
import {
  NAAC_OPTIONS,
  NBA_OPTIONS,
  WIZARD_STEPS,
  fieldIdForMissingCode,
  firstError,
  formatBytes,
  hasErrors,
  programLevelLabel,
  stepForMissingCode,
  toIntegerOrNull,
  toNumberOrNull,
  validateStep,
  type FieldErrors,
  type WizardStepId,
} from "../lib/application";
import {
  ApiError,
  downloadDocumentShell,
  getApplication,
  getApplicationChecklist,
  getApplicationFee,
  getCompliancePreview,
  getSecurityDepositQuote,
  listDocumentShells,
  payApplicationFee,
  submitApplication,
  updateApplicationData,
  type ApplicationData,
  type ApplicationSubmission,
  type MissingItem,
  type NaacGrade,
  type NbaStatus,
} from "../lib/api";
import { formatDate, formatInr, humanizeEnum, shortId } from "../lib/format";
import { applicationsLabelFor } from "../lib/roles";
import { useDebouncedValue } from "../lib/useDebouncedValue";

const SECTION_STEP_IDS: WizardStepId[] = [
  "profile",
  "infrastructure",
  "faculty",
  "finance",
  "accreditation",
];

const CHECKLIST_SECTION_BY_STEP: Partial<Record<WizardStepId, string>> = {
  profile: "institution_profile",
  infrastructure: "infrastructure",
  faculty: "faculty",
  finance: "finance",
  accreditation: "accreditation",
};

const CHECKLIST_LABEL_BY_STEP: Partial<Record<WizardStepId, string>> = {
  profile: "Institution profile",
  infrastructure: "Infrastructure",
  faculty: "Faculty",
  finance: "Finance",
  accreditation: "Accreditation",
};

function normaliseData(
  data: ApplicationData | undefined,
  institutionState: string | undefined,
): ApplicationData {
  return {
    institution_profile: {
      ...(institutionState ? { state: institutionState } : {}),
      ...(data?.institution_profile ?? {}),
    },
    infrastructure: { hostel: 0, ...(data?.infrastructure ?? {}) },
    faculty: { ...(data?.faculty ?? {}) },
    finance: { ...(data?.finance ?? {}) },
    accreditation: { ...(data?.accreditation ?? {}) },
    mandatory_disclosure_url: data?.mandatory_disclosure_url ?? null,
  };
}

function valueOrDash(value: string | number | null | undefined): string {
  if (value === null || value === undefined || value === "") {
    return "—";
  }
  return String(value);
}

function FormGroup({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: ReactNode;
}) {
  return (
    <fieldset className="space-y-4">
      <legend className="text-13 font-semibold text-ink">{title}</legend>
      {description ? (
        <p className="max-w-2xl text-12 leading-5 text-ink-500">{description}</p>
      ) : null}
      <div className="grid grid-cols-1 gap-5 sm:grid-cols-2">{children}</div>
    </fieldset>
  );
}

function ReviewField({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="min-w-0">
      <dt className="text-12 text-ink-500">{label}</dt>
      <dd className="mt-0.5 break-words text-13 text-ink">{value}</dd>
    </div>
  );
}

function ReviewSection({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <section className="rounded-input border border-line p-4">
      <h3 className="text-13 font-semibold text-ink">{title}</h3>
      <dl className="mt-3 grid grid-cols-1 gap-x-4 gap-y-3 sm:grid-cols-2">{children}</dl>
    </section>
  );
}

export default function ApplicationWizardPage() {
  const { applicationId } = useParams<{ applicationId: string }>();
  const { user, token } = useAuth();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { toast } = useToast();

  const [stepIndex, setStepIndex] = useState(0);
  const [form, setForm] = useState<ApplicationData>({});
  const [hydrated, setHydrated] = useState(false);
  const [errors, setErrors] = useState<FieldErrors>({});
  const [saveState, setSaveState] = useState<SaveState>("saved");
  const [saveError, setSaveError] = useState<string | null>(null);
  const [lastSavedAt, setLastSavedAt] = useState<Date | null>(null);
  const [serverMissing, setServerMissing] = useState<MissingItem[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [submission, setSubmission] = useState<ApplicationSubmission | null>(null);
  const [pendingFocus, setPendingFocus] = useState<string | null>(null);
  const hydratedId = useRef<string | null>(null);
  const skipAutosave = useRef(true);
  const saveSequence = useRef(0);

  const applicationQuery = useQuery({
    queryKey: ["application", applicationId],
    queryFn: () => getApplication(token ?? "", applicationId ?? ""),
    enabled: Boolean(token && applicationId),
    retry: false,
  });

  const checklistQuery = useQuery({
    queryKey: ["checklist", applicationId],
    queryFn: () => getApplicationChecklist(token ?? "", applicationId ?? ""),
    enabled: Boolean(token && applicationId),
    retry: false,
  });

  const application = applicationQuery.data;
  const checklist = checklistQuery.data;
  const debouncedForm = useDebouncedValue(form, 500);

  const complianceQuery = useQuery({
    queryKey: ["compliance-preview", applicationId, debouncedForm],
    queryFn: () => getCompliancePreview(token ?? "", applicationId ?? "", debouncedForm),
    enabled: Boolean(
      token && applicationId && hydrated && application?.status === "DRAFT",
    ),
    retry: false,
    placeholderData: (previousData) => previousData,
  });

  const feeQuery = useQuery({
    queryKey: ["application-fee", applicationId],
    queryFn: () => getApplicationFee(token ?? "", applicationId ?? ""),
    enabled: Boolean(token && applicationId),
    retry: false,
  });

  const securityDepositQuery = useQuery({
    queryKey: ["security-deposit", applicationId],
    queryFn: () => getSecurityDepositQuote(token ?? "", applicationId ?? ""),
    enabled: Boolean(token && applicationId),
    retry: false,
  });

  const shellsQuery = useQuery({
    queryKey: ["document-shells", applicationId],
    queryFn: () => listDocumentShells(token ?? "", applicationId ?? ""),
    enabled: Boolean(token && applicationId),
    retry: false,
  });

  const [paying, setPaying] = useState(false);
  const [downloadingShell, setDownloadingShell] = useState<string | null>(null);
  const [shellError, setShellError] = useState<string | null>(null);

  useEffect(() => {
    const loadedApplication = applicationQuery.data;
    if (!loadedApplication || hydratedId.current === loadedApplication.id) {
      return;
    }
    hydratedId.current = loadedApplication.id;
    setForm(
      normaliseData(loadedApplication.data, loadedApplication.institution.state),
    );
    const savedAt = loadedApplication.updated_at
      ? new Date(loadedApplication.updated_at)
      : new Date();
    setLastSavedAt(Number.isNaN(savedAt.getTime()) ? new Date() : savedAt);
    setHydrated(true);
    skipAutosave.current = true;
  }, [applicationQuery.data]);

  useEffect(() => {
    if (!hydrated || !token || !applicationId || submission) {
      return;
    }
    if (skipAutosave.current) {
      skipAutosave.current = false;
      return;
    }

    const sequence = ++saveSequence.current;
    setSaveState("pending");
    const timer = window.setTimeout(() => {
      setSaveState("saving");
      updateApplicationData(token, applicationId, form)
        .then(() => {
          if (sequence !== saveSequence.current) {
            return;
          }
          setSaveState("saved");
          setSaveError(null);
          setLastSavedAt(new Date());
          void queryClient.invalidateQueries({
            queryKey: ["checklist", applicationId],
          });
        })
        .catch((saveFailure: unknown) => {
          if (sequence !== saveSequence.current) {
            return;
          }
          setSaveState("error");
          setSaveError(
            saveFailure instanceof ApiError
              ? saveFailure.message
              : "Draft could not be saved.",
          );
        });
    }, 700);

    return () => window.clearTimeout(timer);
  }, [applicationId, form, hydrated, queryClient, submission, token]);

  useEffect(() => {
    if (!pendingFocus) {
      return;
    }
    const frame = window.requestAnimationFrame(() => {
      const element = window.document.getElementById(pendingFocus);
      if (element instanceof HTMLElement) {
        element.scrollIntoView({ behavior: "smooth", block: "center" });
        element.focus({ preventScroll: true });
      }
      setPendingFocus(null);
    });
    return () => window.cancelAnimationFrame(frame);
  }, [pendingFocus, stepIndex]);

  const currentStep = WIZARD_STEPS[stepIndex] ?? WIZARD_STEPS[0];
  const currentIndex = stepIndex;
  const profile = form.institution_profile;
  const infrastructure = form.infrastructure;
  const faculty = form.faculty;
  const finance = form.finance;
  const accreditation = form.accreditation;
  const mandatoryDocs = checklist?.documents.filter((document) => document.mandatory) ?? [];
  const uploadedDocs = mandatoryDocs.filter(
    (document) => document.uploaded && document.signed_with_dsc !== false,
  ).length;
  const documentPercent =
    mandatoryDocs.length > 0 ? Math.round((uploadedDocs / mandatoryDocs.length) * 100) : 100;

  const localMissing = useMemo(() => {
    const items: MissingItem[] = [];
    for (const step of SECTION_STEP_IDS) {
      const stepErrors = validateStep(step, form);
      for (const [field, message] of Object.entries(stepErrors)) {
        const sectionKey =
          field === "mandatory_disclosure_url"
            ? "mandatory_disclosure_url"
            : (CHECKLIST_SECTION_BY_STEP[step] ?? step);
        items.push({
          code: `${sectionKey}.${field}`,
          section: CHECKLIST_LABEL_BY_STEP[step] ?? currentStep.label,
          message,
        });
      }
    }
    for (const document of mandatoryDocs) {
      if (!document.uploaded) {
        items.push({
          code: `document.${document.doc_type}`,
          section: "Documents",
          message: `Upload the required document: ${document.label}.`,
        });
      } else if (document.signed_with_dsc === false) {
        items.push({
          code: `document.${document.doc_type}.dsc`,
          section: "Documents",
          message: `Re-upload ${document.label} with a valid digital signature (DSC).`,
        });
      }
    }
    return items;
  }, [form, mandatoryDocs]);

  const blockingIssues = useMemo(() => {
    const byCode = new Map<string, MissingItem>();
    for (const item of localMissing) {
      byCode.set(item.code, item);
    }
    for (const item of [...serverMissing, ...(checklist?.missing ?? [])]) {
      if (!byCode.has(item.code)) {
        byCode.set(item.code, item);
      }
    }
    return Array.from(byCode.values());
  }, [checklist?.missing, localMissing, serverMissing]);

  const canSubmit =
    blockingIssues.length === 0 &&
    Boolean(checklist?.can_submit) &&
    Boolean(feeQuery.data?.is_paid) &&
    !checklistQuery.isPending;
  const feePaid = Boolean(feeQuery.data?.is_paid);
  const submitDisabled =
    submitting ||
    !canSubmit ||
    saveState === "pending" ||
    saveState === "saving" ||
    saveState === "error" ||
    checklistQuery.isPending;

  const stepCompletion = useMemo(() => {
    const completion = {} as Record<WizardStepId, boolean>;
    for (const step of WIZARD_STEPS) {
      switch (step.id) {
        case "profile":
        case "infrastructure":
        case "faculty":
        case "finance":
        case "accreditation":
          completion[step.id] = !hasErrors(validateStep(step.id, form));
          break;
        case "programs":
          completion[step.id] = (application?.programs.length ?? 0) > 0;
          break;
        case "documents":
          completion[step.id] =
            mandatoryDocs.length > 0 && uploadedDocs === mandatoryDocs.length;
          break;
        case "payment":
          completion[step.id] = Boolean(feeQuery.data?.is_paid);
          break;
        case "review":
          completion[step.id] = canSubmit;
          break;
      }
    }
    return completion;
  }, [
    application?.programs.length,
    canSubmit,
    feeQuery.data?.is_paid,
    form,
    mandatoryDocs.length,
    uploadedDocs,
  ]);

  const saveNow = async (): Promise<boolean> => {
    if (!token || !applicationId) {
      return false;
    }
    setSaveState("saving");
    setSaveError(null);
    try {
      await updateApplicationData(token, applicationId, form);
      setSaveState("saved");
      setLastSavedAt(new Date());
      await queryClient.invalidateQueries({ queryKey: ["checklist", applicationId] });
      return true;
    } catch (saveFailure) {
      setSaveState("error");
      setSaveError(
        saveFailure instanceof ApiError
          ? saveFailure.message
          : "Draft could not be saved.",
      );
      return false;
    }
  };

  const updateForm = (updater: (current: ApplicationData) => ApplicationData) => {
    setForm(updater);
    setServerMissing([]);
  };

  const clearError = (key: string) => {
    setErrors((current) => {
      if (!(key in current)) {
        return current;
      }
      const next = { ...current };
      delete next[key];
      return next;
    });
  };

  const validateOnBlur = (step: WizardStepId, key: string) => {
    const stepErrors = validateStep(step, form);
    setErrors((current) => {
      const next = { ...current };
      if (stepErrors[key]) {
        next[key] = stepErrors[key];
      } else {
        delete next[key];
      }
      return next;
    });
  };

  const goToStep = (step: WizardStepId) => {
    const index = WIZARD_STEPS.findIndex((stepDefinition) => stepDefinition.id === step);
    if (index >= 0) {
      setStepIndex(index);
      setErrors({});
      setPendingFocus(null);
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
  };

  const jumpToIssue = (item: MissingItem) => {
    const step = stepForMissingCode(item.code);
    const index = WIZARD_STEPS.findIndex((stepDefinition) => stepDefinition.id === step);
    if (index < 0) {
      return;
    }
    setStepIndex(index);
    setErrors({});
    setPendingFocus(fieldIdForMissingCode(item.code));
  };

  const goNext = () => {
    const nextErrors = validateStep(currentStep.id, form);
    setErrors(nextErrors);
    if (hasErrors(nextErrors)) {
      toast({
        title: "Check this section",
        description: firstError(nextErrors) ?? "Complete the required fields.",
        variant: "error",
      });
      return;
    }
    if (stepIndex < WIZARD_STEPS.length - 1) {
      setStepIndex((index) => index + 1);
      setErrors({});
      setPendingFocus(null);
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
  };

  const goBack = () => {
    if (stepIndex > 0) {
      setStepIndex((index) => index - 1);
      setErrors({});
      setPendingFocus(null);
      window.scrollTo({ top: 0, behavior: "smooth" });
    }
  };

  const handleSubmit = async () => {
    setServerMissing([]);
    if (blockingIssues.length > 0) {
      toast({
        title: "Resolve blocking issues",
        description: `${blockingIssues.length} required item${
          blockingIssues.length === 1 ? "" : "s"
        } must be completed before submission.`,
        variant: "error",
      });
      return;
    }
    for (const step of SECTION_STEP_IDS) {
      const sectionErrors = validateStep(step, form);
      if (hasErrors(sectionErrors)) {
        const index = WIZARD_STEPS.findIndex((item) => item.id === step);
        setStepIndex(Math.max(0, index));
        setErrors(sectionErrors);
        toast({
          title: "Complete the required fields",
          description: firstError(sectionErrors) ?? "A required section is incomplete.",
          variant: "error",
        });
        return;
      }
    }
    if (!feePaid) {
      const paymentIndex = WIZARD_STEPS.findIndex((item) => item.id === "payment");
      setStepIndex(Math.max(0, paymentIndex));
      setErrors({});
      toast({
        title: "TER payment required",
        description:
          "Pay the TER on the Payment step before submitting. The server will reject an unpaid submission.",
        variant: "error",
      });
      return;
    }
    if (!token || !applicationId) {
      return;
    }

    setSubmitting(true);
    const saved = await saveNow();
    if (!saved) {
      setSubmitting(false);
      toast({
        title: "Submission stopped",
        description: "Your latest changes could not be saved.",
        variant: "error",
      });
      return;
    }

    try {
      const submitted = await submitApplication(token, applicationId);
      setSubmission(submitted);
      toast({
        title: "Application submitted",
        description: "The SLA due date has been set from the configured application-stage duration.",
        variant: "success",
      });
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["application", applicationId] }),
        queryClient.invalidateQueries({ queryKey: ["checklist", applicationId] }),
        queryClient.invalidateQueries({ queryKey: ["applications"] }),
      ]);
    } catch (submitError) {
      if (submitError instanceof ApiError) {
        setServerMissing(submitError.missing ?? []);
      }
      toast({
        title: "Application not submitted",
        description:
          submitError instanceof ApiError
            ? submitError.message
            : "The application could not be submitted.",
        variant: "error",
      });
    } finally {
      setSubmitting(false);
    }
  };

  const handlePay = async () => {
    if (!token || !applicationId) {
      return;
    }
    setPaying(true);
    try {
      const result = await payApplicationFee(token, applicationId);
      queryClient.setQueryData(["application-fee", applicationId], result.quote);
      toast({
        title: "TER paid",
        description: result.quote.ter_receipt_no
          ? `Receipt ${result.quote.ter_receipt_no} recorded. You can now submit.`
          : "Payment recorded against this application.",
        variant: "success",
      });
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["application-fee", applicationId] }),
        queryClient.invalidateQueries({ queryKey: ["checklist", applicationId] }),
        queryClient.invalidateQueries({ queryKey: ["application", applicationId] }),
      ]);
    } catch (payError) {
      toast({
        title: "Payment not recorded",
        description:
          payError instanceof ApiError
            ? payError.message
            : "The simulated gateway could not complete the payment.",
        variant: "error",
      });
    } finally {
      setPaying(false);
    }
  };

  const handleShellDownload = async (docCode: string) => {
    if (!token || !applicationId) {
      return;
    }
    setDownloadingShell(docCode);
    setShellError(null);
    try {
      await downloadDocumentShell(token, applicationId, docCode);
    } catch (shellFailure) {
      setShellError(
        shellFailure instanceof ApiError
          ? shellFailure.message
          : "The document shell could not be downloaded.",
      );
    } finally {
      setDownloadingShell(null);
    }
  };

  const updateProfile = (patch: Partial<NonNullable<ApplicationData["institution_profile"]>>) => {
    updateForm((current) => ({
      ...current,
      institution_profile: { ...(current.institution_profile ?? {}), ...patch },
    }));
  };
  const updateInfrastructure = (
    patch: Partial<NonNullable<ApplicationData["infrastructure"]>>,
  ) => {
    updateForm((current) => ({
      ...current,
      infrastructure: { ...(current.infrastructure ?? {}), ...patch },
    }));
  };
  const updateFaculty = (patch: Partial<NonNullable<ApplicationData["faculty"]>>) => {
    updateForm((current) => ({
      ...current,
      faculty: { ...(current.faculty ?? {}), ...patch },
    }));
  };
  const updateFinance = (patch: Partial<NonNullable<ApplicationData["finance"]>>) => {
    updateForm((current) => ({
      ...current,
      finance: { ...(current.finance ?? {}), ...patch },
    }));
  };
  const updateAccreditation = (
    patch: Partial<NonNullable<ApplicationData["accreditation"]>>,
  ) => {
    updateForm((current) => ({
      ...current,
      accreditation: { ...(current.accreditation ?? {}), ...patch },
    }));
  };

  const renderCompliancePanel = () => (
    <CompliancePreviewPanel
      preview={complianceQuery.data}
      loading={complianceQuery.isPending}
      fetching={complianceQuery.isFetching}
      error={complianceQuery.isError}
      onRetry={() => void complianceQuery.refetch()}
    />
  );

  if (!user) {
    return null;
  }
  if (!applicationId) {
    return <Navigate to="/applications" replace />;
  }

  const applicationsLabel = applicationsLabelFor(user.role);

  if (submission) {
    const submittedApplication = submission.application;
    return (
      <>
        <Breadcrumbs
          items={[
            { label: applicationsLabel, to: "/applications" },
            {
              label:
                submittedApplication.reference ??
                `Application ${shortId(submittedApplication.id)}`,
              to: `/applications/${submittedApplication.id}`,
            },
            { label: "Submitted" },
          ]}
        />
        <SubmissionSuccessPanel submission={submission} />
      </>
    );
  }

  if (applicationQuery.isPending) {
    return (
      <>
        <Breadcrumbs
          items={[{ label: applicationsLabel, to: "/applications" }, { label: "Draft" }]}
        />
        <PageHeader
          eyebrow="Institution workspace"
          title="Loading draft"
          description="Retrieving the application, completeness checklist and compliance preview."
        />
        <div className="space-y-4" role="status">
          <Skeleton className="h-16 w-full" />
          <Skeleton className="h-96 w-full" />
          <span className="sr-only">Loading draft</span>
        </div>
      </>
    );
  }

  if (applicationQuery.isError || !application) {
    return (
      <>
        <Breadcrumbs
          items={[{ label: applicationsLabel, to: "/applications" }, { label: "Draft" }]}
        />
        <PageHeader
          eyebrow="Institution workspace"
          title="Draft unavailable"
          description="The draft may not exist, or it may be outside your permitted scope."
        />
        <div className="rounded-panel border border-line bg-surface p-6">
          <p className="rounded-input border border-breach bg-breach-soft p-4 text-14 text-breach-strong">
            {applicationQuery.error instanceof ApiError
              ? applicationQuery.error.message
              : "This draft could not be loaded."}
          </p>
          <Button asChild variant="secondary" size="sm" className="mt-4">
            <Link to="/applications">
              <ArrowLeft aria-hidden="true" className="size-4" />
              Back to {applicationsLabel.toLowerCase()}
            </Link>
          </Button>
        </div>
      </>
    );
  }

  if (application.status !== "DRAFT") {
    return (
      <>
        <Breadcrumbs
          items={[
            { label: applicationsLabel, to: "/applications" },
            { label: application.reference ?? `Application ${shortId(application.id)}` },
          ]}
        />
        <PageHeader
          eyebrow="Application record"
          title="This application is no longer a draft"
          description="Submitted applications are read-only in the institution workspace."
          actions={
            <Button asChild variant="secondary" size="sm">
              <Link to={`/applications/${application.id}`}>
                <ArrowLeft aria-hidden="true" className="size-4" />
                Open application
              </Link>
            </Button>
          }
        />
        <section className="rounded-panel border border-line bg-surface p-5">
          <div className="flex items-start gap-2.5">
            <Lock aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-ink-500" />
            <div className="space-y-1">
              <h2 className="text-14 font-semibold text-ink">Final submission locked</h2>
              <p className="text-12 leading-5 text-ink-500">
                {application.locked_at
                  ? `Locked on ${formatDate(application.locked_at)}. `
                  : "Data is locked. "}
                Any edit is rejected with HTTP 409. The Regulation Bureau may reopen the
                application once under APH 2.3.3d-e.
              </p>
              <p className="text-12 text-ink-500">
                Portal application number:{" "}
                <span className="font-medium text-ink-700">
                  {application.portal_application_no ?? "Not issued"}
                </span>
              </p>
              <p className="text-12 text-ink-500">
                Reopenings used: {application.reopen_count} of 1
                {application.late_submission
                  ? " · flagged as a late submission and moved to the next academic year"
                  : ""}
              </p>
            </div>
          </div>
        </section>
      </>
    );
  }

  const title = application.reference ?? `Draft ${shortId(application.id)}`;
  const isReview = currentStep.id === "review";
  const submitHelper = submitting
    ? "Submitting the application…"
    : blockingIssues.length > 0
      ? `Resolve ${blockingIssues.length} blocking issue${
          blockingIssues.length === 1 ? "" : "s"
        } to enable submission.`
      : checklistQuery.isPending
        ? "Checking the server-side completeness checklist…"
        : !feePaid
          ? feeQuery.isError
            ? "The TER position could not be loaded. Retry the Payment step before submitting."
            : "Pay the TER on the Payment step to enable submission."
          : saveState === "pending" || saveState === "saving"
            ? "Saving your latest changes before submission…"
            : saveState === "error"
              ? "The latest changes could not be saved. Retry before submitting."
              : "Ready to submit. The server will re-check every required item.";

  const stepContent = () => {
    switch (currentStep.id) {
      case "profile":
        return (
          <div className="space-y-7">
            <FormGroup
              title="Institution contact"
              description="These details identify the institution and the person coordinating this application."
            >
              <Input
                id="profile-head-name"
                label="Head of institution"
                required
                value={profile?.head_name ?? ""}
                error={errors.head_name}
                placeholder="Name of the principal or director"
                onChange={(event) => {
                  updateProfile({ head_name: event.target.value });
                  clearError("head_name");
                }}
                onBlur={() => validateOnBlur("profile", "head_name")}
              />
              <Input
                id="profile-contact-email"
                label="Contact email"
                type="email"
                required
                value={profile?.contact_email ?? ""}
                error={errors.contact_email}
                placeholder="registrar@example.edu"
                onChange={(event) => {
                  updateProfile({ contact_email: event.target.value });
                  clearError("contact_email");
                }}
                onBlur={() => validateOnBlur("profile", "contact_email")}
              />
              <Input
                id="profile-contact-phone"
                label="Contact phone"
                type="tel"
                required
                value={profile?.contact_phone ?? ""}
                error={errors.contact_phone}
                placeholder="+91 98765 43210"
                onChange={(event) => {
                  updateProfile({ contact_phone: event.target.value });
                  clearError("contact_phone");
                }}
                onBlur={() => validateOnBlur("profile", "contact_phone")}
              />
              <Input
                id="profile-website"
                label="Website"
                type="url"
                value={profile?.website ?? ""}
                placeholder="https://example.edu (optional)"
                onChange={(event) => updateProfile({ website: event.target.value })}
              />
            </FormGroup>

            <FormGroup
              title="Campus address"
              description="Use the registered campus address. The state is pre-filled from your institution record."
            >
              <Input
                id="profile-address-line1"
                label="Address line 1"
                required
                value={profile?.address_line1 ?? ""}
                error={errors.address_line1}
                placeholder="Campus address"
                onChange={(event) => {
                  updateProfile({ address_line1: event.target.value });
                  clearError("address_line1");
                }}
                onBlur={() => validateOnBlur("profile", "address_line1")}
                containerClassName="sm:col-span-2"
              />
              <Input
                id="profile-address-line2"
                label="Address line 2"
                value={profile?.address_line2 ?? ""}
                placeholder="Area, landmark (optional)"
                onChange={(event) => updateProfile({ address_line2: event.target.value })}
                containerClassName="sm:col-span-2"
              />
              <Input
                id="profile-city"
                label="City"
                required
                value={profile?.city ?? ""}
                error={errors.city}
                onChange={(event) => {
                  updateProfile({ city: event.target.value });
                  clearError("city");
                }}
                onBlur={() => validateOnBlur("profile", "city")}
              />
              <Input
                id="profile-state"
                label="State"
                required
                value={profile?.state ?? ""}
                error={errors.state}
                onChange={(event) => {
                  updateProfile({ state: event.target.value });
                  clearError("state");
                }}
                onBlur={() => validateOnBlur("profile", "state")}
              />
              <Input
                id="profile-pin-code"
                label="PIN code"
                required
                inputMode="numeric"
                value={profile?.pin_code ?? ""}
                error={errors.pin_code}
                placeholder="411001"
                onChange={(event) => {
                  updateProfile({ pin_code: event.target.value });
                  clearError("pin_code");
                }}
                onBlur={() => validateOnBlur("profile", "pin_code")}
              />
            </FormGroup>
          </div>
        );
      case "infrastructure":
        return (
          <div className="space-y-7">
            <FormGroup
              title="Campus space"
              description="Enter the land and constructed area available to the institution."
            >
              <Input
                id="infrastructure-land-area"
                label="Land area"
                type="number"
                min={0}
                step="any"
                suffix="sq. m"
                required
                value={infrastructure?.land_area ?? ""}
                error={errors.land_area}
                onChange={(event) => {
                  updateInfrastructure({ land_area: toNumberOrNull(event.target.value) });
                  clearError("land_area");
                }}
                onBlur={() => validateOnBlur("infrastructure", "land_area")}
              />
              <Input
                id="infrastructure-built-up-area"
                label="Built-up area"
                type="number"
                min={0}
                step="any"
                suffix="sq. m"
                required
                value={infrastructure?.built_up_area ?? ""}
                error={errors.built_up_area}
                onChange={(event) => {
                  updateInfrastructure({ built_up_area: toNumberOrNull(event.target.value) });
                  clearError("built_up_area");
                }}
                onBlur={() => validateOnBlur("infrastructure", "built_up_area")}
              />
            </FormGroup>

            <FormGroup
              title="Teaching and residential facilities"
              description="Counts are used by the compliance preview while you type."
            >
              <Input
                id="infrastructure-labs"
                label="Laboratories"
                type="number"
                min={0}
                step={1}
                suffix="count"
                required
                value={infrastructure?.labs ?? ""}
                error={errors.labs}
                onChange={(event) => {
                  updateInfrastructure({ labs: toIntegerOrNull(event.target.value) });
                  clearError("labs");
                }}
                onBlur={() => validateOnBlur("infrastructure", "labs")}
              />
              <Input
                id="infrastructure-library"
                label="Library collection"
                type="number"
                min={0}
                step={1}
                suffix="volumes"
                required
                value={infrastructure?.library ?? ""}
                error={errors.library}
                onChange={(event) => {
                  updateInfrastructure({ library: toIntegerOrNull(event.target.value) });
                  clearError("library");
                }}
                onBlur={() => validateOnBlur("infrastructure", "library")}
              />
              <Input
                id="infrastructure-hostel"
                label="Hostel capacity"
                type="number"
                min={0}
                step={1}
                suffix="beds"
                required
                value={infrastructure?.hostel ?? ""}
                error={errors.hostel}
                hint="Use 0 if the institution does not provide hostel accommodation."
                onChange={(event) => {
                  updateInfrastructure({ hostel: toIntegerOrNull(event.target.value) });
                  clearError("hostel");
                }}
                onBlur={() => validateOnBlur("infrastructure", "hostel")}
                containerClassName="sm:max-w-sm"
              />
            </FormGroup>
          </div>
        );
      case "faculty":
        return (
          <div className="space-y-7">
            <FormGroup
              title="Faculty strength"
              description="Use sanctioned or currently filled positions for the current academic year."
            >
              <Input
                id="faculty-total"
                label="Total faculty"
                type="number"
                min={0}
                step={1}
                suffix="count"
                required
                value={faculty?.total ?? ""}
                error={errors.total}
                onChange={(event) => {
                  updateFaculty({ total: toIntegerOrNull(event.target.value) });
                  clearError("total");
                }}
                onBlur={() => validateOnBlur("faculty", "total")}
              />
              <Input
                id="faculty-professors"
                label="Professors"
                type="number"
                min={0}
                step={1}
                suffix="count"
                required
                value={faculty?.professors ?? ""}
                error={errors.professors}
                onChange={(event) => {
                  updateFaculty({ professors: toIntegerOrNull(event.target.value) });
                  clearError("professors");
                }}
                onBlur={() => validateOnBlur("faculty", "professors")}
              />
              <Input
                id="faculty-associate-professors"
                label="Associate professors"
                type="number"
                min={0}
                step={1}
                suffix="count"
                required
                value={faculty?.associate_professors ?? ""}
                error={errors.associate_professors}
                onChange={(event) => {
                  updateFaculty({
                    associate_professors: toIntegerOrNull(event.target.value),
                  });
                  clearError("associate_professors");
                }}
                onBlur={() => validateOnBlur("faculty", "associate_professors")}
              />
              <Input
                id="faculty-assistant-professors"
                label="Assistant professors"
                type="number"
                min={0}
                step={1}
                suffix="count"
                required
                value={faculty?.assistant_professors ?? ""}
                error={errors.assistant_professors}
                onChange={(event) => {
                  updateFaculty({
                    assistant_professors: toIntegerOrNull(event.target.value),
                  });
                  clearError("assistant_professors");
                }}
                onBlur={() => validateOnBlur("faculty", "assistant_professors")}
              />
            </FormGroup>

            <FormGroup
              title="Declared ratios"
              description="These ratios feed the live compliance preview. Enter the values declared in the institutional records."
            >
              <Input
                id="faculty-student-faculty-ratio"
                label="Student-faculty ratio"
                type="number"
                min={0}
                step="any"
                suffix="students/faculty"
                required
                value={faculty?.student_faculty_ratio ?? ""}
                error={errors.student_faculty_ratio}
                onChange={(event) => {
                  updateFaculty({
                    student_faculty_ratio: toNumberOrNull(event.target.value),
                  });
                  clearError("student_faculty_ratio");
                }}
                onBlur={() => validateOnBlur("faculty", "student_faculty_ratio")}
              />
              <Input
                id="faculty-phd-faculty-ratio"
                label="Faculty with a PhD"
                type="number"
                min={0}
                max={100}
                step="any"
                suffix="%"
                required
                value={faculty?.phd_faculty_ratio ?? ""}
                error={errors.phd_faculty_ratio}
                onChange={(event) => {
                  updateFaculty({ phd_faculty_ratio: toNumberOrNull(event.target.value) });
                  clearError("phd_faculty_ratio");
                }}
                onBlur={() => validateOnBlur("faculty", "phd_faculty_ratio")}
              />
            </FormGroup>
          </div>
        );
      case "finance":
        return (
          <div className="space-y-7">
            <FormGroup
              title="Annual fee structure"
              description="Declare the annual fees charged per student for the current academic year."
            >
              <Input
                id="finance-tuition-fee"
                label="Tuition fee"
                type="number"
                min={0}
                step="any"
                suffix="₹ / year"
                required
                value={finance?.tuition_fee ?? ""}
                error={errors.tuition_fee}
                onChange={(event) => {
                  updateFinance({ tuition_fee: toNumberOrNull(event.target.value) });
                  clearError("tuition_fee");
                }}
                onBlur={() => validateOnBlur("finance", "tuition_fee")}
              />
              <Input
                id="finance-development-fee"
                label="Development fee"
                type="number"
                min={0}
                step="any"
                suffix="₹ / year"
                required
                value={finance?.development_fee ?? ""}
                error={errors.development_fee}
                onChange={(event) => {
                  updateFinance({ development_fee: toNumberOrNull(event.target.value) });
                  clearError("development_fee");
                }}
                onBlur={() => validateOnBlur("finance", "development_fee")}
              />
              <Input
                id="finance-other-fees"
                label="Other fees"
                type="number"
                min={0}
                step="any"
                suffix="₹ / year"
                required
                value={finance?.other_fees ?? ""}
                error={errors.other_fees}
                onChange={(event) => {
                  updateFinance({ other_fees: toNumberOrNull(event.target.value) });
                  clearError("other_fees");
                }}
                onBlur={() => validateOnBlur("finance", "other_fees")}
              />
            </FormGroup>

            <FormGroup
              title="Financial position"
              description="Use the audited or management-certified figure for the latest financial year."
            >
              <Input
                id="finance-balance"
                label="Declared balance"
                type="number"
                step="any"
                suffix="₹"
                required
                value={finance?.balance ?? ""}
                error={errors.balance}
                hint="A negative declared balance is allowed but will be flagged in the compliance preview."
                onChange={(event) => {
                  updateFinance({ balance: toNumberOrNull(event.target.value) });
                  clearError("balance");
                }}
                onBlur={() => validateOnBlur("finance", "balance")}
                containerClassName="sm:max-w-sm"
              />
            </FormGroup>
          </div>
        );
      case "accreditation":
        return (
          <div className="space-y-7">
            <FormGroup
              title="Accreditation status"
              description="Select the current NAAC grade and NBA status. Record the latest validation date if available."
            >
              <Select
                id="accreditation-naac-grade"
                label="NAAC grade"
                required
                options={[...NAAC_OPTIONS]}
                value={accreditation?.naac_grade ?? ""}
                error={errors.naac_grade}
                placeholder="Select NAAC grade"
                onValueChange={(value) => {
                  updateAccreditation({ naac_grade: value as NaacGrade });
                  clearError("naac_grade");
                }}
                onBlur={() => validateOnBlur("accreditation", "naac_grade")}
              />
              <Select
                id="accreditation-nba-status"
                label="NBA status"
                required
                options={[...NBA_OPTIONS]}
                value={accreditation?.nba_status ?? ""}
                error={errors.nba_status}
                placeholder="Select NBA status"
                onValueChange={(value) => {
                  updateAccreditation({ nba_status: value as NbaStatus });
                  clearError("nba_status");
                }}
                onBlur={() => validateOnBlur("accreditation", "nba_status")}
              />
              <DatePicker
                id="accreditation-last-validated-on"
                label="Last validated on"
                value={accreditation?.last_validated_on ?? ""}
                onChange={(event) =>
                  updateAccreditation({ last_validated_on: event.target.value || null })
                }
              />
            </FormGroup>

            <FormGroup
              title="Public disclosure"
              description="The mandatory disclosure page must be publicly reachable over http or https."
            >
              <Input
                id="accreditation-mandatory-disclosure-url"
                label="Mandatory disclosure URL"
                type="url"
                required
                value={form.mandatory_disclosure_url ?? ""}
                error={errors.mandatory_disclosure_url}
                placeholder="https://example.edu/mandatory-disclosure"
                hint="A public page or document on the institution website."
                onChange={(event) => {
                  updateForm((current) => ({
                    ...current,
                    mandatory_disclosure_url: event.target.value,
                  }));
                  clearError("mandatory_disclosure_url");
                }}
                onBlur={() => validateOnBlur("accreditation", "mandatory_disclosure_url")}
                containerClassName="sm:col-span-2"
              />
            </FormGroup>
          </div>
        );
      case "programs":
        return (
          <ProgramEditor
            applicationId={application.id}
            token={token ?? ""}
            programs={application.programs}
            onChanged={() => {
              void queryClient.invalidateQueries({
                queryKey: ["application", application.id],
              });
            }}
          />
        );
      case "documents":
        return (
          <div className="space-y-5">
            <div className="rounded-input border border-line bg-paper p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-13 font-medium text-ink">Required documents</p>
                  <p className="mt-0.5 text-12 text-ink-500">
                    {uploadedDocs} of {mandatoryDocs.length} mandatory documents uploaded. Each
                    upload receives an immediate AI verification result.
                  </p>
                </div>
                <span className="text-13 font-semibold tabular-nums text-ink">
                  {documentPercent}%
                </span>
              </div>
              <ProgressBar
                label="Document checklist"
                value={documentPercent}
                status={documentPercent === 100 ? "ok" : "watch"}
                showValue={false}
                className="mt-3"
              />
            </div>
            {checklistQuery.isError ? (
              <p className="rounded-input border border-breach bg-breach-soft p-3 text-13 text-breach-strong">
                The document checklist could not be loaded.
              </p>
            ) : (
              <DocumentChecklist
                applicationId={application.id}
                token={token ?? ""}
                documents={checklist?.documents ?? []}
                disabled={submitting}
                onUploaded={() => {
                  setServerMissing([]);
                  void queryClient.invalidateQueries({
                    queryKey: ["checklist", applicationId],
                  });
                }}
              />
            )}

            <section className="rounded-input border border-line bg-paper p-4">
              <div className="flex items-start gap-2.5">
                <Download aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-ink-500" />
                <div>
                  <h3 className="text-13 font-semibold text-ink">Downloadable document shells</h3>
                  <p className="mt-0.5 text-12 leading-5 text-ink-500">
                    Printable templates generated from this application. The Affidavit 2 shell
                    carries a fictional-data note and an e-stamp fee note for Rs.100; complete the
                    stamp duty and notarisation before uploading the signed copy.
                  </p>
                </div>
              </div>
              {shellsQuery.isPending ? (
                <p className="mt-3 text-12 text-ink-500">Loading document shells…</p>
              ) : shellsQuery.isError ? (
                <p className="mt-3 text-12 text-breach-strong">
                  The document shells could not be listed.
                </p>
              ) : (
                <ul className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
                  {Object.entries(shellsQuery.data ?? {}).map(([code, label]) => (
                    <li key={code}>
                      <Button
                        variant="secondary"
                        size="sm"
                        className="w-full justify-start"
                        onClick={() => void handleShellDownload(code)}
                        disabled={downloadingShell === code}
                      >
                        {downloadingShell === code ? (
                          <Loader2 aria-hidden="true" className="size-4 animate-spin" />
                        ) : (
                          <Download aria-hidden="true" className="size-4" />
                        )}
                        {label}
                      </Button>
                    </li>
                  ))}
                </ul>
              )}
              {shellError ? (
                <p role="alert" className="mt-2 text-12 text-breach-strong">
                  {shellError}
                </p>
              ) : null}
            </section>
          </div>
        );
      case "payment": {
        const fee = feeQuery.data;
        const deposit = securityDepositQuery.data;
        return (
          <div className="space-y-5">
            <div className="rounded-input border border-line bg-paper p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-13 font-medium text-ink">TER and committee charges</p>
                  <p className="mt-0.5 text-12 text-ink-500">
                    Computed from the fee table for this application type and the annual factor.
                    The amounts are integer paise and carry their APH clause.
                  </p>
                </div>
                <span
                  className={
                    fee?.is_paid
                      ? "rounded-pill bg-ok-soft px-2.5 py-1 text-12 font-medium text-ok-strong"
                      : "rounded-pill bg-watch-soft px-2.5 py-1 text-12 font-medium text-watch-strong"
                  }
                >
                  {fee?.is_paid ? "Paid" : "Payment due"}
                </span>
              </div>
            </div>

            {fee?.late_submission ? (
              <section className="rounded-input border border-watch bg-watch-soft p-4 text-13 leading-5 text-watch-strong">
                <p className="flex items-center gap-2 font-medium">
                  <AlertCircle aria-hidden="true" className="size-4" />
                  Late submission
                </p>
                <p className="mt-1">
                  This application is after the Public Notice cut-off. It is accepted but flagged
                  and the late penalty is included below; it will be moved to the next academic
                  year (APH 2.3.3).
                </p>
              </section>
            ) : null}

            {feeQuery.isPending ? (
              <p className="flex items-center gap-2 text-13 text-ink-500">
                <Loader2 aria-hidden="true" className="size-4 animate-spin" />
                Computing the fee position…
              </p>
            ) : feeQuery.isError ? (
              <p className="rounded-input border border-breach bg-breach-soft p-3 text-13 text-breach-strong">
                The fee position could not be loaded. Retry before submitting.
              </p>
            ) : fee ? (
              <section className="rounded-input border border-line bg-surface p-4">
                <ul className="divide-y divide-line">
                  {fee.lines.length === 0 ? (
                    <li className="py-2 text-13 text-ink-700">
                      No TER is due for this application type.
                    </li>
                  ) : (
                    fee.lines.map((line) => (
                      <li
                        key={line.item_code}
                        className="flex items-start justify-between gap-3 py-2.5"
                      >
                        <div className="min-w-0">
                          <p className="text-13 font-medium text-ink">{line.label}</p>
                          <p className="mt-0.5 text-12 text-ink-500">
                            {line.units} × {formatInr(line.unit_amount_paise)}{" "}
                            {humanizeEnum(line.unit).toLowerCase()} · {line.apH_clause}
                            {line.needs_verification ? " · needs verification" : ""}
                          </p>
                        </div>
                        <span className="shrink-0 text-13 font-semibold tabular-nums text-ink">
                          {formatInr(line.amount_paise)}
                        </span>
                      </li>
                    ))
                  )}
                </ul>
                <dl className="mt-3 grid grid-cols-2 gap-2 border-t border-line pt-3 text-13 sm:grid-cols-4">
                  <div>
                    <dt className="text-12 text-ink-500">Total</dt>
                    <dd className="font-semibold tabular-nums text-ink">
                      {formatInr(fee.total_paise)}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-12 text-ink-500">Paid</dt>
                    <dd className="font-semibold tabular-nums text-ink">
                      {formatInr(fee.paid_paise)}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-12 text-ink-500">Refunded</dt>
                    <dd className="font-semibold tabular-nums text-ink">
                      {formatInr(fee.refunded_paise)}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-12 text-ink-500">Due</dt>
                    <dd className="font-semibold tabular-nums text-ink">
                      {formatInr(fee.due_paise)}
                    </dd>
                  </div>
                </dl>

                {fee.ter_receipt_no ? (
                  <p className="mt-3 rounded-input border border-ok bg-ok-soft p-3 text-12 text-ok-strong">
                    TER receipt {fee.ter_receipt_no}
                    {fee.ter_paid_at ? ` · paid ${formatDate(fee.ter_paid_at)}` : ""}
                  </p>
                ) : (
                  <div className="mt-3 rounded-input border border-line bg-paper p-3">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div>
                        <p className="text-13 font-medium text-ink">Simulated payment gateway</p>
                        <p className="mt-0.5 text-12 text-ink-500">
                          No card details are collected. The demo gateway records one immutable
                          FeeTransaction per line and issues a TER receipt.
                        </p>
                      </div>
                      <Button
                        onClick={() => void handlePay()}
                        disabled={paying || fee.due_paise === 0}
                      >
                        {paying ? (
                          <Loader2 aria-hidden="true" className="size-4 animate-spin" />
                        ) : (
                          <CreditCard aria-hidden="true" className="size-4" />
                        )}
                        {paying ? "Processing…" : `Pay ${formatInr(fee.due_paise)}`}
                      </Button>
                    </div>
                  </div>
                )}

                {fee.notes.length > 0 ? (
                  <ul className="mt-3 space-y-1 text-12 leading-5 text-ink-500">
                    {fee.notes.map((note) => (
                      <li key={note}>• {note}</li>
                    ))}
                  </ul>
                ) : null}
              </section>
            ) : null}

            {deposit && deposit.lines.length > 0 ? (
              <section className="rounded-input border border-line bg-surface p-4">
                <h3 className="text-13 font-semibold text-ink">Security Deposit (Table 1.4)</h3>
                <p className="mt-0.5 text-12 leading-5 text-ink-500">
                  Payable after the LoA. The deposit doubles when the building or land is leased.
                  {deposit.intimation_on
                    ? ` Intimation date ${formatDate(deposit.intimation_on)}.`
                    : ""}
                </p>
                <ul className="mt-3 divide-y divide-line">
                  {deposit.lines.map((line) => (
                    <li
                      key={`${line.programme_family}-${line.level}`}
                      className="flex items-start justify-between gap-3 py-2.5"
                    >
                      <div className="min-w-0">
                        <p className="text-13 font-medium text-ink">
                          {humanizeEnum(line.programme_family)} · {humanizeEnum(line.level)}
                        </p>
                        <p className="mt-0.5 text-12 text-ink-500">
                          Base {formatInr(line.base_paise)}
                          {line.leased ? " · doubled for leased premises" : ""}
                          {line.penalty_percent > 0
                            ? ` · ${line.penalty_percent}% penalty window`
                            : ""}{" "}
                          · {line.apH_clause}
                        </p>
                      </div>
                      <span className="shrink-0 text-13 font-semibold tabular-nums text-ink">
                        {formatInr(line.total_due_paise)}
                      </span>
                    </li>
                  ))}
                </ul>
                <p className="mt-3 text-12 text-ink-500">{deposit.penalty_windows}</p>
              </section>
            ) : null}

            <div className="rounded-input border border-line bg-paper p-4 text-12 leading-5 text-ink-700">
              <p className="font-medium text-ink">Refund rules</p>
              <p className="mt-1">
                A rejected application with no appeal is refunded after retaining Rs.0.60 lakh; a
                revoked approval is refunded after retaining Rs.0.25 lakh (APH 1.4.2h). Refunds are
                recorded as separate transactions and are never adjusted into a later payment.
              </p>
            </div>
          </div>
        );
      }
      case "review":
        return (
          <div className="space-y-5">
            <div className="rounded-input border border-line bg-paper p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-13 font-medium text-ink">Submission review</p>
                  <p className="mt-0.5 text-12 text-ink-500">
                    Check the details below. Blocking issues link directly to the field that
                    needs attention.
                  </p>
                </div>
                <span className="text-20 font-serif font-semibold text-ink">
                  {checklist?.percentage ?? 0}%
                </span>
              </div>
            </div>

            <section className="rounded-input border border-breach bg-breach-soft p-4 text-13 leading-5 text-breach-strong">
              <p className="flex items-center gap-2 font-semibold">
                <ShieldAlert aria-hidden="true" className="size-4" />
                Warning: penal action for false information
              </p>
              <p className="mt-1">
                Under APH 2.3.5b and 7.4a, submitting false information or a fabricated document
                can lead to rejection, withdrawal of approval, debarment and other penal action.
                Verify every declaration, figure and upload before you submit.
              </p>
            </section>

            <ReviewSection title="Institution profile">
              <ReviewField label="Head of institution" value={valueOrDash(profile?.head_name)} />
              <ReviewField label="Contact email" value={valueOrDash(profile?.contact_email)} />
              <ReviewField label="Contact phone" value={valueOrDash(profile?.contact_phone)} />
              <ReviewField label="Website" value={valueOrDash(profile?.website)} />
              <ReviewField
                label="Address"
                value={
                  [
                    profile?.address_line1,
                    profile?.address_line2,
                    profile?.city,
                    profile?.state,
                    profile?.pin_code,
                  ]
                    .filter(Boolean)
                    .join(", ") || "—"
                }
              />
            </ReviewSection>

            <ReviewSection title="Infrastructure and faculty">
              <ReviewField
                label="Land area"
                value={`${valueOrDash(infrastructure?.land_area)} sq. m`}
              />
              <ReviewField
                label="Built-up area"
                value={`${valueOrDash(infrastructure?.built_up_area)} sq. m`}
              />
              <ReviewField label="Laboratories" value={valueOrDash(infrastructure?.labs)} />
              <ReviewField label="Library collection" value={valueOrDash(infrastructure?.library)} />
              <ReviewField label="Hostel capacity" value={valueOrDash(infrastructure?.hostel)} />
              <ReviewField label="Total faculty" value={valueOrDash(faculty?.total)} />
              <ReviewField
                label="Faculty by cadre"
                value={`${valueOrDash(faculty?.professors)} professors · ${valueOrDash(
                  faculty?.associate_professors,
                )} associate · ${valueOrDash(faculty?.assistant_professors)} assistant`}
              />
              <ReviewField
                label="Ratios"
                value={`${valueOrDash(
                  faculty?.student_faculty_ratio,
                )} students/faculty · ${valueOrDash(faculty?.phd_faculty_ratio)}% with PhD`}
              />
            </ReviewSection>

            <ReviewSection title="Finance and accreditation">
              <ReviewField label="Tuition fee" value={`₹ ${valueOrDash(finance?.tuition_fee)}`} />
              <ReviewField
                label="Development fee"
                value={`₹ ${valueOrDash(finance?.development_fee)}`}
              />
              <ReviewField label="Other fees" value={`₹ ${valueOrDash(finance?.other_fees)}`} />
              <ReviewField label="Declared balance" value={`₹ ${valueOrDash(finance?.balance)}`} />
              <ReviewField label="NAAC grade" value={valueOrDash(accreditation?.naac_grade)} />
              <ReviewField
                label="NBA status"
                value={
                  accreditation?.nba_status ? humanizeEnum(accreditation.nba_status) : "—"
                }
              />
              <ReviewField
                label="Mandatory disclosure URL"
                value={valueOrDash(form.mandatory_disclosure_url)}
              />
              <ReviewField
                label="Last validated"
                value={formatDate(accreditation?.last_validated_on)}
              />
            </ReviewSection>

            <section className="rounded-input border border-line p-4">
              <div className="flex items-center justify-between gap-3">
                <h3 className="text-13 font-semibold text-ink">Programmes</h3>
                <span className="text-12 text-ink-500">
                  {application.programs.length} recorded
                </span>
              </div>
              {application.programs.length === 0 ? (
                <p className="mt-2 text-12 text-ink-500">
                  No programmes recorded. Programmes do not block submission in this prototype.
                </p>
              ) : (
                <ul className="mt-3 space-y-2">
                  {application.programs.map((program) => (
                    <li key={program.id} className="text-13 text-ink">
                      <span className="font-medium">{program.program_name}</span>{" "}
                      <span className="text-ink-500">
                        · {programLevelLabel(program.level)} · intake {program.intake} ·{" "}
                        {program.faculty_count} faculty
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </section>

            <section className="rounded-input border border-line p-4">
              <div className="flex items-center justify-between gap-3">
                <h3 className="text-13 font-semibold text-ink">Document checklist</h3>
                <span className="text-12 text-ink-500">
                  {uploadedDocs}/{mandatoryDocs.length} mandatory
                </span>
              </div>
              <ul className="mt-3 space-y-2">
                {(checklist?.documents ?? []).map((document) => (
                  <li
                    key={document.doc_type}
                    className="rounded-input border border-line bg-paper p-3"
                  >
                    <div className="flex items-start gap-2.5">
                      {document.uploaded && document.signed_with_dsc !== false ? (
                        <CheckCircle2
                          aria-hidden="true"
                          className="mt-0.5 size-4 shrink-0 text-ok"
                        />
                      ) : (
                        <FileWarning
                          aria-hidden="true"
                          className={
                            document.mandatory || document.signed_with_dsc === false
                              ? "mt-0.5 size-4 shrink-0 text-watch"
                              : "mt-0.5 size-4 shrink-0 text-ink-300"
                          }
                        />
                      )}
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="text-13 font-medium text-ink">{document.label}</p>
                          {!document.mandatory ? (
                            <span className="text-11 text-ink-500">Optional</span>
                          ) : null}
                        </div>
                        <p className="mt-0.5 break-all text-12 text-ink-500">
                          {document.uploaded
                            ? `${document.filename} · ${formatBytes(
                                document.size_bytes,
                              )} · version ${document.version}`
                            : document.mandatory
                              ? "Missing"
                              : "Not uploaded"}
                        </p>
                        {document.uploaded && document.signed_with_dsc === false ? (
                          <p className="mt-1 text-12 font-medium text-breach-strong">
                            Invalid: uploaded without a valid DSC signature (APH 1.4.6).
                          </p>
                        ) : null}
                        {document.uploaded ? (
                          <DocumentVerificationBadge
                            status={document.verification_status}
                            reason={document.verification_reason}
                            className="mt-2"
                          />
                        ) : null}
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            </section>

            {blockingIssues.length > 0 ? (
              <section className="rounded-input border border-watch bg-watch-soft p-4">
                <div className="flex items-center gap-2">
                  <AlertCircle aria-hidden="true" className="size-4 text-watch-strong" />
                  <h3 className="text-13 font-semibold text-watch-strong">
                    {blockingIssues.length} blocking issue
                    {blockingIssues.length === 1 ? "" : "s"} still needed
                  </h3>
                </div>
                <p className="mt-1 text-12 leading-5 text-watch-strong">
                  Select an issue to jump to the field or document, then return here to submit.
                </p>
                <ul className="mt-3 space-y-1">
                  {blockingIssues.map((item) => (
                    <li key={item.code}>
                      <button
                        type="button"
                        onClick={() => jumpToIssue(item)}
                        className="group flex w-full items-start justify-between gap-3 rounded-input px-2 py-2 text-left text-12 leading-5 text-watch-strong transition-colors hover:bg-surface focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
                      >
                        <span className="min-w-0">
                          <span className="font-medium">{item.section}:</span> {item.message}
                        </span>
                        <span className="flex shrink-0 items-center gap-1 font-medium">
                          Fix
                          <ArrowRight
                            aria-hidden="true"
                            className="size-3.5 transition-transform group-hover:translate-x-0.5"
                          />
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              </section>
            ) : (
              <section className="rounded-input border border-ok bg-ok-soft p-4">
                <p className="flex items-center gap-2 text-13 font-medium text-ok-strong">
                  <CheckCircle2 aria-hidden="true" className="size-4" />
                  Every required field and mandatory document is complete.
                </p>
              </section>
            )}

            {complianceQuery.data && complianceQuery.data.failed_count > 0 ? (
              <section className="rounded-input border border-line bg-paper p-4">
                <p className="text-13 font-medium text-ink">Predicted compliance is advisory</p>
                <p className="mt-1 text-12 leading-5 text-ink-500">
                  {complianceQuery.data.failed_count} configured rule
                  {complianceQuery.data.failed_count === 1 ? "" : "s"} currently fail. You can
                  still submit, but review the live compliance preview and explain any accepted
                  exception during scrutiny.
                </p>
              </section>
            ) : null}

            <section className="rounded-input border border-line p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h3 className="text-13 font-semibold text-ink">Fee and payment</h3>
                  <p className="mt-0.5 text-12 leading-5 text-ink-500">
                    {feeQuery.data
                      ? `Total ${formatInr(feeQuery.data.total_paise)} · paid ${formatInr(
                          feeQuery.data.paid_paise,
                        )} · due ${formatInr(feeQuery.data.due_paise)}`
                      : "The fee position is loading."}
                  </p>
                </div>
                <Button variant="secondary" size="sm" onClick={() => goToStep("payment")}>
                  <CreditCard aria-hidden="true" className="size-4" />
                  Payment step
                </Button>
              </div>
              {!feePaid ? (
                <p className="mt-2 rounded-input border border-watch bg-watch-soft p-3 text-12 text-watch-strong">
                  The TER must be paid before the server will accept this submission. Submit stays
                  disabled until the receipt is recorded.
                </p>
              ) : (
                <p className="mt-2 flex items-center gap-1.5 text-12 text-ok-strong">
                  <CheckCircle2 aria-hidden="true" className="size-4" />
                  TER paid
                  {feeQuery.data?.ter_receipt_no
                    ? ` · receipt ${feeQuery.data.ter_receipt_no}`
                    : ""}
                </p>
              )}
            </section>

            <DeficiencyReportPanel
              applicationId={application.id}
              token={token ?? ""}
              autoLoad
            />

            <div className="rounded-input border border-line bg-paper p-4 text-12 leading-5 text-ink-700">
              <p className="font-medium text-ink">Submission and SLA</p>
              <p className="mt-1">
                The application-stage SLA duration is configuration data. On submission the
                server sets the due date from that value and records a workflow event and audit
                entry.
              </p>
            </div>
          </div>
        );
    }
  };

  return (
    <>
      <Breadcrumbs
        items={[
          { label: applicationsLabel, to: "/applications" },
          { label: title, to: `/applications/${application.id}` },
          { label: "Workspace" },
        ]}
      />

      <PageHeader
        eyebrow="Institution workspace"
        title={title}
        description={`${application.institution.name} · ${humanizeEnum(
          application.application_type,
        )} · ${application.academic_year}`}
        actions={
          <div className="flex flex-wrap items-center gap-3">
            <ApplicationStatusBadge status={application.status} />
            <button
              type="button"
              onClick={() => applySaveBeforeLeave(saveNow, navigate)}
              className="inline-flex items-center gap-1.5 text-12 font-medium text-ink-700 underline-offset-4 hover:text-ink hover:underline"
            >
              <ArrowLeft aria-hidden="true" className="size-4" />
              Back to applications
            </button>
          </div>
        }
      />

      <div className="grid grid-cols-1 items-start gap-5 lg:grid-cols-[200px_minmax(0,1fr)] xl:grid-cols-[200px_minmax(0,1fr)_288px] xl:gap-6">
        <aside className="hidden min-w-0 lg:sticky lg:top-24 lg:block">
          <ApplicationProgressRail
            steps={WIZARD_STEPS}
            currentIndex={currentIndex}
            completion={stepCompletion}
            percentage={checklist?.percentage ?? 0}
            completedItems={checklist?.completed_items ?? 0}
            requiredItems={checklist?.required_items ?? 0}
            saveState={saveState}
            saveError={saveError}
            lastSavedAt={lastSavedAt}
            onNavigate={goToStep}
          />
        </aside>

        <div className="min-w-0 space-y-5">
          <section className="rounded-panel border border-line bg-surface p-4 lg:hidden">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-12 font-semibold uppercase tracking-[0.12em] text-ink-500">
                  Application progress
                </p>
                <p className="mt-1 text-13 font-medium text-ink">
                  Step {currentIndex + 1} of {WIZARD_STEPS.length}: {currentStep.label}
                </p>
              </div>
              <span className="text-18 font-serif font-semibold tabular-nums text-ink">
                {checklist?.percentage ?? 0}%
              </span>
            </div>
            <ProgressBar
              label="Application completeness"
              value={checklist?.percentage ?? 0}
              status={checklist?.percentage === 100 ? "ok" : "info"}
              showValue={false}
              className="mt-3"
            />
            <div className="mt-3">
              <SaveStatus state={saveState} error={saveError} lastSavedAt={lastSavedAt} />
            </div>
          </section>

          <section className="rounded-panel border border-line bg-surface">
            <div className="border-b border-line px-5 py-4 sm:px-6">
              <p className="text-12 font-semibold uppercase tracking-[0.12em] text-ink-500">
                Step {currentIndex + 1} of {WIZARD_STEPS.length}
              </p>
              <h2 className="mt-1 font-serif text-22 font-semibold text-ink">
                {currentStep.label}
              </h2>
              <p className="mt-1 text-13 text-ink-500">{currentStep.description}</p>
            </div>

            <div className="px-5 py-5 sm:px-6">{stepContent()}</div>

            <div className="flex flex-wrap items-center justify-between gap-3 border-t border-line px-5 py-4 sm:px-6">
              <Button
                variant="secondary"
                size="sm"
                onClick={goBack}
                disabled={currentIndex === 0 || submitting}
              >
                <ArrowLeft aria-hidden="true" className="size-4" />
                Previous
              </Button>
              {isReview ? (
                <div className="flex flex-col items-end gap-1.5">
                  <Button
                    onClick={() => void handleSubmit()}
                    disabled={submitDisabled}
                    aria-describedby="submit-readiness"
                  >
                    {submitting ? (
                      <Loader2 aria-hidden="true" className="size-4 animate-spin" />
                    ) : (
                      <Send aria-hidden="true" className="size-4" />
                    )}
                    {submitting ? "Submitting…" : "Submit application"}
                  </Button>
                  <p
                    id="submit-readiness"
                    className="max-w-sm text-right text-11 leading-4 text-ink-500"
                  >
                    {submitHelper}
                  </p>
                </div>
              ) : (
                <Button onClick={goNext} disabled={submitting}>
                  Next
                  <ArrowRight aria-hidden="true" className="size-4" />
                </Button>
              )}
            </div>
          </section>

          <div className="xl:hidden">{renderCompliancePanel()}</div>
        </div>

        <aside className="hidden min-w-0 xl:sticky xl:top-24 xl:block xl:max-h-[calc(100vh-7rem)] xl:overflow-y-auto xl:pr-1">
          {renderCompliancePanel()}
        </aside>
      </div>
    </>
  );
}

function applySaveBeforeLeave(
  saveNow: () => Promise<boolean>,
  navigate: (path: string) => void,
) {
  void saveNow().then((saved) => {
    if (saved) {
      navigate("/applications");
    }
  });
}
