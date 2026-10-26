import {
  createContext,
  useContext,
  useEffect,
  useState,
  type FormEvent,
  type ReactNode,
} from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2 } from "lucide-react";

import {
  Button,
  DatePicker,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  Input,
  Select,
  StatusPill,
  Textarea,
  useToast,
} from "../ui";
import {
  ApiError,
  getAllowedActions,
  getWorkflowDefinition,
  listCommitteeMembers,
  listDeficiencies,
  performWorkflowAction,
  type AllowedAction,
  type AllowedActionRequirement,
  type ApplicationDetail,
  type DecisionOutcome,
  type InspectionRecommendation,
  type WorkflowActionPayload,
  type WorkflowDefinition,
} from "../../lib/api";
import { formatDate } from "../../lib/format";

const DEFICIENCY_CATEGORIES = [
  { value: "DOCUMENT", label: "Document" },
  { value: "FACULTY", label: "Faculty" },
  { value: "INFRASTRUCTURE", label: "Infrastructure" },
  { value: "FINANCE", label: "Finance" },
  { value: "OTHER", label: "Other" },
];

const RECOMMENDATION_OPTIONS: {
  value: InspectionRecommendation;
  label: string;
}[] = [
  { value: "APPROVE", label: "Recommend approval" },
  { value: "DEFICIENCY", label: "Record deficiencies" },
  { value: "REJECT", label: "Recommend rejection" },
];

const DECISION_OPTIONS: { value: DecisionOutcome; label: string }[] = [
  { value: "LOA", label: "Letter of Approval (LoA)" },
  { value: "EOA", label: "Extension of Approval (EoA)" },
  { value: "LOD", label: "Letter of Deficiency (LoD)" },
  { value: "LOR", label: "Letter of Rejection (LoR)" },
];

const SAC_RECOMMENDATION_OPTIONS: {
  value: DecisionOutcome;
  label: string;
}[] = [
  { value: "RECOMMEND", label: "Recommend the appeal be allowed" },
  { value: "NOT_RECOMMEND", label: "Recommend the appeal be dismissed" },
];

const SHC_OUTCOME_OPTIONS: { value: DecisionOutcome; label: string }[] = [
  { value: "RECOMMEND", label: "Deficiency closed — recommend approval" },
  { value: "NOT_RECOMMEND", label: "Deficiency stands — do not recommend" },
];

/** Dialog body the selected action needs, beyond its server-declared form. */
type DialogKind =
  | AllowedActionRequirement
  | "observations"
  | "sac_recommendation"
  | "appeal"
  | "issue_letter"
  | "list_for_ec";

function dialogKind(action: AllowedAction): DialogKind {
  switch (action.action) {
    case "pay_security_deposit":
      return "deposit";
    case "observations":
      return "observations";
    case "sac_recommend":
      return "sac_recommendation";
    case "council_final":
      return "decision";
    case "file_appeal":
      return "appeal";
    case "issue_letter":
    case "issue_loa":
    case "issue_eoa":
    case "issue_lod":
    case "issue_lor":
      return "issue_letter";
    case "list_for_ec":
      return "list_for_ec";
    default:
      return action.requires;
  }
}

const OUTCOME_FOR_GUARD: Record<string, DecisionOutcome> = {
  decision_loa: "LOA",
  decision_eoa: "EOA",
  decision_lod: "LOD",
  decision_lor: "LOR",
  final_outcome_loa: "LOA",
  final_outcome_lod: "LOD",
  final_outcome_lor: "LOR",
  ratified_outcome_loa: "LOA",
  ratified_outcome_lod: "LOD",
  ratified_outcome_lor: "LOR",
};

function matchingTransitions(
  definition: WorkflowDefinition | undefined,
  action: AllowedAction | null,
  status: ApplicationDetail["status"],
) {
  if (!definition || !action) {
    return [];
  }
  return definition.transitions.filter(
    (transition) =>
      transition.action === action.action && transition.from_state === status,
  );
}

/** Decision outcomes the configured guards allow for this action. */
function decisionOptionsFor(
  definition: WorkflowDefinition | undefined,
  action: AllowedAction | null,
  status: ApplicationDetail["status"],
): { value: DecisionOutcome; label: string }[] {
  const outcomes = new Set<DecisionOutcome>();
  for (const transition of matchingTransitions(definition, action, status)) {
    for (const guard of transition.guard_expr) {
      const outcome = OUTCOME_FOR_GUARD[guard];
      if (outcome) {
        outcomes.add(outcome);
      }
    }
  }
  return outcomes.size === 0
    ? DECISION_OPTIONS
    : DECISION_OPTIONS.filter((option) => outcomes.has(option.value));
}

/** True when the selected edges require a closure outcome with the decision. */
function needsClosureOutcome(
  definition: WorkflowDefinition | undefined,
  action: AllowedAction | null,
  status: ApplicationDetail["status"],
): boolean {
  return matchingTransitions(definition, action, status).some((transition) =>
    transition.guard_expr.includes("closure_outcome_present"),
  );
}

export interface WorkflowPrefill {
  /** Category of a prefilled deficiency item. */
  category?: string;
  /** Description of a prefilled deficiency item. */
  description?: string;
  /** Deficiency selected in the close dialog. */
  deficiencyId?: string;
}

interface DeficiencyDraft {
  key: string;
  category: string;
  description: string;
  dueDate: string;
}

interface ReportDraft {
  infrastructure_ok: boolean;
  faculty_verified: boolean;
  lab_verified: boolean;
  observations: string;
  recommendation: InspectionRecommendation;
}

interface WorkflowActionsContextValue {
  /** Server-calculated actions available to the current role. */
  actions: AllowedAction[];
  findAction: (action: AllowedAction["action"]) => AllowedAction | undefined;
  openAction: (action: AllowedAction, prefill?: WorkflowPrefill) => void;
}

const WorkflowActionsContext =
  createContext<WorkflowActionsContextValue | null>(null);

export function useWorkflowActions(): WorkflowActionsContextValue {
  const value = useContext(WorkflowActionsContext);
  if (!value) {
    throw new Error(
      "useWorkflowActions must be used inside a WorkflowDialogHost",
    );
  }
  return value;
}

let draftSequence = 0;

function newDeficiencyDraft(): DeficiencyDraft {
  draftSequence += 1;
  return {
    key: `deficiency-draft-${draftSequence}`,
    category: "DOCUMENT",
    description: "",
    dueDate: isoDatePlusDays(7),
  };
}

function isoDatePlusDays(days: number): string {
  const date = new Date();
  date.setDate(date.getDate() + days);
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function localDateTimePlusDays(days: number): string {
  const date = new Date();
  date.setDate(date.getDate() + days);
  date.setHours(10, 0, 0, 0);
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  const hours = String(date.getHours()).padStart(2, "0");
  const minutes = String(date.getMinutes()).padStart(2, "0");
  return `${year}-${month}-${day}T${hours}:${minutes}`;
}

function emptyReport(): ReportDraft {
  return {
    infrastructure_ok: false,
    faculty_verified: false,
    lab_verified: false,
    observations: "",
    recommendation: "APPROVE",
  };
}

export function actionTone(
  tone: AllowedAction["tone"],
): "primary" | "secondary" | "destructive" {
  return tone === "danger" ? "destructive" : tone;
}

/**
 * Owns every workflow dialog for the case file. Any tab, header button or
 * table row can open an action dialog through the shared context, including
 * prefilled deficiency text drafted from failed compliance rules.
 */
export function WorkflowDialogHost({
  application,
  token,
  children,
}: {
  application: ApplicationDetail;
  token: string;
  children: ReactNode;
}) {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const applicationId = application.id;

  const allowedQuery = useQuery({
    queryKey: ["allowed-actions", applicationId],
    queryFn: () => getAllowedActions(token, applicationId),
    enabled: Boolean(token && applicationId),
    retry: false,
  });
  const deficienciesQuery = useQuery({
    queryKey: ["deficiencies", applicationId],
    queryFn: () => listDeficiencies(token, applicationId),
    enabled: Boolean(token && applicationId),
    retry: false,
  });

  const actions = allowedQuery.data?.actions ?? [];
  const scheduleAllowed = actions.some(
    (item) =>
      item.action === "constitute_evc" || item.requires === "inspection_schedule",
  );
  const committeeQuery = useQuery({
    queryKey: ["committee-members", applicationId],
    queryFn: () => listCommitteeMembers(token, applicationId),
    enabled: Boolean(token && applicationId && scheduleAllowed),
    retry: false,
  });
  // Decision options come from the configured transitions, not a stage list.
  const definitionQuery = useQuery({
    queryKey: ["workflow-definition", application.application_type],
    queryFn: () =>
      getWorkflowDefinition(token, application.application_type),
    enabled: Boolean(token && application.application_type),
    retry: false,
  });

  const [activeAction, setActiveAction] = useState<AllowedAction | null>(null);
  const [comment, setComment] = useState("");
  const [observations, setObservations] = useState("");
  const [decision, setDecision] = useState<DecisionOutcome | "">("");
  const [sacRecommendation, setSacRecommendation] = useState<DecisionOutcome | "">("");
  const [shcOutcome, setShcOutcome] = useState<DecisionOutcome | "">("");
  const [quorumMet, setQuorumMet] = useState(false);
  const [speakingOrder, setSpeakingOrder] = useState("");
  const [closureFailed, setClosureFailed] = useState(false);
  const [videoUrl, setVideoUrl] = useState("");
  const [videoMinutes, setVideoMinutes] = useState("30");
  const [depositReceiptNo, setDepositReceiptNo] = useState("");
  const [affidavit3Filed, setAffidavit3Filed] = useState(false);
  const [appealText, setAppealText] = useState("");
  const [approvedIntake, setApprovedIntake] = useState("");
  const [deficiencyDrafts, setDeficiencyDrafts] = useState<DeficiencyDraft[]>([]);
  const [responseDrafts, setResponseDrafts] = useState<Record<string, string>>({});
  const [selectedDeficiencyId, setSelectedDeficiencyId] = useState("");
  const [committeeId, setCommitteeId] = useState("");
  const [scheduledOn, setScheduledOn] = useState(localDateTimePlusDays(3));
  const [report, setReport] = useState<ReportDraft>(emptyReport);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const deficiencies = deficienciesQuery.data ?? [];
  const openDeficiencies = deficiencies.filter((item) => item.status === "OPEN");
  const respondedDeficiencies = deficiencies.filter(
    (item) => item.status === "RESPONDED",
  );
  const deficienciesPending = deficienciesQuery.isPending;
  const committeePending = committeeQuery.isPending;
  const committeeAvailable = committeeQuery.data ?? [];
  const activeKind = activeAction ? dialogKind(activeAction) : "none";
  const decisionOptions = decisionOptionsFor(
    definitionQuery.data,
    activeAction,
    application.status,
  );
  const showClosureOutcome = needsClosureOutcome(
    definitionQuery.data,
    activeAction,
    application.status,
  );

  useEffect(() => {
    if (
      activeAction?.requires === "inspection_schedule" &&
      !committeeId &&
      committeeAvailable.length
    ) {
      setCommitteeId(committeeAvailable[0].id);
    }
  }, [activeAction, committeeId, committeeAvailable]);

  const openAction = (action: AllowedAction, prefill?: WorkflowPrefill) => {
    setActiveAction(action);
    setComment("");
    setObservations("");
    setDecision("");
    setSacRecommendation("");
    setShcOutcome("");
    setQuorumMet(false);
    setSpeakingOrder("");
    setClosureFailed(false);
    setVideoUrl("");
    setVideoMinutes("30");
    setDepositReceiptNo("");
    setAffidavit3Filed(false);
    setAppealText("");
    setApprovedIntake("");
    setError(null);
    setDeficiencyDrafts(
      action.requires === "deficiencies"
        ? [
            {
              ...newDeficiencyDraft(),
              category: prefill?.category ?? "DOCUMENT",
              description: prefill?.description ?? "",
            },
          ]
        : [],
    );
    setResponseDrafts(
      action.requires === "responses"
        ? Object.fromEntries(
            deficiencies
              .filter((item) => item.status === "OPEN")
              .map((item) => [item.id, ""]),
          )
        : {},
    );
    setSelectedDeficiencyId(
      action.requires === "deficiency_id"
        ? (prefill?.deficiencyId ?? respondedDeficiencies[0]?.id ?? "")
        : "",
    );
    setCommitteeId(
      action.requires === "inspection_schedule"
        ? (committeeAvailable[0]?.id ?? "")
        : "",
    );
    setScheduledOn(localDateTimePlusDays(3));
    setReport(emptyReport());
  };

  const findAction = (action: AllowedAction["action"]) =>
    actions.find((item) => item.action === action);

  const closeDialog = () => {
    if (!submitting) {
      setActiveAction(null);
    }
  };

  const updateDeficiencyDraft = (
    key: string,
    field: keyof Omit<DeficiencyDraft, "key">,
    value: string,
  ) => {
    setDeficiencyDrafts((current) =>
      current.map((item) =>
        item.key === key ? { ...item, [field]: value } : item,
      ),
    );
  };

  const validate = (): string | null => {
    if (!activeAction) {
      return "No workflow action is selected.";
    }
    switch (activeKind) {
      case "deficiencies":
        if (deficiencyDrafts.length === 0) {
          return "Add at least one deficiency item.";
        }
        for (const item of deficiencyDrafts) {
          if (!item.description.trim()) {
            return "Describe every deficiency item.";
          }
          if (!item.dueDate) {
            return "Choose a due date for every deficiency item.";
          }
        }
        return null;
      case "responses":
        if (deficienciesPending) {
          return "Deficiencies are still loading. Try again in a moment.";
        }
        if (openDeficiencies.length === 0) {
          return "There are no open deficiencies to respond to.";
        }
        for (const item of openDeficiencies) {
          if (!(responseDrafts[item.id] ?? "").trim()) {
            return "Respond to every open deficiency in one submission.";
          }
        }
        return null;
      case "deficiency_id":
        return selectedDeficiencyId ? null : "Select a deficiency to close.";
      case "inspection_schedule":
        if (!committeeId) {
          return "Choose an inspection committee member.";
        }
        return scheduledOn ? null : "Choose the inspection date and time.";
      case "inspection_report":
        return report.observations.trim()
          ? null
          : "Add the inspection observations.";
      case "video":
        if (!videoUrl.trim()) {
          return "Enter the URL of the Expert Visit Committee video (APH 1.9f-g).";
        }
        if (!Number.isFinite(Number(videoMinutes)) || Number(videoMinutes) < 30) {
          return "The visit video must be at least 30 minutes long (APH 1.9f-g).";
        }
        return null;
      case "decision":
        if (!decision) {
          return "Choose the decision outcome.";
        }
        if (!quorumMet) {
          return "Confirm that the quorum was met (APH 1.10a).";
        }
        if (decision === "LOR" && !speakingOrder.trim()) {
          return "A rejection requires a Speaking Order with reasons (APH 2.24a).";
        }
        return null;
      case "shc_outcome":
        return shcOutcome ? null : "Record the SHC hearing outcome (APH 2.23.3).";
      case "deposit":
        if (!depositReceiptNo.trim()) {
          return "Enter the Security Deposit receipt number.";
        }
        if (!affidavit3Filed) {
          return "Confirm that Affidavit 3 was filed (APH 2.25f).";
        }
        return null;
      case "observations":
        return observations.trim()
          ? null
          : "Record the Regulation Bureau observations.";
      case "sac_recommendation":
        return sacRecommendation ? null : "Record the SAC recommendation.";
      case "appeal":
        return appealText.trim() ? null : "Set out the grounds of the appeal.";
      default:
        return null;
    }
  };

  const buildPayload = (): WorkflowActionPayload => {
    if (!activeAction) {
      return {};
    }
    const note = comment.trim();
    const base = note ? { comment: note } : {};
    const decisionBase = note ? { comment: note, notes: note } : {};
    switch (activeKind) {
      case "deficiencies":
        return {
          ...base,
          deficiencies: deficiencyDrafts.map((item) => ({
            category: item.category,
            description: item.description.trim(),
            due_date: item.dueDate,
          })),
        };
      case "responses":
        return {
          ...base,
          responses: openDeficiencies.map((item) => ({
            deficiency_id: item.id,
            response_text: (responseDrafts[item.id] ?? "").trim(),
          })),
        };
      case "deficiency_id":
        return { ...base, deficiency_id: selectedDeficiencyId };
      case "inspection_schedule":
        return {
          ...base,
          committee_id: committeeId,
          scheduled_on: new Date(scheduledOn).toISOString(),
        };
      case "inspection_report":
        return {
          ...base,
          report: {
            ...report,
            observations: report.observations.trim(),
          },
        };
      case "video":
        return {
          ...base,
          video_url: videoUrl.trim(),
          video_minutes: Number(videoMinutes),
        };
      case "decision":
        return {
          ...decisionBase,
          decision: decision || undefined,
          quorum_met: quorumMet,
          speaking_order: speakingOrder.trim() || undefined,
          ...(showClosureOutcome ? { closure_failed: closureFailed } : {}),
        };
      case "shc_outcome":
        return {
          ...decisionBase,
          shc_outcome: shcOutcome || undefined,
        };
      case "deposit":
        return {
          ...base,
          deposit_receipt_no: depositReceiptNo.trim(),
          affidavit3_filed: affidavit3Filed,
        };
      case "observations":
        return {
          ...decisionBase,
          observations: observations.trim(),
        };
      case "sac_recommendation":
        return {
          ...decisionBase,
          sac_recommendation: sacRecommendation || undefined,
        };
      case "appeal":
        return {
          ...decisionBase,
          appeal_text: appealText.trim(),
        };
      case "issue_letter":
        return {
          ...base,
          speaking_order: speakingOrder.trim() || undefined,
          observations: observations.trim() || undefined,
        };
      case "list_for_ec": {
        const parsed = Number(approvedIntake);
        return {
          ...base,
          approved_intake:
            approvedIntake.trim() && Number.isFinite(parsed) ? parsed : undefined,
        };
      }
      default:
        return base;
    }
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!activeAction) {
      return;
    }
    const validationError = validate();
    if (validationError) {
      setError(validationError);
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      const result = await performWorkflowAction(
        token,
        applicationId,
        activeAction.action,
        buildPayload(),
      );
      toast({
        title: activeAction.label,
        description: result.message,
        variant: "success",
      });
      setActiveAction(null);
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: ["application", applicationId],
        }),
        queryClient.invalidateQueries({
          queryKey: ["allowed-actions", applicationId],
        }),
        queryClient.invalidateQueries({
          queryKey: ["workflow-timeline", applicationId],
        }),
        queryClient.invalidateQueries({
          queryKey: ["deficiencies", applicationId],
        }),
        queryClient.invalidateQueries({
          queryKey: ["inspections", applicationId],
        }),
        queryClient.invalidateQueries({
          queryKey: ["compliance-preview", applicationId],
        }),
        queryClient.invalidateQueries({ queryKey: ["applications"] }),
      ]);
    } catch (actionError) {
      const message =
        actionError instanceof ApiError
          ? actionError.message
          : "The workflow action could not be applied.";
      setError(message);
      toast({
        title: "Action not applied",
        description: message,
        variant: "error",
      });
    } finally {
      setSubmitting(false);
    }
  };

  const contextValue: WorkflowActionsContextValue = {
    actions,
    findAction,
    openAction,
  };

  const renderDialogFields = () => {
    if (!activeAction) {
      return null;
    }
    switch (activeKind) {
      case "deficiencies":
        return (
          <div className="space-y-4">
            {deficiencyDrafts.map((item, index) => (
              <div
                key={item.key}
                className="space-y-3 rounded-input border border-line bg-paper p-3"
              >
                <div className="flex items-center justify-between gap-2">
                  <p className="text-13 font-semibold text-ink">
                    Deficiency {index + 1}
                  </p>
                  {deficiencyDrafts.length > 1 ? (
                    <Button
                      variant="quiet"
                      size="sm"
                      onClick={() =>
                        setDeficiencyDrafts((current) =>
                          current.filter((draft) => draft.key !== item.key),
                        )
                      }
                    >
                      Remove
                    </Button>
                  ) : null}
                </div>
                <Select
                  label="Category"
                  options={DEFICIENCY_CATEGORIES}
                  value={item.category}
                  onValueChange={(value) =>
                    updateDeficiencyDraft(item.key, "category", value)
                  }
                />
                <Textarea
                  label="Description"
                  value={item.description}
                  onChange={(event) =>
                    updateDeficiencyDraft(
                      item.key,
                      "description",
                      event.target.value,
                    )
                  }
                  placeholder="Describe the gap the institution must address."
                  required
                />
                <DatePicker
                  label="Due date"
                  value={item.dueDate}
                  min={isoDatePlusDays(0)}
                  onChange={(event) =>
                    updateDeficiencyDraft(item.key, "dueDate", event.target.value)
                  }
                  required
                />
              </div>
            ))}
            <Button
              variant="secondary"
              size="sm"
              onClick={() =>
                setDeficiencyDrafts((current) => [
                  ...current,
                  newDeficiencyDraft(),
                ])
              }
            >
              Add another deficiency
            </Button>
          </div>
        );
      case "responses":
        return openDeficiencies.length === 0 ? (
          <p className="rounded-input border border-line bg-paper p-3 text-13 text-ink-700">
            There are no open deficiencies to respond to.
          </p>
        ) : (
          <div className="space-y-4">
            {openDeficiencies.map((item) => (
              <div
                key={item.id}
                className="space-y-2 rounded-input border border-line bg-paper p-3"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <StatusPill status="breach">{item.category}</StatusPill>
                  <span className="text-12 text-ink-500">
                    Due {formatDate(item.due_date)}
                  </span>
                </div>
                <p className="text-13 leading-5 text-ink-700">
                  {item.description}
                </p>
                <Textarea
                  label="Institution response"
                  value={responseDrafts[item.id] ?? ""}
                  onChange={(event) =>
                    setResponseDrafts((current) => ({
                      ...current,
                      [item.id]: event.target.value,
                    }))
                  }
                  placeholder="Explain how the deficiency has been addressed."
                  required
                />
              </div>
            ))}
          </div>
        );
      case "deficiency_id":
        return respondedDeficiencies.length === 0 ? (
          <p className="rounded-input border border-line bg-paper p-3 text-13 text-ink-700">
            There are no responded deficiencies waiting for closure.
          </p>
        ) : (
          <Select
            label="Deficiency to close"
            options={respondedDeficiencies.map((item) => ({
              value: item.id,
              label: `${item.category} — ${item.description.slice(0, 60)}`,
            }))}
            value={selectedDeficiencyId}
            onValueChange={setSelectedDeficiencyId}
            required
          />
        );
      case "inspection_schedule":
        return (
          <div className="space-y-4">
            {committeePending ? (
              <p className="text-13 text-ink-500">Loading committee members…</p>
            ) : committeeQuery.isError ? (
              <p className="rounded-input border border-breach bg-breach-soft p-3 text-13 text-breach-strong">
                Committee members could not be loaded.
              </p>
            ) : committeeAvailable.length === 0 ? (
              <p className="rounded-input border border-line bg-paper p-3 text-13 text-ink-700">
                No inspection committee members are available in this region.
              </p>
            ) : (
              <Select
                label="Inspection committee member"
                options={committeeAvailable.map((member) => ({
                  value: member.id,
                  label: `${member.name} · ${member.email}`,
                }))}
                value={committeeId}
                onValueChange={setCommitteeId}
                required
              />
            )}
            <Input
              type="datetime-local"
              label="Visit date and time"
              value={scheduledOn}
              onChange={(event) => setScheduledOn(event.target.value)}
              required
            />
          </div>
        );
      case "inspection_report":
        return (
          <div className="space-y-4">
            <fieldset className="space-y-2">
              <legend className="text-13 font-medium text-ink-700">
                Verified on site
              </legend>
              <label className="flex items-center gap-2 text-13 text-ink">
                <input
                  type="checkbox"
                  className="size-4 rounded border-line"
                  checked={report.infrastructure_ok}
                  onChange={(event) =>
                    setReport((current) => ({
                      ...current,
                      infrastructure_ok: event.target.checked,
                    }))
                  }
                />
                Infrastructure verified
              </label>
              <label className="flex items-center gap-2 text-13 text-ink">
                <input
                  type="checkbox"
                  className="size-4 rounded border-line"
                  checked={report.faculty_verified}
                  onChange={(event) =>
                    setReport((current) => ({
                      ...current,
                      faculty_verified: event.target.checked,
                    }))
                  }
                />
                Faculty verified
              </label>
              <label className="flex items-center gap-2 text-13 text-ink">
                <input
                  type="checkbox"
                  className="size-4 rounded border-line"
                  checked={report.lab_verified}
                  onChange={(event) =>
                    setReport((current) => ({
                      ...current,
                      lab_verified: event.target.checked,
                    }))
                  }
                />
                Laboratories verified
              </label>
            </fieldset>
            <Textarea
              label="Observations"
              value={report.observations}
              onChange={(event) =>
                setReport((current) => ({
                  ...current,
                  observations: event.target.value,
                }))
              }
              placeholder="Record the committee's findings from the visit."
              required
            />
            <Select
              label="Recommendation"
              options={RECOMMENDATION_OPTIONS}
              value={report.recommendation}
              onValueChange={(value) =>
                setReport((current) => ({
                  ...current,
                  recommendation: value as InspectionRecommendation,
                }))
              }
            />
          </div>
        );
      case "video":
        return (
          <div className="space-y-4">
            <Input
              label="Visit video URL"
              value={videoUrl}
              onChange={(event) => setVideoUrl(event.target.value)}
              placeholder="https://…"
              required
            />
            <Input
              type="number"
              min={30}
              max={600}
              label="Video length (minutes)"
              value={videoMinutes}
              onChange={(event) => setVideoMinutes(event.target.value)}
              hint="APH 1.9f-g requires at least 30 minutes of uninterrupted visit footage."
              required
            />
          </div>
        );
      case "decision":
        return (
          <div className="space-y-4">
            <Select
              label="Decision outcome"
              options={decisionOptions}
              value={decision}
              onValueChange={(value) => setDecision(value as DecisionOutcome)}
              required
            />
            {showClosureOutcome ? (
              <label className="flex items-start gap-2 text-12 text-ink-700">
                <input
                  type="checkbox"
                  className="mt-0.5 size-4 rounded border-line"
                  checked={closureFailed}
                  onChange={(event) => setClosureFailed(event.target.checked)}
                />
                <span>
                  The linked closure did not succeed; grant the extension with zero
                  approved intake (APH 2.3.3h).
                </span>
              </label>
            ) : null}
            <label className="flex items-start gap-2 text-12 text-ink-700">
              <input
                type="checkbox"
                className="mt-0.5 size-4 rounded border-line"
                checked={quorumMet}
                onChange={(event) => setQuorumMet(event.target.checked)}
              />
              <span>The quorum required by APH 1.10a was met.</span>
            </label>
            {decision === "LOR" ? (
              <Textarea
                label="Speaking Order"
                value={speakingOrder}
                onChange={(event) => setSpeakingOrder(event.target.value)}
                placeholder="Record the reasons that must accompany a rejection (APH 2.24a)."
                required
              />
            ) : null}
            <Textarea
              label="Decision notes (optional)"
              value={comment}
              onChange={(event) => setComment(event.target.value)}
            />
          </div>
        );
      case "shc_outcome":
        return (
          <div className="space-y-4">
            <Select
              label="SHC hearing outcome"
              options={SHC_OUTCOME_OPTIONS}
              value={shcOutcome}
              onValueChange={(value) => setShcOutcome(value as DecisionOutcome)}
              required
            />
            <Textarea
              label="Hearing notes"
              value={comment}
              onChange={(event) => setComment(event.target.value)}
              placeholder="Summarise what the Standing Hearing Committee recorded."
            />
          </div>
        );
      case "deposit":
        return (
          <div className="space-y-4">
            <Input
              label="Security Deposit receipt number"
              value={depositReceiptNo}
              onChange={(event) => setDepositReceiptNo(event.target.value)}
              required
            />
            <label className="flex items-start gap-2 text-12 text-ink-700">
              <input
                type="checkbox"
                className="mt-0.5 size-4 rounded border-line"
                checked={affidavit3Filed}
                onChange={(event) => setAffidavit3Filed(event.target.checked)}
              />
              <span>Affidavit 3 has been filed with the Security Deposit (APH 2.25f).</span>
            </label>
            <Textarea
              label="Comment (optional)"
              value={comment}
              onChange={(event) => setComment(event.target.value)}
            />
          </div>
        );
      case "observations":
        return (
          <Textarea
            label="Regulation Bureau observations"
            value={observations}
            onChange={(event) => setObservations(event.target.value)}
            placeholder="Record the observations that go to the Executive Committee."
            required
          />
        );
      case "sac_recommendation":
        return (
          <div className="space-y-4">
            <Select
              label="SAC recommendation"
              options={SAC_RECOMMENDATION_OPTIONS}
              value={sacRecommendation}
              onValueChange={(value) =>
                setSacRecommendation(value as DecisionOutcome)
              }
              required
            />
            <Textarea
              label="Recommendation notes"
              value={comment}
              onChange={(event) => setComment(event.target.value)}
              placeholder="Record the reasons for the recommendation (APH 1.11d)."
            />
          </div>
        );
      case "appeal":
        return (
          <Textarea
            label="Grounds of appeal"
            value={appealText}
            onChange={(event) => setAppealText(event.target.value)}
            placeholder="Set out why the institution is appealing the decision."
            required
          />
        );
      case "issue_letter":
        return (
          <div className="space-y-4">
            <Textarea
              label="Speaking Order (required for an LoR)"
              value={speakingOrder}
              onChange={(event) => setSpeakingOrder(event.target.value)}
              placeholder="Reuse the Speaking Order recorded with the decision, if any."
            />
            <Textarea
              label="Letter observations (optional)"
              value={observations}
              onChange={(event) => setObservations(event.target.value)}
            />
            <Textarea
              label="Comment (optional)"
              value={comment}
              onChange={(event) => setComment(event.target.value)}
            />
          </div>
        );
      case "list_for_ec":
        return (
          <div className="space-y-4">
            <Input
              type="number"
              min={0}
              label="Approved intake (optional)"
              value={approvedIntake}
              onChange={(event) => setApprovedIntake(event.target.value)}
              hint="Leave blank to keep the intake proposed in the application."
            />
            <Textarea
              label="Comment (optional)"
              value={comment}
              onChange={(event) => setComment(event.target.value)}
            />
          </div>
        );
      default:
        return (
          <Textarea
            label={
              activeAction.action === "withdraw_application"
                ? "Reason / comment"
                : "Comment (optional)"
            }
            value={comment}
            onChange={(event) => setComment(event.target.value)}
            placeholder={
              activeAction.action === "withdraw_application"
                ? "Record why the institution is withdrawing."
                : "Add an optional note for the timeline."
            }
          />
        );
    }
  };

  return (
    <WorkflowActionsContext.Provider value={contextValue}>
      {children}
      <Dialog
        open={Boolean(activeAction)}
        onOpenChange={(open) => {
          if (!open) {
            closeDialog();
          }
        }}
      >
        <DialogContent className="max-w-xl">
          {activeAction ? (
            <form onSubmit={(event) => void handleSubmit(event)}>
              <DialogHeader>
                <DialogTitle>{activeAction.label}</DialogTitle>
                <DialogDescription>
                  {activeAction.description}
                </DialogDescription>
              </DialogHeader>

              <div className="mt-5 space-y-4">
                {renderDialogFields()}
                {error ? (
                  <p
                    role="alert"
                    className="rounded-input border border-breach bg-breach-soft p-3 text-13 text-breach-strong"
                  >
                    {error}
                  </p>
                ) : null}
              </div>

              <DialogFooter>
                <Button
                  type="button"
                  variant="secondary"
                  onClick={closeDialog}
                  disabled={submitting}
                >
                  Cancel
                </Button>
                <Button
                  type="submit"
                  variant={actionTone(activeAction.tone)}
                  disabled={submitting}
                >
                  {submitting ? (
                    <Loader2 aria-hidden="true" className="size-4 animate-spin" />
                  ) : null}
                  {submitting ? "Applying…" : activeAction.label}
                </Button>
              </DialogFooter>
            </form>
          ) : null}
        </DialogContent>
      </Dialog>
    </WorkflowActionsContext.Provider>
  );
}
