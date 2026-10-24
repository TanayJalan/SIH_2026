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
  listCommitteeMembers,
  listDeficiencies,
  performWorkflowAction,
  type AllowedAction,
  type ApplicationDetail,
  type InspectionRecommendation,
  type WorkflowActionPayload,
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
  { value: "CONDITIONAL_APPROVE", label: "Recommend conditional approval" },
  { value: "REJECT", label: "Recommend rejection" },
];

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
    (item) => item.action === "schedule_inspection",
  );
  const committeeQuery = useQuery({
    queryKey: ["committee-members", applicationId],
    queryFn: () => listCommitteeMembers(token, applicationId),
    enabled: Boolean(token && applicationId && scheduleAllowed),
    retry: false,
  });

  const [activeAction, setActiveAction] = useState<AllowedAction | null>(null);
  const [comment, setComment] = useState("");
  const [conditions, setConditions] = useState("");
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
    setConditions("");
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
    switch (activeAction.requires) {
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
      case "conditions":
        return conditions.trim()
          ? null
          : "Written conditions are required for conditional approval.";
      default:
        return null;
    }
  };

  const buildPayload = (): WorkflowActionPayload => {
    if (!activeAction) {
      return {};
    }
    const base = comment.trim() ? { comment: comment.trim() } : {};
    switch (activeAction.requires) {
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
      case "conditions":
        return { ...base, conditions: conditions.trim() };
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
    switch (activeAction.requires) {
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
      case "conditions":
        return (
          <div className="space-y-4">
            <Textarea
              label="Written conditions"
              value={conditions}
              onChange={(event) => setConditions(event.target.value)}
              placeholder="List the conditions the institution must satisfy."
              required
            />
            <Textarea
              label="Decision comment (optional)"
              value={comment}
              onChange={(event) => setComment(event.target.value)}
            />
          </div>
        );
      default:
        return (
          <Textarea
            label={
              activeAction.action === "reject" ||
              activeAction.action === "withdraw"
                ? "Reason / comment"
                : "Comment (optional)"
            }
            value={comment}
            onChange={(event) => setComment(event.target.value)}
            placeholder={
              activeAction.action === "reject"
                ? "Record the reason for rejection."
                : activeAction.action === "withdraw"
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
