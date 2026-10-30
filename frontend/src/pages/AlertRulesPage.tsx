import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  BellRing,
  Pencil,
  Plus,
  RefreshCw,
  ShieldAlert,
  Trash2,
} from "lucide-react";

import { useAuth } from "../auth/AuthContext";
import PageHeader from "../components/PageHeader";
import {
  Button,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  EmptyState,
  Input,
  Select,
  Skeleton,
  StatusPill,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
  Textarea,
  useToast,
  type StatusPillTone,
} from "../components/ui";
import {
  ApiError,
  createAlertRule,
  deleteAlertRule,
  listAlertRules,
  updateAlertRule,
  type AlertChannel,
  type AlertRule,
  type AlertRuleInput,
  type AlertTrigger,
  type Role,
  type Severity,
} from "../lib/api";
import { humanizeEnum } from "../lib/format";

const TRIGGER_LABELS: Record<AlertTrigger, string> = {
  DEADLINE_APPROACHING: "Deadline approaching",
  SLA_BREACHED: "SLA breached",
  DEFICIENCY_DUE: "Deficiency response due",
  DEFICIENCY_OVERDUE: "Deficiency response overdue",
  DOCUMENT_EXPIRING: "Document expiring",
  COMPLIANCE_RED: "Compliance became RED",
  APPLICATION_STATUS_CHANGED: "Application status changed",
  INSPECTION_SCHEDULED: "Inspection scheduled",
};

const SAMPLE_TEMPLATE_VALUES: Record<string, string> = {
  institution: "Vidya Vikas College of Engineering",
  application_id: "a1b2c3d4",
  application_reference: "APP-2026-0001",
  due_date: "31 Oct 2026",
  days_remaining: "7",
  status: "Submitted",
  stage: "Scrutiny",
  document: "DSC Certificate",
  deficiency: "Missing faculty appointment letters",
  inspection_date: "15 Nov 2026",
};

/** Render an alert template with sample values, mirroring the backend's
 *  safe placeholder handling (unknown placeholders stay visible). */
function renderAlertTemplate(template: string): string {
  return template.replaceAll(/\{([^}]+)\}/g, (_match, key) => {
    const value = SAMPLE_TEMPLATE_VALUES[key.trim()];
    return value === undefined ? `{${key}}` : value;
  });
}

const TRIGGER_OPTIONS = (Object.keys(TRIGGER_LABELS) as AlertTrigger[]).map(
  (value) => ({ value, label: TRIGGER_LABELS[value] }),
);

const SEVERITY_TONES: Record<Severity, StatusPillTone> = {
  LOW: "info",
  MEDIUM: "watch",
  HIGH: "breach",
  CRITICAL: "breach",
};

const SEVERITY_OPTIONS: { value: Severity; label: string }[] = [
  { value: "LOW", label: "Low" },
  { value: "MEDIUM", label: "Medium" },
  { value: "HIGH", label: "High" },
  { value: "CRITICAL", label: "Critical" },
];

const CHANNEL_LABELS: Record<AlertChannel, string> = {
  IN_APP: "In-app",
  EMAIL: "Email",
  SMS: "SMS (mock)",
};

const CHANNELS: AlertChannel[] = ["IN_APP", "EMAIL", "SMS"];

const ESCALATION_ROLES: { value: Role; label: string }[] = [
  { value: "REGIONAL_OFFICER", label: "Regional Officer" },
  { value: "REGULATION_BUREAU_OFFICER", label: "Regulation Bureau officer" },
  { value: "EXECUTIVE_COMMITTEE_MEMBER", label: "Executive Committee member" },
  { value: "SUPER_ADMIN", label: "Super administrator" },
];

const TEMPLATE_PLACEHOLDERS =
  "{institution}, {application_id}, {application_reference}, {due_date}, {days_remaining}, {status}, {stage}, {document}, {deficiency}, {inspection_date}";

interface RuleFormState {
  code: string;
  name: string;
  description: string;
  trigger_type: AlertTrigger;
  days_before: string;
  severity: Severity;
  channel_list: AlertChannel[];
  template: string;
  escalation_role: Role;
  is_active: boolean;
}

function emptyForm(): RuleFormState {
  return {
    code: "",
    name: "",
    description: "",
    trigger_type: "DEADLINE_APPROACHING",
    days_before: "7",
    severity: "MEDIUM",
    channel_list: ["IN_APP", "EMAIL"],
    template:
      "The {stage} stage for {institution} (application {application_reference}) is due on {due_date}. {days_remaining} day(s) remain.",
    escalation_role: "REGIONAL_OFFICER",
    is_active: true,
  };
}

function ruleToForm(rule: AlertRule): RuleFormState {
  return {
    code: rule.code,
    name: rule.name,
    description: rule.description,
    trigger_type: rule.trigger_type,
    days_before: String(rule.days_before),
    severity: rule.severity,
    channel_list: rule.channel_list,
    template: rule.template,
    escalation_role: rule.escalation_role,
    is_active: rule.is_active,
  };
}

function formToInput(form: RuleFormState): AlertRuleInput {
  return {
    code: form.code.trim().toUpperCase(),
    name: form.name.trim(),
    description: form.description.trim(),
    trigger_type: form.trigger_type,
    days_before: Number(form.days_before),
    severity: form.severity,
    channel_list: form.channel_list,
    template: form.template.trim(),
    escalation_role: form.escalation_role,
    is_active: form.is_active,
  };
}

function validateForm(form: RuleFormState): string | null {
  if (!/^[A-Z0-9][A-Z0-9_-]*$/.test(form.code.trim().toUpperCase())) {
    return "Use a code of upper-case letters, numbers, hyphens or underscores, starting with a letter or number.";
  }
  if (!form.name.trim()) return "A rule name is required.";
  if (!form.template.trim()) return "A message template is required.";
  const days = Number(form.days_before);
  if (!Number.isInteger(days) || days < 0 || days > 365) {
    return "Days before must be a whole number between 0 and 365.";
  }
  if (form.channel_list.length === 0) return "Select at least one delivery channel.";
  return null;
}

function messageFor(error: unknown, fallback: string): string {
  return error instanceof ApiError ? error.message : fallback;
}

function thresholdText(rule: Pick<AlertRule, "days_before">): string {
  return rule.days_before === 0 ? "Immediate" : `T-${rule.days_before} days`;
}

function TemplatePreview({ template }: { template: string }): JSX.Element {
  const rendered = renderAlertTemplate(template);
  const hasPlaceholders = /\{(institution|application_id|application_reference|due_date|days_remaining|status|stage|document|deficiency|inspection_date)\}/.test(
    template,
  );

  return (
    <section
      className="rounded-input border border-line bg-surface p-3"
      aria-label="Template preview"
    >
      <div className="flex items-center gap-2 mb-2">
        <span className="text-11 font-semibold uppercase tracking-wide text-ink-500">
          Live preview
        </span>
        {hasPlaceholders ? (
          <span className="text-11 text-ink-500">
            · Sample values shown; unknown placeholders stay visible
          </span>
        ) : null}
      </div>
      <div className="rounded-input border border-line bg-paper p-3 text-13 leading-6 text-ink-700 font-sans">
        {rendered}
      </div>
      {template.trim() === "" ? (
        <p className="mt-1 text-11 text-ink-500">
          Enter a template to see the preview.
        </p>
      ) : null}
    </section>
  );
}

function AlertRuleDialog({
  token,
  rule,
  onClose,
}: {
  token: string;
  rule: AlertRule | null;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [form, setForm] = useState<RuleFormState>(() =>
    rule ? ruleToForm(rule) : emptyForm(),
  );
  const [error, setError] = useState<string | null>(null);

  const saveMutation = useMutation({
    mutationFn: (input: AlertRuleInput) =>
      rule
        ? updateAlertRule(token, rule.id, input)
        : createAlertRule(token, input),
    onSuccess: () => {
      toast({
        title: rule ? "Alert rule updated" : "Alert rule created",
        description: "The change is audited and the scheduler will use it on the next scan.",
      });
      void queryClient.invalidateQueries({ queryKey: ["alert-rules"] });
      onClose();
    },
    onError: (mutationError) => {
      setError(messageFor(mutationError, "The alert rule could not be saved."));
    },
  });

  const update = <K extends keyof RuleFormState>(
    key: K,
    value: RuleFormState[K],
  ) => {
    setForm((current) => ({ ...current, [key]: value }));
  };

  const toggleChannel = (channel: AlertChannel) => {
    if (channel === "IN_APP") {
      return;
    }
    update(
      "channel_list",
      form.channel_list.includes(channel)
        ? form.channel_list.filter((item) => item !== channel)
        : [...form.channel_list, channel],
    );
  };

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const validation = validateForm(form);
    if (validation) {
      setError(validation);
      return;
    }
    setError(null);
    saveMutation.mutate(formToInput(form));
  };

  return (
    <Dialog open onOpenChange={(open) => (!open ? onClose() : undefined)}>
      <DialogContent className="max-w-3xl">
        <DialogHeader>
          <DialogTitle>{rule ? "Edit alert rule" : "Add alert rule"}</DialogTitle>
          <DialogDescription>
            Rules are database configuration, not code. Day thresholds and templates are
            illustrative and must be reviewed against the current AICTE Approval Process Handbook.
            Every change is written to the audit log.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="mt-5 space-y-4">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Input
              label="Rule code"
              value={form.code}
              onChange={(event) => update("code", event.target.value)}
              disabled={Boolean(rule)}
              placeholder="DEADLINE-7"
              hint={rule ? "The code is immutable after creation." : "Upper-case, unique."}
              required
            />
            <Input
              label="Rule name"
              value={form.name}
              onChange={(event) => update("name", event.target.value)}
              placeholder="Approaching deadline: 7 days"
              required
            />
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Select
              label="Trigger"
              value={form.trigger_type}
              onValueChange={(value) => update("trigger_type", value as AlertTrigger)}
              options={TRIGGER_OPTIONS}
            />
            <Input
              label="Days before"
              type="number"
              min="0"
              max="365"
              step="1"
              value={form.days_before}
              onChange={(event) => update("days_before", event.target.value)}
              hint="Use 0 for events that fire immediately. Deadline and expiry windows use days before the due date."
              required
            />
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Select
              label="Severity"
              value={form.severity}
              onValueChange={(value) => update("severity", value as Severity)}
              options={SEVERITY_OPTIONS}
            />
            <Select
              label="Escalate first to"
              value={form.escalation_role}
              onValueChange={(value) => update("escalation_role", value as Role)}
              options={ESCALATION_ROLES}
              hint="The next step in the chain is always the super administrator."
            />
          </div>

          <Textarea
            label="Description"
            value={form.description}
            onChange={(event) => update("description", event.target.value)}
            hint="Shown to administrators in this catalogue."
          />

          <fieldset>
            <legend className="mb-1.5 block text-13 font-medium text-ink-700">
              Delivery channels
            </legend>
            <div className="flex flex-wrap gap-x-5 gap-y-2 rounded-input border border-line px-3 py-2.5">
              {CHANNELS.map((channel) => (
                <label
                  key={channel}
                  className="flex items-center gap-2 text-13 text-ink-700"
                >
                  <input
                    type="checkbox"
                    checked={form.channel_list.includes(channel)}
                    onChange={() => toggleChannel(channel)}
                    disabled={channel === "IN_APP"}
                    className="size-4 rounded border-line text-saffron focus-visible:ring-focus disabled:opacity-60"
                  />
                  {CHANNEL_LABELS[channel]}
                  {channel === "IN_APP" ? (
                    <span className="text-11 text-ink-500">required</span>
                  ) : null}
                </label>
              ))}
            </div>
          </fieldset>

          <Textarea
            label="Message template"
            value={form.template}
            onChange={(event) => update("template", event.target.value)}
            hint={`Placeholders: ${TEMPLATE_PLACEHOLDERS}. Unknown placeholders are left visible.`}
            className="min-h-32 font-mono text-13"
            required
          />
          <TemplatePreview template={form.template} />

          <label className="flex items-center gap-2 text-13 font-medium text-ink-700">
            <input
              type="checkbox"
              checked={form.is_active}
              onChange={(event) => update("is_active", event.target.checked)}
              className="size-4 rounded border-line text-saffron focus-visible:ring-focus"
            />
            Active (included in periodic scans and event notifications)
          </label>

          {error ? (
            <p className="rounded-input border border-breach bg-breach-soft p-3 text-13 text-breach-strong">
              {error}
            </p>
          ) : null}

          <DialogFooter>
            <Button variant="secondary" type="button" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" disabled={saveMutation.isPending}>
              {saveMutation.isPending
                ? "Saving…"
                : rule
                  ? "Save changes"
                  : "Create rule"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export default function AlertRulesPage() {
  const { user, token } = useAuth();
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [triggerFilter, setTriggerFilter] = useState<AlertTrigger | "ALL">("ALL");
  const [includeInactive, setIncludeInactive] = useState(true);
  const [editor, setEditor] = useState<{ rule: AlertRule | null } | null>(null);
  const [deleting, setDeleting] = useState<AlertRule | null>(null);

  const authToken = token ?? "";

  const rulesQuery = useQuery({
    queryKey: ["alert-rules", { triggerFilter, includeInactive }],
    queryFn: () =>
      listAlertRules(authToken, {
        triggerType: triggerFilter === "ALL" ? undefined : triggerFilter,
        includeInactive,
        pageSize: 100,
      }),
    enabled: Boolean(authToken && user),
  });

  const toggleMutation = useMutation({
    mutationFn: (rule: AlertRule) =>
      updateAlertRule(authToken, rule.id, { is_active: !rule.is_active }),
    onSuccess: (rule) => {
      toast({
        title: rule.is_active ? "Alert rule activated" : "Alert rule deactivated",
        description: rule.is_active
          ? "The rule will be evaluated on the next scan."
          : "Existing alerts remain; future scans skip this rule.",
      });
      void queryClient.invalidateQueries({ queryKey: ["alert-rules"] });
    },
    onError: (error) => {
      toast({
        title: "Alert rule could not be updated",
        description: messageFor(error, "Try again."),
        variant: "error",
      });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (rule: AlertRule) => deleteAlertRule(authToken, rule.id),
    onSuccess: () => {
      toast({
        title: "Alert rule deleted",
        description: "Historical alerts are retained; future scans no longer use this rule.",
      });
      void queryClient.invalidateQueries({ queryKey: ["alert-rules"] });
      setDeleting(null);
    },
    onError: (error) => {
      toast({
        title: "Alert rule could not be deleted",
        description: messageFor(error, "Try again."),
        variant: "error",
      });
    },
  });

  if (!user) {
    return null;
  }

  const rules = rulesQuery.data?.items ?? [];
  const activeCount = rules.filter((rule) => rule.is_active).length;

  return (
    <>
      <PageHeader
        eyebrow="Alert administration"
        title="Alert rules"
        description="Configure when alerts fire, which channels they use, and who receives the first escalation. The 15-minute alert scan reads these rows as data."
        actions={
          <>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => void rulesQuery.refetch()}
              disabled={rulesQuery.isFetching}
            >
              <RefreshCw
                aria-hidden="true"
                className={rulesQuery.isFetching ? "size-4 animate-spin" : "size-4"}
              />
              Refresh
            </Button>
            <Button size="sm" onClick={() => setEditor({ rule: null })}>
              <Plus aria-hidden="true" className="size-4" />
              Add rule
            </Button>
          </>
        }
      />

      <section
        aria-label="Filter alert rules"
        className="mb-5 rounded-panel border border-line bg-surface p-4"
      >
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4 lg:items-end">
          <Select
            label="Trigger"
            value={triggerFilter}
            onValueChange={(value) =>
              setTriggerFilter(value as AlertTrigger | "ALL")
            }
            options={[{ value: "ALL", label: "All triggers" }, ...TRIGGER_OPTIONS]}
          />
          <label className="flex h-10 items-center gap-2 text-13 font-medium text-ink-700">
            <input
              type="checkbox"
              checked={includeInactive}
              onChange={(event) => setIncludeInactive(event.target.checked)}
              className="size-4 rounded border-line text-saffron focus-visible:ring-focus"
            />
            Include inactive rules
          </label>
          <p className="text-12 text-ink-500 lg:col-span-2 lg:text-right">
            {rules.length} rule{rules.length === 1 ? "" : "s"} shown · {activeCount} active
          </p>
        </div>
      </section>

      <section
        aria-label="Alert rule catalogue"
        className="rounded-panel border border-line bg-surface"
      >
        <div className="border-b border-line px-4 py-3">
          <h2 className="font-serif text-20 font-semibold text-ink">Rule catalogue</h2>
          <p className="mt-0.5 max-w-3xl text-12 leading-5 text-ink-500">
            Multiple rows with the same trigger are threshold windows. A deadline rule with
            T-7, T-3 and T-1 produces one alert per window, deduplicated by trigger, entity and
            threshold.
          </p>
        </div>

        {rulesQuery.isPending ? (
          <div className="space-y-3 p-4" role="status">
            {[0, 1, 2, 3, 4].map((item) => (
              <Skeleton key={item} className="h-12 w-full" />
            ))}
            <span className="sr-only">Loading alert rules</span>
          </div>
        ) : rulesQuery.isError ? (
          <div className="p-4">
            <p className="rounded-input border border-breach bg-breach-soft p-3 text-13 text-breach-strong">
              {messageFor(rulesQuery.error, "Alert rules could not be loaded.")}
            </p>
            <Button
              variant="secondary"
              size="sm"
              className="mt-3"
              onClick={() => void rulesQuery.refetch()}
            >
              Retry
            </Button>
          </div>
        ) : rules.length === 0 ? (
          <div className="p-4">
            <EmptyState
              message="No alert rules match this filter."
              action={
                <Button size="sm" onClick={() => setEditor({ rule: null })}>
                  Add a rule
                </Button>
              }
            />
          </div>
        ) : (
          <div className="overflow-x-auto">
            <Table density="dense">
              <TableHeader>
                <TableRow>
                  <TableHead>Rule</TableHead>
                  <TableHead>Trigger and threshold</TableHead>
                  <TableHead>Severity</TableHead>
                  <TableHead>Channels</TableHead>
                  <TableHead>Escalates to</TableHead>
                  <TableHead>Active</TableHead>
                  <TableHead>
                    <span className="sr-only">Actions</span>
                  </TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {rules.map((rule) => (
                  <TableRow
                    key={rule.id}
                    className={rule.is_active ? undefined : "opacity-60"}
                  >
                    <TableCell className="min-w-56">
                      <p className="font-medium text-ink">{rule.name}</p>
                      <p className="mt-0.5 font-mono text-11 text-ink-500">{rule.code}</p>
                      {rule.description ? (
                        <p className="mt-1 line-clamp-2 max-w-80 text-12 leading-4 text-ink-500">
                          {rule.description}
                        </p>
                      ) : null}
                    </TableCell>
                    <TableCell className="whitespace-nowrap text-12 text-ink-700">
                      <p>{TRIGGER_LABELS[rule.trigger_type]}</p>
                      <p className="mt-0.5 text-ink-500">{thresholdText(rule)}</p>
                    </TableCell>
                    <TableCell>
                      <StatusPill status={SEVERITY_TONES[rule.severity]}>
                        {humanizeEnum(rule.severity)}
                      </StatusPill>
                    </TableCell>
                    <TableCell className="min-w-32 text-12 text-ink-700">
                      {rule.channel_list
                        .map((channel) => CHANNEL_LABELS[channel])
                        .join(" · ")}
                    </TableCell>
                    <TableCell className="whitespace-nowrap text-12 text-ink-700">
                      {humanizeEnum(rule.escalation_role)}
                    </TableCell>
                    <TableCell>
                      <button
                        type="button"
                        onClick={() => toggleMutation.mutate(rule)}
                        disabled={toggleMutation.isPending}
                        aria-label={
                          rule.is_active
                            ? `Deactivate ${rule.name}`
                            : `Activate ${rule.name}`
                        }
                        title={
                          rule.is_active
                            ? "Click to deactivate"
                            : "Click to activate"
                        }
                        className={`rounded-pill px-2.5 py-1 text-12 font-medium ${
                          rule.is_active
                            ? "bg-ok-soft text-ok-strong"
                            : "bg-paper text-ink-500"
                        }`}
                      >
                        {rule.is_active ? "Active" : "Inactive"}
                      </button>
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-1">
                        <Button
                          variant="quiet"
                          size="sm"
                          onClick={() => setEditor({ rule })}
                        >
                          <Pencil aria-hidden="true" className="size-3.5" />
                          Edit
                        </Button>
                        <Button
                          variant="quiet"
                          size="sm"
                          onClick={() => setDeleting(rule)}
                          aria-label={`Delete ${rule.name}`}
                        >
                          <Trash2 aria-hidden="true" className="size-3.5" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}

        <p className="border-t border-line px-4 py-3 text-11 leading-4 text-ink-500">
          Changes take effect on the next periodic scan. Deactivating or deleting a rule does
          not remove alerts that have already been delivered.
        </p>
      </section>

      <p className="mt-5 flex items-start gap-2 rounded-panel border border-line bg-surface p-3 text-12 leading-5 text-ink-500">
        <ShieldAlert aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
        Alert thresholds and templates are illustrative configuration. They are not official
        AICTE policy and must be verified against the current Approval Process Handbook.
      </p>

      {editor ? (
        <AlertRuleDialog
          token={authToken}
          rule={editor.rule}
          onClose={() => setEditor(null)}
        />
      ) : null}

      {deleting ? (
        <Dialog open onOpenChange={(open) => (!open ? setDeleting(null) : undefined)}>
          <DialogContent className="max-w-lg">
            <DialogHeader>
              <DialogTitle>Delete alert rule</DialogTitle>
              <DialogDescription>
                Delete “{deleting.name}” ({deleting.code})? Historical alerts are retained, but
                the periodic scan will stop evaluating this rule.
              </DialogDescription>
            </DialogHeader>
            <div className="mt-5 flex items-start gap-2 rounded-input border border-watch bg-watch-soft p-3 text-13 text-watch-strong">
              <BellRing aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
              Consider deactivating the rule instead if you only want to pause it.
            </div>
            <DialogFooter>
              <Button variant="secondary" onClick={() => setDeleting(null)}>
                Cancel
              </Button>
              <Button
                variant="destructive"
                onClick={() => deleteMutation.mutate(deleting)}
                disabled={deleteMutation.isPending}
              >
                {deleteMutation.isPending ? "Deleting…" : "Delete rule"}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      ) : null}
    </>
  );
}
