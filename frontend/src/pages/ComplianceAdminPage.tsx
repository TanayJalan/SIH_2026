import { useMemo, useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  History,
  Pencil,
  Plus,
  RefreshCw,
  ShieldCheck,
  TrendingUp,
} from "lucide-react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip as ChartTooltip,
  XAxis,
  YAxis,
} from "recharts";

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
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
  Textarea,
  useToast,
  type StatusPillTone,
} from "../components/ui";
import {
  ApiError,
  createComplianceRule,
  getComplianceConfig,
  getComplianceMonitor,
  getComplianceRuleHistory,
  getInstitutionComplianceTrend,
  listComplianceMetrics,
  listComplianceRules,
  previewComplianceRuleImpact,
  runComplianceMonitor,
  updateComplianceConfig,
  updateComplianceRule,
  type BandwidthTier,
  type ComplianceConfig,
  type ComplianceConfigUpdate,
  type ComplianceHealth,
  type ComplianceInstitutionTrend,
  type ComplianceMetric,
  type ComplianceRule,
  type ComplianceRuleImpact,
  type ComplianceRuleInput,
  type RagBreakpoints,
  type RuleOperator,
  type Severity,
  type SeverityWeights,
} from "../lib/api";
import { formatDateTime, humanizeEnum } from "../lib/format";

const HEALTH_TONE: Record<ComplianceHealth, StatusPillTone> = {
  GREEN: "compliant",
  AMBER: "watch",
  RED: "breach",
};

const HEALTH_LABEL: Record<ComplianceHealth, string> = {
  GREEN: "Green",
  AMBER: "Amber",
  RED: "Red",
};

const SEVERITY_TONE: Record<Severity, StatusPillTone> = {
  CRITICAL: "breach",
  HIGH: "watch",
  MEDIUM: "info",
  LOW: "neutral",
};

const OPERATOR_OPTIONS: { value: RuleOperator; label: string }[] = [
  { value: ">=", label: "At least (>=)" },
  { value: "<=", label: "At most (<=)" },
  { value: "=", label: "Equal to (=)" },
  { value: "==", label: "Equal to (==)" },
  { value: "BETWEEN", label: "Between (inclusive)" },
  { value: "EXISTS", label: "Value exists" },
  { value: "RATIO", label: "Ratio of two metrics" },
  { value: "SUM", label: "Sum of metrics" },
  { value: "COUNT", label: "Count of matches" },
  { value: "DATE_NOT_EXPIRED", label: "Date not expired" },
  { value: ">", label: "Above (>)" },
  { value: "<", label: "Below (<)" },
  { value: "!=", label: "Different from (!=)" },
];

const SEVERITY_OPTIONS: Severity[] = ["CRITICAL", "HIGH", "MEDIUM", "LOW"];

const CATEGORY_OPTIONS = [
  "Faculty",
  "Land and building",
  "Infrastructure",
  "Library",
  "Computing",
  "Essential requirements",
  "Admissions",
  "Documents",
  "Finance",
  "Accreditation",
  "Other",
];

const FAMILY_OPTIONS = [
  "ENGINEERING_TECHNOLOGY",
  "MANAGEMENT",
  "COMPUTER_APPLICATIONS",
  "PLANNING",
  "DESIGN",
  "HMCT",
  "APPLIED_ARTS_CRAFTS",
];

const LEVEL_OPTIONS = ["UG", "PG", "DIPLOMA", "PG_DIPLOMA", "INTEGRATED"];

interface RuleFormState {
  code: string;
  name: string;
  category: string;
  description: string;
  metric_key: string;
  operator: RuleOperator;
  threshold: string;
  threshold_max: string;
  severity: Severity;
  applies_to: string;
  applies_to_family: string;
  applies_to_level: string;
  apH_clause: string;
  needs_verification: boolean;
  mandatory: boolean;
  illustrative: boolean;
  weight: string;
  unit: string;
  explanation_template: string;
  metric_params: string;
  penalty_codes: string;
  is_active: boolean;
}

function emptyRuleForm(metrics: ComplianceMetric[]): RuleFormState {
  return {
    code: "",
    name: "",
    category: "Infrastructure",
    description: "",
    metric_key: metrics[0]?.key ?? "area.built_up_available",
    operator: ">=",
    threshold: "0",
    threshold_max: "",
    severity: "MEDIUM",
    applies_to: "ALL",
    applies_to_family: "",
    applies_to_level: "",
    apH_clause: "APH ",
    needs_verification: true,
    mandatory: true,
    illustrative: false,
    weight: "",
    unit: "",
    explanation_template: "",
    metric_params: "{}",
    penalty_codes: "",
    is_active: true,
  };
}

function ruleToForm(rule: ComplianceRule): RuleFormState {
  return {
    code: rule.code,
    name: rule.name,
    category: rule.category,
    description: rule.description,
    metric_key: rule.metric_key,
    operator: rule.operator,
    threshold: String(rule.threshold),
    threshold_max: rule.threshold_max === null ? "" : String(rule.threshold_max),
    severity: rule.severity,
    applies_to: rule.applies_to,
    applies_to_family: rule.applies_to_family ?? "",
    applies_to_level: rule.applies_to_level ?? "",
    apH_clause: rule.apH_clause,
    needs_verification: rule.needs_verification,
    mandatory: rule.mandatory,
    illustrative: rule.illustrative,
    weight: rule.weight === null ? "" : String(rule.weight),
    unit: rule.unit ?? "",
    explanation_template: rule.explanation_template ?? "",
    metric_params: JSON.stringify(rule.metric_params ?? {}, null, 2),
    penalty_codes: (rule.penalty_codes ?? []).join(", "),
    is_active: rule.is_active,
  };
}

function parseMetricParams(raw: string): Record<string, unknown> | string {
  const trimmed = raw.trim();
  if (!trimmed) {
    return {};
  }
  let parsed: unknown;
  try {
    parsed = JSON.parse(trimmed);
  } catch {
    return "The metric parameters must be valid JSON.";
  }
  if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
    return "The metric parameters must be a JSON object.";
  }
  return parsed as Record<string, unknown>;
}

function formToInput(form: RuleFormState): ComplianceRuleInput {
  const params = parseMetricParams(form.metric_params);
  return {
    code: form.code.trim(),
    name: form.name.trim(),
    category: form.category.trim(),
    description: form.description.trim(),
    metric_key: form.metric_key.trim(),
    operator: form.operator,
    threshold: Number(form.threshold),
    threshold_max:
      form.operator === "BETWEEN" && form.threshold_max !== ""
        ? Number(form.threshold_max)
        : null,
    severity: form.severity,
    applies_to: form.applies_to.trim() || "ALL",
    applies_to_family: form.applies_to_family.trim() || null,
    applies_to_level: form.applies_to_level.trim() || null,
    apH_clause: form.apH_clause.trim() || "DEMO",
    needs_verification: form.needs_verification,
    mandatory: form.mandatory,
    illustrative: form.illustrative,
    weight: form.weight.trim() === "" ? null : Number(form.weight),
    unit: form.unit.trim() || null,
    explanation_template: form.explanation_template.trim() || null,
    metric_params: typeof params === "string" ? {} : params,
    penalty_codes: form.penalty_codes
      .split(",")
      .map((code) => code.trim())
      .filter(Boolean),
    is_active: form.is_active,
  };
}

function validateForm(form: RuleFormState): string | null {
  if (!form.code.trim()) return "A rule code is required.";
  if (!form.name.trim()) return "A rule name is required.";
  if (!form.category.trim()) return "A category is required.";
  if (!form.description.trim()) return "A description is required.";
  if (!form.metric_key.trim()) return "A metric is required.";
  if (!Number.isFinite(Number(form.threshold))) return "Threshold must be a number.";
  if (form.weight.trim() !== "" && !Number.isFinite(Number(form.weight))) {
    return "Weight must be a number.";
  }
  if (form.operator === "BETWEEN") {
    const max = Number(form.threshold_max);
    if (form.threshold_max === "" || !Number.isFinite(max)) {
      return "An upper bound is required for BETWEEN.";
    }
    if (max < Number(form.threshold)) {
      return "The upper bound must be greater than or equal to the lower bound.";
    }
  }
  const params = parseMetricParams(form.metric_params);
  if (typeof params === "string") {
    return params;
  }
  if (
    (form.operator === "RATIO" ||
      form.operator === "SUM" ||
      form.operator === "COUNT") &&
    Object.keys(params).length === 0
  ) {
    return "RATIO, SUM and COUNT rules need metric parameters.";
  }
  if (form.illustrative && !form.needs_verification) {
    return "An illustrative rule cannot claim a verified AICTE clause. Keep 'needs verification' on.";
  }
  if (!form.apH_clause.trim() || form.apH_clause.trim() === "APH") {
    return "An APH clause is required, for example APH 6.14.";
  }
  return null;
}

function conditionText(rule: ComplianceRule): string {
  const operator = rule.operator === "==" ? "=" : rule.operator;
  if (rule.operator === "BETWEEN") {
    return `between ${rule.threshold} and ${rule.threshold_max ?? "?"}`;
  }
  if (rule.operator === "EXISTS") return "present";
  if (rule.operator === "DATE_NOT_EXPIRED") return "not expired";
  return `${operator} ${rule.threshold}`;
}

function messageFor(error: unknown, fallback: string): string {
  return error instanceof ApiError ? error.message : fallback;
}

function MetricSummary({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone: "ok" | "watch" | "breach" | "ink";
}) {
  const toneClass = {
    ok: "text-ok-strong",
    watch: "text-watch-strong",
    breach: "text-breach-strong",
    ink: "text-ink",
  }[tone];
  return (
    <div className="rounded-panel border border-line bg-surface p-4">
      <p className="text-12 font-medium text-ink-500">{label}</p>
      <p className={`mt-1 font-serif text-28 font-semibold tabular-nums ${toneClass}`}>
        {value}
      </p>
    </div>
  );
}

function TrendPanel({
  trend,
  breakpoints,
  loading,
}: {
  trend: ComplianceInstitutionTrend | undefined;
  breakpoints: RagBreakpoints | undefined;
  loading: boolean;
}) {
  if (loading) {
    return <Skeleton className="h-64 w-full" />;
  }
  if (!trend || trend.points.length === 0) {
    return (
      <EmptyState
        message="No compliance snapshots exist for this institution yet. Re-evaluate monitoring to create the first point."
        action={
          <span className="text-12 text-ink-500">
            Use “Re-evaluate now” at the top of the page.
          </span>
        }
      />
    );
  }

  const data = trend.points.map((point) => ({
    ...point,
    label: new Date(point.evaluated_at).toLocaleString("en-IN", {
      day: "2-digit",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
    }),
  }));

  return (
    <div>
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="text-14 font-semibold text-ink">{trend.institution_name}</p>
          <p className="mt-0.5 text-12 text-ink-500">
            {trend.region} · {trend.points.length} stored evaluation
            {trend.points.length === 1 ? "" : "s"}
          </p>
        </div>
        <StatusPill status={HEALTH_TONE[trend.points[trend.points.length - 1].status]}>
          Latest {HEALTH_LABEL[trend.points[trend.points.length - 1].status]}
        </StatusPill>
      </div>

      <div className="mt-4 h-64 w-full" aria-label="Institution compliance score trend">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data} margin={{ top: 8, right: 16, bottom: 0, left: -16 }}>
            <CartesianGrid stroke="var(--line)" strokeDasharray="3 3" vertical={false} />
            <XAxis
              dataKey="label"
              tick={{ fill: "var(--ink-500)", fontSize: 11 }}
              axisLine={{ stroke: "var(--line)" }}
              tickLine={false}
            />
            <YAxis
              domain={[0, 100]}
              tick={{ fill: "var(--ink-500)", fontSize: 11 }}
              axisLine={false}
              tickLine={false}
            />
            <ChartTooltip
              contentStyle={{
                background: "var(--surface)",
                border: "1px solid var(--line)",
                borderRadius: 8,
                fontSize: 12,
              }}
              labelFormatter={(label) => `Evaluated ${label}`}
              formatter={(value) => [`${value}/100`, "Score"]}
            />
            {breakpoints ? (
              <>
                <ReferenceLine
                  y={breakpoints.red_below}
                  stroke="var(--breach)"
                  strokeDasharray="4 4"
                  label={{
                    value: `RED < ${breakpoints.red_below}`,
                    position: "insideBottomRight",
                    fill: "var(--breach-strong)",
                    fontSize: 10,
                  }}
                />
                <ReferenceLine
                  y={breakpoints.amber_below}
                  stroke="var(--watch)"
                  strokeDasharray="4 4"
                  label={{
                    value: `AMBER < ${breakpoints.amber_below}`,
                    position: "insideTopRight",
                    fill: "var(--watch-strong)",
                    fontSize: 10,
                  }}
                />
              </>
            ) : null}
            <Line
              type="monotone"
              dataKey="score"
              stroke="var(--ink)"
              strokeWidth={2}
              dot={{ r: 3, fill: "var(--ink)" }}
              activeDot={{ r: 5 }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>

      <ul className="mt-4 divide-y divide-line border-t border-line text-12">
        {trend.points
          .slice()
          .reverse()
          .slice(0, 6)
          .map((point) => (
            <li
              key={point.snapshot_id}
              className="flex flex-wrap items-center justify-between gap-2 py-2"
            >
              <span className="text-ink-500">{formatDateTime(point.evaluated_at)}</span>
              <span className="tabular-nums text-ink">{point.score.toFixed(1)}/100</span>
              <StatusPill status={HEALTH_TONE[point.status]}>
                {HEALTH_LABEL[point.status]}
              </StatusPill>
              <span className="text-ink-500">
                {point.failed_count} failed · {point.missing_count} missing · {point.trigger}
              </span>
            </li>
          ))}
      </ul>
    </div>
  );
}

function RuleDialog({
  token,
  rule,
  metrics,
  onClose,
}: {
  token: string;
  rule: ComplianceRule | null;
  metrics: ComplianceMetric[];
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [form, setForm] = useState<RuleFormState>(() =>
    rule ? ruleToForm(rule) : emptyRuleForm(metrics),
  );
  const [impact, setImpact] = useState<ComplianceRuleImpact | null>(null);
  const [error, setError] = useState<string | null>(null);

  const invalidate = () => {
    void queryClient.invalidateQueries({ queryKey: ["compliance-rules"] });
    void queryClient.invalidateQueries({ queryKey: ["compliance-monitor"] });
    void queryClient.invalidateQueries({ queryKey: ["compliance-trend"] });
    void queryClient.invalidateQueries({ queryKey: ["compliance-preview"] });
  };

  const saveMutation = useMutation({
    mutationFn: (input: ComplianceRuleInput) =>
      rule
        ? updateComplianceRule(token, rule.id, input)
        : createComplianceRule(token, input),
    onSuccess: () => {
      toast({
        title: rule ? "Rule updated" : "Rule created",
        description: "The change is audited and live evaluations will use it immediately.",
      });
      invalidate();
      onClose();
    },
    onError: (mutationError) => {
      setError(messageFor(mutationError, "The rule could not be saved."));
    },
  });

  const impactMutation = useMutation({
    mutationFn: () =>
      previewComplianceRuleImpact(token, {
        ruleId: rule?.id ?? null,
        proposed: formToInput(form),
      }),
    onSuccess: (result) => {
      setError(null);
      setImpact(result);
    },
    onError: (mutationError) => {
      setError(messageFor(mutationError, "The impact could not be projected."));
    },
  });

  const update = <K extends keyof RuleFormState>(key: K, value: RuleFormState[K]) => {
    setForm((current) => ({ ...current, [key]: value }));
    setImpact(null);
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

  const handleImpact = () => {
    const validation = validateForm(form);
    if (validation) {
      setError(validation);
      return;
    }
    setError(null);
    impactMutation.mutate();
  };

  const metricOptions = metrics.map((metric) => ({
    value: metric.key,
    label: `${metric.label}${metric.unit ? ` (${metric.unit})` : ""}`,
  }));

  return (
    <Dialog open onOpenChange={(open) => (!open ? onClose() : undefined)}>
      <DialogContent className="max-w-3xl">
        <DialogHeader>
          <DialogTitle>{rule ? "Edit compliance rule" : "Add compliance rule"}</DialogTitle>
          <DialogDescription>
            Rules and thresholds are configuration data, never code. Each rule must cite the APH
            clause it implements, and every change is written to the audit log.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit} className="mt-5 space-y-4">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Input
              label="Rule code"
              value={form.code}
              onChange={(event) => update("code", event.target.value)}
              disabled={Boolean(rule)}
              hint={rule ? "The code is immutable after creation." : "Unique, for example APH-FSR-20."}
              required
            />
            <Input
              label="Rule name"
              value={form.name}
              onChange={(event) => update("name", event.target.value)}
              required
            />
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Select
              label="Category"
              value={form.category}
              onValueChange={(value) => update("category", value)}
              options={CATEGORY_OPTIONS.map((category) => ({
                value: category,
                label: category,
              }))}
            />
            <Select
              label="Metric"
              value={form.metric_key}
              onValueChange={(value) => update("metric_key", value)}
              options={metricOptions}
            />
          </div>

          <Textarea
            label="Description"
            value={form.description}
            onChange={(event) => update("description", event.target.value)}
            hint="Shown to officers alongside the rule outcome."
            required
          />

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <Select
              label="Operator"
              value={form.operator}
              onValueChange={(value) => update("operator", value as RuleOperator)}
              options={OPERATOR_OPTIONS}
            />
            <Input
              label="Threshold"
              type="number"
              step="0.01"
              min="0"
              value={form.threshold}
              onChange={(event) => update("threshold", event.target.value)}
              disabled={form.operator === "EXISTS"}
              hint={form.operator === "EXISTS" ? "Not used by EXISTS." : undefined}
              required
            />
            {form.operator === "BETWEEN" ? (
              <Input
                label="Upper bound"
                type="number"
                step="0.01"
                min="0"
                value={form.threshold_max}
                onChange={(event) => update("threshold_max", event.target.value)}
                required
              />
            ) : (
              <Input
                label="Unit"
                value={form.unit}
                onChange={(event) => update("unit", event.target.value)}
                hint="sq. m, faculty, Mbps, count…"
              />
            )}
          </div>

          {form.operator === "BETWEEN" ? (
            <Input
              label="Unit"
              value={form.unit}
              onChange={(event) => update("unit", event.target.value)}
              hint="sq. m, faculty, Mbps, count…"
            />
          ) : null}

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <Input
              label="APH clause"
              value={form.apH_clause}
              onChange={(event) => update("apH_clause", event.target.value)}
              hint="For example APH 6.14 or APH Annexure-2.1."
              required
            />
            <Input
              label="Penalty codes"
              value={form.penalty_codes}
              onChange={(event) => update("penalty_codes", event.target.value)}
              hint="Comma separated APH 7.4 codes, for example 7.4a, 7.4c."
            />
            <Input
              label="Weight (optional)"
              type="number"
              step="0.5"
              min="0"
              value={form.weight}
              onChange={(event) => update("weight", event.target.value)}
              hint="Overrides the severity weight when set."
            />
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Select
              label="Severity"
              value={form.severity}
              onValueChange={(value) => update("severity", value as Severity)}
              options={SEVERITY_OPTIONS.map((severity) => ({
                value: severity,
                label: humanizeEnum(severity),
              }))}
            />
            <Input
              label="Applies to"
              value={form.applies_to}
              onChange={(event) => update("applies_to", event.target.value)}
              hint="Comma-separated application types, levels, or ALL."
            />
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Select
              label="Programme family scope"
              value={form.applies_to_family || "__all__"}
              onValueChange={(value) =>
                update("applies_to_family", value === "__all__" ? "" : value)
              }
              options={[
                { value: "__all__", label: "All families" },
                ...FAMILY_OPTIONS.map((family) => ({
                  value: family,
                  label: humanizeEnum(family),
                })),
              ]}
            />
            <Select
              label="Programme level scope"
              value={form.applies_to_level || "__all__"}
              onValueChange={(value) =>
                update("applies_to_level", value === "__all__" ? "" : value)
              }
              options={[
                { value: "__all__", label: "All levels" },
                ...LEVEL_OPTIONS.map((level) => ({
                  value: level,
                  label: humanizeEnum(level),
                })),
              ]}
            />
          </div>

          <Textarea
            label="Explanation template"
            value={form.explanation_template}
            onChange={(event) => update("explanation_template", event.target.value)}
            rows={2}
            hint="Quotes the clause and fills in observed and required values."
          />
          <Textarea
            label="Metric parameters (JSON)"
            value={form.metric_params}
            onChange={(event) => update("metric_params", event.target.value)}
            rows={4}
            hint='Required for RATIO/SUM/COUNT, for example {"numerator": "faculty.total", "denominator": "students.total"}.'
          />

          <div className="grid gap-2 sm:grid-cols-2">
            <label className="flex items-center gap-2 text-13 font-medium text-ink-700">
              <input
                type="checkbox"
                checked={form.mandatory}
                onChange={(event) => update("mandatory", event.target.checked)}
                className="size-4 rounded border-line text-saffron focus-visible:ring-focus"
              />
              Mandatory (blocks Nil Deficiency)
            </label>
            <label className="flex items-center gap-2 text-13 font-medium text-ink-700">
              <input
                type="checkbox"
                checked={form.illustrative}
                onChange={(event) => update("illustrative", event.target.checked)}
                className="size-4 rounded border-line text-saffron focus-visible:ring-focus"
              />
              Illustrative, not an AICTE norm
            </label>
            <label className="flex items-center gap-2 text-13 font-medium text-ink-700">
              <input
                type="checkbox"
                checked={form.needs_verification}
                onChange={(event) => update("needs_verification", event.target.checked)}
                className="size-4 rounded border-line text-saffron focus-visible:ring-focus"
              />
              Clause or threshold still needs verification
            </label>
            <label className="flex items-center gap-2 text-13 font-medium text-ink-700">
              <input
                type="checkbox"
                checked={form.is_active}
                onChange={(event) => update("is_active", event.target.checked)}
                className="size-4 rounded border-line text-saffron focus-visible:ring-focus"
              />
              Active (included in evaluations)
            </label>
          </div>

          {error ? (
            <p className="rounded-input border border-breach bg-breach-soft p-3 text-13 text-breach-strong">
              {error}
            </p>
          ) : null}

          {impact ? (
            <div
              className={`rounded-input border p-3 text-13 ${
                impact.red_flips > 0
                  ? "border-breach bg-breach-soft text-breach-strong"
                  : impact.amber_flips > 0
                    ? "border-watch bg-watch-soft text-watch-strong"
                    : "border-line bg-paper text-ink-700"
              }`}
            >
              <p className="font-semibold">{impact.message}</p>
              <p className="mt-1 text-12">
                {impact.red_flips} RED flips · {impact.amber_flips} AMBER flips ·{" "}
                {impact.improved} improved · {impact.unchanged} unchanged
              </p>
              {impact.affected.length > 0 ? (
                <ul className="mt-2 space-y-1 text-12">
                  {impact.affected.map((institution) => (
                    <li key={institution.institution_id}>
                      {institution.institution_name} ({institution.region}):{" "}
                      {institution.current_status} → {institution.projected_status}
                    </li>
                  ))}
                </ul>
              ) : null}
            </div>
          ) : null}

          <DialogFooter>
            <Button variant="secondary" type="button" onClick={onClose}>
              Cancel
            </Button>
            <Button
              variant="secondary"
              type="button"
              onClick={handleImpact}
              disabled={impactMutation.isPending}
            >
              {impactMutation.isPending ? "Projecting…" : "Preview impact"}
            </Button>
            <Button type="submit" disabled={saveMutation.isPending}>
              {saveMutation.isPending ? "Saving…" : rule ? "Save changes" : "Create rule"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function RuleHistoryDialog({
  token,
  rule,
  onClose,
}: {
  token: string;
  rule: ComplianceRule;
  onClose: () => void;
}) {
  const historyQuery = useQuery({
    queryKey: ["compliance-rule-history", rule.id],
    queryFn: () => getComplianceRuleHistory(token, rule.id),
  });

  return (
    <Dialog open onOpenChange={(open) => (!open ? onClose() : undefined)}>
      <DialogContent className="max-w-2xl">
        <DialogHeader>
          <DialogTitle>Change history · {rule.code}</DialogTitle>
          <DialogDescription>
            Every create, edit and activation change is written to the audit log with the actor,
            timestamp and before/after values.
          </DialogDescription>
        </DialogHeader>

        {historyQuery.isPending ? (
          <div className="mt-4 space-y-2">
            {[0, 1, 2].map((item) => (
              <Skeleton key={item} className="h-16 w-full" />
            ))}
          </div>
        ) : historyQuery.isError ? (
          <p className="mt-4 rounded-input border border-breach bg-breach-soft p-3 text-13 text-breach-strong">
            {messageFor(historyQuery.error, "The history could not be loaded.")}
          </p>
        ) : historyQuery.data && historyQuery.data.items.length > 0 ? (
          <ol className="mt-4 divide-y divide-line border-y border-line">
            {historyQuery.data.items.map((entry) => (
              <li key={entry.id} className="py-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-13 font-medium text-ink">
                    {humanizeEnum(entry.action)}
                  </p>
                  <p className="text-12 text-ink-500">{formatDateTime(entry.created_at)}</p>
                </div>
                <p className="mt-0.5 text-12 text-ink-500">
                  {entry.actor_name ?? "Seed or system"} · {entry.changed_fields.length} field
                  {entry.changed_fields.length === 1 ? "" : "s"} changed
                </p>
                {entry.changed_fields.length > 0 ? (
                  <p className="mt-1 font-mono text-11 leading-5 text-ink-700">
                    {entry.changed_fields.join(", ")}
                  </p>
                ) : null}
              </li>
            ))}
          </ol>
        ) : (
          <p className="mt-4 rounded-input border border-line bg-paper p-3 text-13 text-ink-700">
            No audited changes are recorded for this rule yet.
          </p>
        )}

        <DialogFooter>
          <Button variant="secondary" type="button" onClick={onClose}>
            Close
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function ScoringPanel({
  token,
  config,
}: {
  token: string;
  config: ComplianceConfig;
}) {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [weights, setWeights] = useState<SeverityWeights>(config.severity_weights);
  const [breakpoints, setBreakpoints] = useState<RagBreakpoints>(config.rag_breakpoints);
  const [error, setError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: (input: ComplianceConfigUpdate) => updateComplianceConfig(token, input),
    onSuccess: () => {
      toast({
        title: "Scoring configuration saved",
        description: "New evaluations use these weights and status bands.",
      });
      setError(null);
      void queryClient.invalidateQueries({ queryKey: ["compliance-config"] });
      void queryClient.invalidateQueries({ queryKey: ["compliance-monitor"] });
      void queryClient.invalidateQueries({ queryKey: ["compliance-trend"] });
      void queryClient.invalidateQueries({ queryKey: ["compliance-preview"] });
    },
    onError: (mutationError) => {
      setError(messageFor(mutationError, "The configuration could not be saved."));
    },
  });

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (breakpoints.amber_below < breakpoints.red_below) {
      setError("The AMBER breakpoint must be greater than or equal to the RED breakpoint.");
      return;
    }
    setError(null);
    mutation.mutate({ severity_weights: weights, rag_breakpoints: breakpoints });
  };

  const numberField = (
    label: string,
    value: number,
    onChange: (value: number) => void,
  ) => (
    <Input
      label={label}
      type="number"
      min="0"
      step="0.5"
      value={String(value)}
      onChange={(event) => onChange(Number(event.target.value))}
    />
  );

  return (
    <form
      onSubmit={handleSubmit}
      className="rounded-panel border border-line bg-surface p-5 sm:p-6"
    >
      <div className="flex items-start gap-3">
        <Activity aria-hidden="true" className="mt-0.5 size-5 text-ink-500" />
        <div>
          <h2 className="font-serif text-20 font-semibold text-ink">Scoring and status bands</h2>
          <p className="mt-1 text-13 text-ink-500">
            The score is earned severity weight divided by assessed severity weight. Missing
            metrics are excluded from the score and counted as “data missing”. A mandatory failure
            cannot be GREEN, and a failed CRITICAL rule forces RED regardless of score.
          </p>
        </div>
      </div>

      <div className="mt-5 grid grid-cols-1 gap-6 lg:grid-cols-2">
        <fieldset>
          <legend className="text-13 font-semibold text-ink">Severity weights</legend>
          <div className="mt-3 grid grid-cols-2 gap-3">
            {numberField("CRITICAL", weights.CRITICAL, (value) =>
              setWeights((current) => ({ ...current, CRITICAL: value })),
            )}
            {numberField("HIGH", weights.HIGH, (value) =>
              setWeights((current) => ({ ...current, HIGH: value })),
            )}
            {numberField("MEDIUM", weights.MEDIUM, (value) =>
              setWeights((current) => ({ ...current, MEDIUM: value })),
            )}
            {numberField("LOW", weights.LOW, (value) =>
              setWeights((current) => ({ ...current, LOW: value })),
            )}
          </div>
        </fieldset>

        <fieldset>
          <legend className="text-13 font-semibold text-ink">RED / AMBER / GREEN bands</legend>
          <div className="mt-3 grid grid-cols-2 gap-3">
            {numberField("RED below", breakpoints.red_below, (value) =>
              setBreakpoints((current) => ({ ...current, red_below: value })),
            )}
            {numberField("AMBER below", breakpoints.amber_below, (value) =>
              setBreakpoints((current) => ({ ...current, amber_below: value })),
            )}
          </div>
          <p className="mt-3 text-12 leading-5 text-ink-500">
            Scores below the RED bound are RED. Scores below the AMBER bound are AMBER. Everything
            else is GREEN.
          </p>
        </fieldset>
      </div>

      {error ? (
        <p className="mt-4 rounded-input border border-breach bg-breach-soft p-3 text-13 text-breach-strong">
          {error}
        </p>
      ) : null}

      <div className="mt-5 flex flex-wrap items-center gap-3 border-t border-line pt-4">
        <Button type="submit" disabled={mutation.isPending}>
          {mutation.isPending ? "Saving…" : "Save configuration"}
        </Button>
        <p className="text-12 text-ink-500">
          Last updated {formatDateTime(config.updated_at)}. Configuration edits are audited.
        </p>
      </div>
    </form>
  );
}

function NumberCell({
  label,
  value,
  onChange,
  step = "0.5",
  integer = false,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  step?: string;
  integer?: boolean;
}) {
  return (
    <input
      aria-label={label}
      type="number"
      min="0"
      step={integer ? "1" : step}
      value={value}
      onChange={(event) => onChange(event.target.value)}
      className="h-9 w-full rounded-input border border-line bg-surface px-2 text-13 tabular-nums text-ink focus-visible:border-focus focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
    />
  );
}

type RatioMap = Record<string, Record<string, string>>;

function RatioTable({
  title,
  description,
  value,
  onChange,
  unitLabel,
}: {
  title: string;
  description: string;
  value: RatioMap;
  onChange: (next: RatioMap) => void;
  unitLabel: string;
}) {
  const families = Object.keys(value).sort();
  const levels = Array.from(
    new Set(families.flatMap((family) => Object.keys(value[family] ?? {}))),
  );
  if (families.length === 0) {
    return (
      <p className="text-12 text-ink-500">No {title.toLowerCase()} rows are configured yet.</p>
    );
  }
  return (
    <div>
      <p className="text-13 font-semibold text-ink">{title}</p>
      <p className="mt-0.5 text-12 leading-5 text-ink-500">{description}</p>
      <div className="mt-2 overflow-x-auto rounded-input border border-line">
        <table className="w-full min-w-[520px] text-left text-12">
          <thead>
            <tr className="border-b border-line bg-paper">
              <th scope="col" className="px-2 py-1.5 font-semibold text-ink-700">
                Family
              </th>
              {levels.map((level) => (
                <th key={level} scope="col" className="px-2 py-1.5 font-semibold text-ink-700">
                  {humanizeEnum(level)}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {families.map((family) => (
              <tr key={family}>
                <th scope="row" className="px-2 py-1.5 text-left font-medium text-ink-700">
                  {humanizeEnum(family)}
                </th>
                {levels.map((level) => (
                  <td key={`${family}-${level}`} className="px-2 py-1.5">
                    <NumberCell
                      label={`${title} ${family} ${level} ${unitLabel}`}
                      value={value[family]?.[level] ?? ""}
                      onChange={(next) =>
                        onChange({
                          ...value,
                          [family]: { ...(value[family] ?? {}), [level]: next },
                        })
                      }
                    />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

type NumberMap = Record<string, string>;

function FlatNorms({
  title,
  description,
  value,
  onChange,
  unitLabel,
}: {
  title: string;
  description: string;
  value: NumberMap;
  onChange: (next: NumberMap) => void;
  unitLabel: string;
}) {
  const keys = Object.keys(value).sort();
  if (keys.length === 0) {
    return (
      <p className="text-12 text-ink-500">No {title.toLowerCase()} values are configured yet.</p>
    );
  }
  return (
    <div>
      <p className="text-13 font-semibold text-ink">{title}</p>
      <p className="mt-0.5 text-12 leading-5 text-ink-500">{description}</p>
      <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-2">
        {keys.map((key) => (
          <div key={key} className="flex items-center justify-between gap-2">
            <span className="text-12 text-ink-700">{humanizeEnum(key)}</span>
            <div className="w-28">
              <NumberCell
                label={`${title} ${key} ${unitLabel}`}
                value={value[key]}
                onChange={(next) => onChange({ ...value, [key]: next })}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function NormsPanel({
  token,
  config,
}: {
  token: string;
  config: ComplianceConfig;
}) {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [error, setError] = useState<string | null>(null);

  const toRatioMap = (source: Record<string, Record<string, number>>): RatioMap =>
    Object.fromEntries(
      Object.entries(source).map(([family, levels]) => [
        family,
        Object.fromEntries(
          Object.entries(levels).map(([level, ratio]) => [level, String(ratio)]),
        ),
      ]),
    );

  const toNumberMap = (source: Record<string, number>): NumberMap =>
    Object.fromEntries(Object.entries(source).map(([key, value]) => [key, String(value)]));

  const [fsrRatios, setFsrRatios] = useState<RatioMap>(() => toRatioMap(config.fsr_ratios));
  const [pcRatios, setPcRatios] = useState<RatioMap>(() => toRatioMap(config.pc_ratios));
  const [areaNorms, setAreaNorms] = useState<NumberMap>(() => toNumberMap(config.area_norms));
  const [libraryNorms, setLibraryNorms] = useState<NumberMap>(() =>
    toNumberMap(config.library_norms),
  );
  const [cadreRatios, setCadreRatios] = useState<Record<string, string>>(() =>
    Object.fromEntries(
      Object.entries(config.cadre_ratios).map(([key, value]) => [key, value.join(",")]),
    ),
  );
  const [tiers, setTiers] = useState<{ max_intake: string; mbps: string }[]>(() =>
    config.bandwidth_tiers.map((tier) => ({
      max_intake: tier.max_intake === null ? "" : String(tier.max_intake),
      mbps: String(tier.mbps),
    })),
  );

  const mutation = useMutation({
    mutationFn: (input: ComplianceConfigUpdate) => updateComplianceConfig(token, input),
    onSuccess: () => {
      toast({
        title: "Norm configuration saved",
        description: "Calculators use these values on the next evaluation.",
      });
      setError(null);
      void queryClient.invalidateQueries({ queryKey: ["compliance-config"] });
      void queryClient.invalidateQueries({ queryKey: ["compliance-monitor"] });
      void queryClient.invalidateQueries({ queryKey: ["compliance-trend"] });
      void queryClient.invalidateQueries({ queryKey: ["compliance-preview"] });
    },
    onError: (mutationError) => {
      setError(messageFor(mutationError, "The norm configuration could not be saved."));
    },
  });

  const buildPayload = (): ComplianceConfigUpdate | string => {
    const parseRatioMap = (source: RatioMap, label: string) => {
      const parsed: Record<string, Record<string, number>> = {};
      for (const [family, levels] of Object.entries(source)) {
        const parsedLevels: Record<string, number> = {};
        for (const [level, raw] of Object.entries(levels)) {
          if (raw.trim() === "") {
            continue;
          }
          const value = Number(raw);
          if (!Number.isFinite(value) || value <= 0) {
            return `${label}: ${humanizeEnum(family)} ${level} must be a positive number.`;
          }
          parsedLevels[level] = value;
        }
        if (Object.keys(parsedLevels).length > 0) {
          parsed[family] = parsedLevels;
        }
      }
      return parsed;
    };

    const parseNumberMap = (source: NumberMap, label: string) => {
      const parsed: Record<string, number> = {};
      for (const [key, raw] of Object.entries(source)) {
        if (raw.trim() === "") {
          continue;
        }
        const value = Number(raw);
        if (!Number.isFinite(value) || value < 0) {
          return `${label}: ${humanizeEnum(key)} must be a non-negative number.`;
        }
        parsed[key] = value;
      }
      return parsed;
    };

    const parsedFsr = parseRatioMap(fsrRatios, "Faculty-student ratio");
    if (typeof parsedFsr === "string") return parsedFsr;
    const parsedPc = parseRatioMap(pcRatios, "Students per computer");
    if (typeof parsedPc === "string") return parsedPc;
    const parsedArea = parseNumberMap(areaNorms, "Area norms");
    if (typeof parsedArea === "string") return parsedArea;
    const parsedLibrary = parseNumberMap(libraryNorms, "Library norms");
    if (typeof parsedLibrary === "string") return parsedLibrary;

    const parsedCadre: Record<string, number[]> = {};
    for (const [key, raw] of Object.entries(cadreRatios)) {
      const parts = raw
        .split(",")
        .map((part) => part.trim())
        .filter(Boolean)
        .map(Number);
      if (parts.length !== 3 || parts.some((part) => !Number.isFinite(part) || part < 0)) {
        return `Cadre ratio ${key} must be three comma-separated numbers, e.g. 1,2,6.`;
      }
      parsedCadre[key] = parts.map((part) => Math.round(part));
    }

    const parsedTiers: BandwidthTier[] = [];
    for (const tier of tiers) {
      const mbps = Number(tier.mbps);
      if (!Number.isFinite(mbps) || mbps <= 0) {
        return "Every bandwidth tier needs a positive Mbps value.";
      }
      const maxIntake =
        tier.max_intake.trim() === "" ? null : Number(tier.max_intake);
      if (maxIntake !== null && (!Number.isFinite(maxIntake) || maxIntake < 0)) {
        return "The bandwidth tier intake must be a non-negative number or blank.";
      }
      parsedTiers.push({
        max_intake: maxIntake === null ? null : Math.round(maxIntake),
        mbps: Math.round(mbps),
      });
    }

    return {
      fsr_ratios: parsedFsr,
      pc_ratios: parsedPc,
      area_norms: parsedArea,
      library_norms: parsedLibrary,
      cadre_ratios: parsedCadre,
      bandwidth_tiers: parsedTiers,
    };
  };

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const payload = buildPayload();
    if (typeof payload === "string") {
      setError(payload);
      return;
    }
    setError(null);
    mutation.mutate(payload);
  };

  const cadreKeys = Object.keys(cadreRatios).sort();

  return (
    <form
      onSubmit={handleSubmit}
      className="space-y-5 rounded-panel border border-line bg-surface p-5 sm:p-6"
    >
      <div>
        <h2 className="font-serif text-20 font-semibold text-ink">Calculator norms</h2>
        <p className="mt-1 text-13 leading-5 text-ink-500">
          These values feed the APH calculators for faculty, area, library and computing. They live
          in the database so the handbook figures can be corrected without a code change. Confirm
          each value against the current AICTE Approval Process Handbook.
        </p>
      </div>

      <RatioTable
        title="Faculty-student ratio"
        description="Students per faculty member. The calculator sums the sanctioned intake times the programme duration for every programme in scope."
        value={fsrRatios}
        onChange={setFsrRatios}
        unitLabel="students per faculty"
      />

      <div>
        <p className="text-13 font-semibold text-ink">Cadre ratio</p>
        <p className="mt-0.5 text-12 leading-5 text-ink-500">
          Professor, Associate Professor and Assistant Professor share for each family and level.
          The Principal or Director occupies the first Professor slot.
        </p>
        <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-2">
          {cadreKeys.map((key) => (
            <div key={key} className="flex items-center justify-between gap-2">
              <label className="text-12 text-ink-700" htmlFor={`cadre-${key}`}>
                {key.replace("|", " · ")}
              </label>
              <div className="w-28">
                <input
                  id={`cadre-${key}`}
                  aria-label={`Cadre ratio ${key}`}
                  value={cadreRatios[key]}
                  onChange={(event) =>
                    setCadreRatios((current) => ({ ...current, [key]: event.target.value }))
                  }
                  className="h-9 w-full rounded-input border border-line bg-surface px-2 text-13 tabular-nums text-ink focus-visible:border-focus focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus"
                />
              </div>
            </div>
          ))}
        </div>
      </div>

      <FlatNorms
        title="Area norms"
        description="Fixed administrative and amenities area plus the circulation factor applied on top of the instructional area."
        value={areaNorms}
        onChange={setAreaNorms}
        unitLabel="value"
      />

      <FlatNorms
        title="Library norms"
        description="Journals per course and the share of students that must have a reading-room seat and a digital library computer."
        value={libraryNorms}
        onChange={setLibraryNorms}
        unitLabel="value"
      />

      <RatioTable
        title="Students per computer"
        description="Computing ratio used to compute the required number of computers for a programme group."
        value={pcRatios}
        onChange={setPcRatios}
        unitLabel="students per computer"
      />

      <div>
        <p className="text-13 font-semibold text-ink">Internet bandwidth tiers</p>
        <p className="mt-0.5 text-12 leading-5 text-ink-500">
          Required Mbps by sanctioned intake. A blank intake is the catch-all top tier.
        </p>
        <div className="mt-2 space-y-2">
          {tiers.map((tier, index) => (
            <div key={index} className="flex items-end gap-2">
              <div className="w-40">
                <Input
                  label="Max intake"
                  type="number"
                  min="0"
                  step="1"
                  value={tier.max_intake}
                  onChange={(event) =>
                    setTiers((current) =>
                      current.map((row, rowIndex) =>
                        rowIndex === index
                          ? { ...row, max_intake: event.target.value }
                          : row,
                      ),
                    )
                  }
                />
              </div>
              <div className="w-40">
                <Input
                  label="Mbps"
                  type="number"
                  min="1"
                  step="1"
                  value={tier.mbps}
                  onChange={(event) =>
                    setTiers((current) =>
                      current.map((row, rowIndex) =>
                        rowIndex === index ? { ...row, mbps: event.target.value } : row,
                      ),
                    )
                  }
                />
              </div>
              <Button
                variant="quiet"
                size="sm"
                type="button"
                onClick={() =>
                  setTiers((current) => current.filter((_, rowIndex) => rowIndex !== index))
                }
              >
                Remove
              </Button>
            </div>
          ))}
        </div>
        <Button
          variant="secondary"
          size="sm"
          type="button"
          className="mt-2"
          onClick={() => setTiers((current) => [...current, { max_intake: "", mbps: "" }])}
        >
          <Plus aria-hidden="true" className="size-3.5" />
          Add tier
        </Button>
      </div>

      {error ? (
        <p className="rounded-input border border-breach bg-breach-soft p-3 text-13 text-breach-strong">
          {error}
        </p>
      ) : null}

      <div className="flex flex-wrap items-center gap-3 border-t border-line pt-4">
        <Button type="submit" disabled={mutation.isPending}>
          {mutation.isPending ? "Saving…" : "Save norms"}
        </Button>
        <p className="text-12 text-ink-500">
          Last updated {formatDateTime(config.updated_at)}. Every edit is audited.
        </p>
      </div>
    </form>
  );
}

interface RuleFilters {
  category: string;
  search: string;
  needsVerification: boolean;
  illustrative: boolean;
  mandatory: boolean;
}

const EMPTY_FILTERS: RuleFilters = {
  category: "",
  search: "",
  needsVerification: false,
  illustrative: false,
  mandatory: false,
};

export default function ComplianceAdminPage() {
  const { user, token } = useAuth();
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [editor, setEditor] = useState<{ rule: ComplianceRule | null } | null>(null);
  const [historyRule, setHistoryRule] = useState<ComplianceRule | null>(null);
  const [selectedInstitutionId, setSelectedInstitutionId] = useState<string | null>(null);
  const [filters, setFilters] = useState<RuleFilters>(EMPTY_FILTERS);

  const authToken = token ?? "";

  const monitorQuery = useQuery({
    queryKey: ["compliance-monitor"],
    queryFn: () => getComplianceMonitor(authToken, { pageSize: 100 }),
    enabled: Boolean(authToken && user),
  });
  const rulesQuery = useQuery({
    queryKey: ["compliance-rules", filters],
    queryFn: () =>
      listComplianceRules(authToken, {
        pageSize: 100,
        category: filters.category || undefined,
        search: filters.search.trim() || undefined,
        needsVerification: filters.needsVerification ? true : undefined,
        illustrative: filters.illustrative ? true : undefined,
        mandatory: filters.mandatory ? true : undefined,
      }),
    enabled: Boolean(authToken && user),
  });
  const metricsQuery = useQuery({
    queryKey: ["compliance-metrics"],
    queryFn: () => listComplianceMetrics(authToken),
    enabled: Boolean(authToken && user),
  });
  const configQuery = useQuery({
    queryKey: ["compliance-config"],
    queryFn: () => getComplianceConfig(authToken),
    enabled: Boolean(authToken && user),
  });

  const activeInstitution = useMemo(() => {
    const items = monitorQuery.data?.items ?? [];
    return (
      items.find((item) => item.institution_id === selectedInstitutionId) ??
      items.find((item) => item.latest_status !== null) ??
      items[0]
    );
  }, [monitorQuery.data, selectedInstitutionId]);

  const trendQuery = useQuery({
    queryKey: ["compliance-trend", activeInstitution?.institution_id],
    queryFn: () =>
      getInstitutionComplianceTrend(authToken, activeInstitution?.institution_id ?? "", 50),
    enabled: Boolean(authToken && activeInstitution),
  });

  const runMutation = useMutation({
    mutationFn: () => runComplianceMonitor(authToken),
    onSuccess: (result) => {
      toast({ title: "Monitoring re-evaluated", description: result.message });
      void queryClient.invalidateQueries({ queryKey: ["compliance-monitor"] });
      void queryClient.invalidateQueries({ queryKey: ["compliance-trend"] });
      void queryClient.invalidateQueries({ queryKey: ["compliance-preview"] });
    },
    onError: (error) => {
      toast({
        title: "Re-evaluation failed",
        description: messageFor(error, "The monitoring run could not be completed."),
        variant: "error",
      });
    },
  });

  const toggleActiveMutation = useMutation({
    mutationFn: (rule: ComplianceRule) =>
      updateComplianceRule(authToken, rule.id, { is_active: !rule.is_active }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["compliance-rules"] });
      void queryClient.invalidateQueries({ queryKey: ["compliance-monitor"] });
      void queryClient.invalidateQueries({ queryKey: ["compliance-preview"] });
    },
    onError: (error) => {
      toast({
        title: "Rule could not be updated",
        description: messageFor(error, "Try again."),
        variant: "error",
      });
    },
  });

  if (!user) {
    return null;
  }

  const items = monitorQuery.data?.items ?? [];
  const counts = {
    red: items.filter((item) => item.latest_status === "RED").length,
    amber: items.filter((item) => item.latest_status === "AMBER").length,
    green: items.filter((item) => item.latest_status === "GREEN").length,
    missing: items.filter((item) => item.latest_status === null).length,
  };
  const rules = rulesQuery.data?.items ?? [];
  const needsVerificationCount = rules.filter((rule) => rule.needs_verification).length;
  const illustrativeCount = rules.filter((rule) => rule.illustrative).length;

  return (
    <>
      <PageHeader
        eyebrow="Oversight"
        title="Compliance monitoring"
        description="Configure the APH norms, inspect rule-by-rule outcomes and track institution score trends. Every threshold is editable data with the clause that backs it."
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => {
                void monitorQuery.refetch();
                void rulesQuery.refetch();
                void configQuery.refetch();
              }}
              disabled={monitorQuery.isFetching}
            >
              <RefreshCw
                aria-hidden="true"
                className={monitorQuery.isFetching ? "size-4 animate-spin" : "size-4"}
              />
              Refresh
            </Button>
            <Button
              size="sm"
              onClick={() => runMutation.mutate()}
              disabled={runMutation.isPending}
            >
              <Activity aria-hidden="true" className="size-4" />
              {runMutation.isPending ? "Evaluating…" : "Re-evaluate now"}
            </Button>
          </div>
        }
      />

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <MetricSummary label="RED institutions" value={counts.red} tone="breach" />
        <MetricSummary label="AMBER institutions" value={counts.amber} tone="watch" />
        <MetricSummary label="GREEN institutions" value={counts.green} tone="ok" />
        <MetricSummary label="Awaiting data" value={counts.missing} tone="ink" />
      </div>

      <Tabs defaultValue="monitoring" className="mt-6">
        <TabsList aria-label="Compliance administration sections">
          <TabsTrigger value="monitoring">Monitoring</TabsTrigger>
          <TabsTrigger value="rules">Rules</TabsTrigger>
          <TabsTrigger value="scoring">Scoring</TabsTrigger>
          <TabsTrigger value="norms">Norm calculators</TabsTrigger>
        </TabsList>

        <TabsContent value="monitoring">
          <div className="grid grid-cols-1 gap-5">
            <section
              className="min-w-0 rounded-panel border border-line bg-surface"
              aria-label="Institution monitoring list"
            >
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-4 py-3">
                <div>
                  <h2 className="font-serif text-20 font-semibold text-ink">Institutions</h2>
                  <p className="mt-0.5 text-12 text-ink-500">
                    Latest stored evaluation per institution. Select a row to chart its history.
                  </p>
                </div>
                <span className="text-12 text-ink-500">{items.length} in scope</span>
              </div>

              {monitorQuery.isPending ? (
                <div className="space-y-3 p-4" role="status">
                  {[0, 1, 2, 3].map((item) => (
                    <Skeleton key={item} className="h-12 w-full" />
                  ))}
                  <span className="sr-only">Loading monitoring list</span>
                </div>
              ) : monitorQuery.isError ? (
                <div className="p-4">
                  <p className="rounded-input border border-breach bg-breach-soft p-3 text-13 text-breach-strong">
                    {messageFor(monitorQuery.error, "Monitoring data could not be loaded.")}
                  </p>
                  <Button
                    variant="secondary"
                    size="sm"
                    className="mt-3"
                    onClick={() => void monitorQuery.refetch()}
                  >
                    Retry
                  </Button>
                </div>
              ) : items.length === 0 ? (
                <div className="p-4">
                  <EmptyState
                    message="No institutions are in your monitoring scope."
                    action={
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={() => void monitorQuery.refetch()}
                      >
                        Refresh
                      </Button>
                    }
                  />
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <Table density="dense">
                    <TableHeader>
                      <TableRow>
                        <TableHead>Institution</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>Score</TableHead>
                        <TableHead>Failed</TableHead>
                        <TableHead>Data missing</TableHead>
                        <TableHead>Last evaluated</TableHead>
                        <TableHead>
                          <span className="sr-only">Trend</span>
                        </TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {items.map((item) => {
                        const selected =
                          item.institution_id === activeInstitution?.institution_id;
                        return (
                          <TableRow
                            key={item.institution_id}
                            className={selected ? "bg-paper" : undefined}
                          >
                            <TableCell>
                              <p className="font-medium text-ink">{item.institution_name}</p>
                              <p className="mt-0.5 text-12 text-ink-500">
                                {item.region} · {item.state}
                              </p>
                            </TableCell>
                            <TableCell>
                              {item.latest_status ? (
                                <StatusPill status={HEALTH_TONE[item.latest_status]}>
                                  {HEALTH_LABEL[item.latest_status]}
                                </StatusPill>
                              ) : (
                                <span className="text-12 text-ink-500">Not evaluated</span>
                              )}
                            </TableCell>
                            <TableCell className="tabular-nums">
                              {item.latest_score === null
                                ? "—"
                                : `${item.latest_score.toFixed(1)}/100`}
                            </TableCell>
                            <TableCell className="tabular-nums">
                              {item.latest_failed_count ?? "—"}
                            </TableCell>
                            <TableCell className="tabular-nums">
                              {item.latest_missing_count ?? "—"}
                            </TableCell>
                            <TableCell className="text-12 text-ink-500">
                              <p>{formatDateTime(item.latest_evaluated_at)}</p>
                              {item.latest_trigger ? (
                                <p className="mt-0.5 text-11 text-ink-300">
                                  {item.latest_trigger}
                                </p>
                              ) : null}
                            </TableCell>
                            <TableCell className="text-right">
                              <Button
                                variant="quiet"
                                size="sm"
                                onClick={() => setSelectedInstitutionId(item.institution_id)}
                              >
                                <TrendingUp aria-hidden="true" className="size-4" />
                                Trend
                              </Button>
                            </TableCell>
                          </TableRow>
                        );
                      })}
                    </TableBody>
                  </Table>
                </div>
              )}
            </section>

            <section
              className="min-w-0 rounded-panel border border-line bg-surface p-4 sm:p-5"
              aria-label="Institution score trend"
            >
              <div className="flex items-center gap-2">
                <TrendingUp aria-hidden="true" className="size-4 text-ink-500" />
                <h2 className="font-serif text-20 font-semibold text-ink">Score history</h2>
              </div>
              <div className="mt-4">
                <TrendPanel
                  trend={trendQuery.data}
                  breakpoints={configQuery.data?.rag_breakpoints}
                  loading={trendQuery.isPending && Boolean(activeInstitution)}
                />
              </div>
            </section>
          </div>
        </TabsContent>

        <TabsContent value="rules">
          <section className="rounded-panel border border-line bg-surface">
            <div className="flex flex-wrap items-start justify-between gap-3 border-b border-line px-4 py-3">
              <div>
                <h2 className="font-serif text-20 font-semibold text-ink">Rule catalogue</h2>
                <p className="mt-0.5 max-w-2xl text-12 leading-5 text-ink-500">
                  Each rule cites the APH clause it implements. Rules marked illustrative are
                  project-only demo thresholds and never block a Nil Deficiency result.
                </p>
              </div>
              <Button size="sm" onClick={() => setEditor({ rule: null })}>
                <Plus aria-hidden="true" className="size-4" />
                Add rule
              </Button>
            </div>

            <div className="flex flex-wrap items-end gap-3 border-b border-line bg-paper px-4 py-3">
              <div className="w-64">
                <Input
                  label="Search"
                  value={filters.search}
                  onChange={(event) =>
                    setFilters((current) => ({ ...current, search: event.target.value }))
                  }
                  placeholder="Code, name or clause"
                />
              </div>
              <div className="w-52">
                <Select
                  label="Category"
                  value={filters.category || "__all__"}
                  onValueChange={(value) =>
                    setFilters((current) => ({
                      ...current,
                      category: value === "__all__" ? "" : value,
                    }))
                  }
                  options={[
                    { value: "__all__", label: "All categories" },
                    ...CATEGORY_OPTIONS.map((category) => ({
                      value: category,
                      label: category,
                    })),
                  ]}
                />
              </div>
              <label className="flex h-10 items-center gap-2 text-13 font-medium text-ink-700">
                <input
                  type="checkbox"
                  checked={filters.needsVerification}
                  onChange={(event) =>
                    setFilters((current) => ({
                      ...current,
                      needsVerification: event.target.checked,
                    }))
                  }
                  className="size-4 rounded border-line text-saffron focus-visible:ring-focus"
                />
                Needs verification
              </label>
              <label className="flex h-10 items-center gap-2 text-13 font-medium text-ink-700">
                <input
                  type="checkbox"
                  checked={filters.illustrative}
                  onChange={(event) =>
                    setFilters((current) => ({
                      ...current,
                      illustrative: event.target.checked,
                    }))
                  }
                  className="size-4 rounded border-line text-saffron focus-visible:ring-focus"
                />
                Illustrative only
              </label>
              <label className="flex h-10 items-center gap-2 text-13 font-medium text-ink-700">
                <input
                  type="checkbox"
                  checked={filters.mandatory}
                  onChange={(event) =>
                    setFilters((current) => ({
                      ...current,
                      mandatory: event.target.checked,
                    }))
                  }
                  className="size-4 rounded border-line text-saffron focus-visible:ring-focus"
                />
                Mandatory only
              </label>
              <Button
                variant="quiet"
                size="sm"
                onClick={() => setFilters(EMPTY_FILTERS)}
                disabled={
                  filters.category === "" &&
                  filters.search === "" &&
                  !filters.needsVerification &&
                  !filters.illustrative &&
                  !filters.mandatory
                }
              >
                Clear filters
              </Button>
            </div>

            {rulesQuery.isPending ? (
              <div className="space-y-3 p-4" role="status">
                {[0, 1, 2, 3, 4].map((item) => (
                  <Skeleton key={item} className="h-12 w-full" />
                ))}
                <span className="sr-only">Loading compliance rules</span>
              </div>
            ) : rulesQuery.isError ? (
              <div className="p-4">
                <p className="rounded-input border border-breach bg-breach-soft p-3 text-13 text-breach-strong">
                  {messageFor(rulesQuery.error, "Rules could not be loaded.")}
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
                  message={
                    rulesQuery.data?.total
                      ? "No rule matches these filters."
                      : "No compliance rules are configured."
                  }
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
                      <TableHead>Clause</TableHead>
                      <TableHead>Condition</TableHead>
                      <TableHead>Severity</TableHead>
                      <TableHead>Scope</TableHead>
                      <TableHead>Active</TableHead>
                      <TableHead>
                        <span className="sr-only">Actions</span>
                      </TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {rules.map((rule) => (
                      <TableRow key={rule.id} className={rule.is_active ? undefined : "opacity-60"}>
                        <TableCell className="min-w-64">
                          <p className="font-medium text-ink">{rule.name}</p>
                          <p className="mt-0.5 font-mono text-11 text-ink-500">{rule.code}</p>
                          <div className="mt-1 flex flex-wrap items-center gap-1.5">
                            {!rule.mandatory ? (
                              <span className="rounded-pill bg-neutral-soft px-2 py-0.5 text-11 text-ink-700">
                                Advisory
                              </span>
                            ) : null}
                            {rule.illustrative ? (
                              <span className="rounded-pill bg-watch-soft px-2 py-0.5 text-11 text-watch-strong">
                                Illustrative, not an AICTE norm
                              </span>
                            ) : null}
                            {rule.needs_verification ? (
                              <span className="rounded-pill bg-watch-soft px-2 py-0.5 text-11 text-watch-strong">
                                Needs verification
                              </span>
                            ) : null}
                          </div>
                        </TableCell>
                        <TableCell className="whitespace-nowrap text-12 text-ink-700">
                          {rule.apH_clause}
                        </TableCell>
                        <TableCell className="whitespace-nowrap tabular-nums">
                          {conditionText(rule)}
                        </TableCell>
                        <TableCell>
                          <StatusPill status={SEVERITY_TONE[rule.severity]}>
                            {rule.severity}
                          </StatusPill>
                        </TableCell>
                        <TableCell className="text-12 text-ink-700">
                          <p>{humanizeEnum(rule.applies_to)}</p>
                          {rule.applies_to_family ? (
                            <p className="mt-0.5 text-11 text-ink-500">
                              {humanizeEnum(rule.applies_to_family)}
                              {rule.applies_to_level
                                ? ` · ${humanizeEnum(rule.applies_to_level)}`
                                : ""}
                            </p>
                          ) : rule.applies_to_level ? (
                            <p className="mt-0.5 text-11 text-ink-500">
                              {humanizeEnum(rule.applies_to_level)}
                            </p>
                          ) : null}
                        </TableCell>
                        <TableCell>
                          <button
                            type="button"
                            onClick={() => toggleActiveMutation.mutate(rule)}
                            disabled={toggleActiveMutation.isPending}
                            aria-label={
                              rule.is_active
                                ? `Deactivate ${rule.name}`
                                : `Activate ${rule.name}`
                            }
                            title={
                              rule.is_active ? "Click to deactivate" : "Click to activate"
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
                          <div className="flex justify-end gap-1">
                            <Button
                              variant="quiet"
                              size="sm"
                              onClick={() => setHistoryRule(rule)}
                            >
                              <History aria-hidden="true" className="size-3.5" />
                              History
                            </Button>
                            <Button
                              variant="quiet"
                              size="sm"
                              onClick={() => setEditor({ rule })}
                            >
                              <Pencil aria-hidden="true" className="size-3.5" />
                              Edit
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
              {rules.length} rule{rules.length === 1 ? "" : "s"} shown · {needsVerificationCount}{" "}
              awaiting verification · {illustrativeCount} illustrative. Editing a threshold changes
              live application previews immediately; stored monitoring snapshots refresh on the next
              nightly run or when you select “Re-evaluate now”.
            </p>
          </section>
        </TabsContent>

        <TabsContent value="scoring">
          {configQuery.isPending ? (
            <Skeleton className="h-64 w-full" />
          ) : configQuery.isError ? (
            <div className="rounded-panel border border-line bg-surface p-4">
              <p className="rounded-input border border-breach bg-breach-soft p-3 text-13 text-breach-strong">
                {messageFor(configQuery.error, "Scoring configuration could not be loaded.")}
              </p>
              <Button
                variant="secondary"
                size="sm"
                className="mt-3"
                onClick={() => void configQuery.refetch()}
              >
                Retry
              </Button>
            </div>
          ) : configQuery.data ? (
            <ScoringPanel
              key={configQuery.data.updated_at ?? "default"}
              token={authToken}
              config={configQuery.data}
            />
          ) : null}
        </TabsContent>

        <TabsContent value="norms">
          {configQuery.isPending ? (
            <Skeleton className="h-64 w-full" />
          ) : configQuery.isError ? (
            <div className="rounded-panel border border-line bg-surface p-4">
              <p className="rounded-input border border-breach bg-breach-soft p-3 text-13 text-breach-strong">
                {messageFor(configQuery.error, "Norm configuration could not be loaded.")}
              </p>
              <Button
                variant="secondary"
                size="sm"
                className="mt-3"
                onClick={() => void configQuery.refetch()}
              >
                Retry
              </Button>
            </div>
          ) : configQuery.data ? (
            <NormsPanel
              key={configQuery.data.updated_at ?? "default"}
              token={authToken}
              config={configQuery.data}
            />
          ) : null}
        </TabsContent>
      </Tabs>

      <p className="mt-5 flex items-start gap-2 rounded-panel border border-line bg-surface p-3 text-12 leading-5 text-ink-500">
        <ShieldCheck aria-hidden="true" className="mt-0.5 size-4 shrink-0" />
        Rules marked illustrative are prototype-only values, not AICTE norms. The remaining rules
        cite the APH clause they implement, but every figure still has to be verified against the
        current AICTE Approval Process Handbook before an approval decision relies on it.
      </p>

      {editor ? (
        <RuleDialog
          token={authToken}
          rule={editor.rule}
          metrics={metricsQuery.data?.items ?? []}
          onClose={() => setEditor(null)}
        />
      ) : null}

      {historyRule ? (
        <RuleHistoryDialog
          token={authToken}
          rule={historyRule}
          onClose={() => setHistoryRule(null)}
        />
      ) : null}
    </>
  );
}
