import * as React from "react";

import {
  Button,
  DatePicker,
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  Drawer,
  DrawerClose,
  DrawerContent,
  DrawerDescription,
  DrawerFooter,
  DrawerHeader,
  DrawerTitle,
  DrawerTrigger,
  EmptyState,
  Input,
  ProgressBar,
  RiskBadge,
  ScoreGauge,
  Select,
  Skeleton,
  SlaRing,
  StageTrack,
  Stat,
  StatusPill,
  Stepper,
  Table,
  TableBody,
  TableCaption,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
  Textarea,
  Tooltip,
  useToast,
  type ScoreBand,
  type SlaState,
  type StageTrackEvent,
  type StageTrackStage,
  type StatusPillTone,
  type TableDensity,
  type TableSortDirection,
} from "@/components/ui";
import { cn } from "@/lib/utils";

const navItems = [
  { id: "foundations", label: "Foundations" },
  { id: "actions", label: "Actions" },
  { id: "form-controls", label: "Form controls" },
  { id: "data-display", label: "Data display" },
  { id: "navigation", label: "Navigation" },
  { id: "feedback", label: "Feedback and overlays" },
  { id: "table", label: "Application table" },
];

const coreTokens: Array<{
  name: string;
  note: string;
  swatchClassName: string;
}> = [
  { name: "ink", note: "Primary text", swatchClassName: "bg-ink" },
  { name: "ink-700", note: "Secondary text", swatchClassName: "bg-ink-700" },
  { name: "ink-500", note: "Muted text", swatchClassName: "bg-ink-500" },
  { name: "ink-300", note: "Disabled text", swatchClassName: "bg-ink-300" },
  { name: "ink-100", note: "Subtle fills", swatchClassName: "bg-ink-100" },
  { name: "paper", note: "Page background", swatchClassName: "bg-paper" },
  { name: "surface", note: "Panels", swatchClassName: "bg-surface" },
  { name: "line", note: "Borders", swatchClassName: "bg-line" },
  {
    name: "saffron",
    note: "Primary action only",
    swatchClassName: "bg-saffron",
  },
];

const statusTokens: Array<{
  name: string;
  tone: StatusPillTone;
  className: string;
}> = [
  { name: "ok-soft / ok-strong", tone: "compliant", className: "bg-ok-soft" },
  { name: "watch-soft / watch-strong", tone: "watch", className: "bg-watch-soft" },
  {
    name: "breach-soft / breach-strong",
    tone: "breach",
    className: "bg-breach-soft",
  },
  { name: "info-soft / info-strong", tone: "info", className: "bg-info-soft" },
  {
    name: "neutral-soft / neutral-strong",
    tone: "neutral",
    className: "bg-neutral-soft",
  },
];

const typeScale: Array<{
  token: string;
  sample: string;
  className: string;
  note: string;
}> = [
  {
    token: "text-12",
    sample: "Updated 22 October 2026",
    className: "text-12",
    note: "12 / 16",
  },
  {
    token: "text-13",
    sample: "Required before scrutiny",
    className: "text-13",
    note: "13 / 18",
  },
  {
    token: "text-14",
    sample: "The institution submitted the revised land record.",
    className: "text-14",
    note: "14 / 20",
  },
  {
    token: "text-16",
    sample: "Application summary",
    className: "text-16",
    note: "16 / 24",
  },
  {
    token: "text-20",
    sample: "Compliance overview",
    className: "text-20",
    note: "20 / 28",
  },
  {
    token: "text-28",
    sample: "Scrutiny in progress",
    className: "text-28 font-serif font-semibold",
    note: "28 / 34",
  },
  {
    token: "text-40",
    sample: "Approval workflow",
    className: "text-40 font-serif font-semibold",
    note: "40 / 46",
  },
];

const spacingScale = [
  { label: "4px", className: "w-1" },
  { label: "8px", className: "w-2" },
  { label: "12px", className: "w-3" },
  { label: "16px", className: "w-4" },
  { label: "24px", className: "w-6" },
  { label: "32px", className: "w-8" },
];

const applicationStages: StageTrackStage[] = [
  { id: "submitted", label: "Submitted" },
  { id: "documents", label: "Documents" },
  { id: "scrutiny", label: "Scrutiny" },
  { id: "inspection", label: "Inspection" },
  { id: "committee", label: "Committee" },
  { id: "decision", label: "Decision" },
];

const inProgressEvents: StageTrackEvent[] = [
  { stage: "submitted", at: "12 Oct 2026, 09:20" },
  { stage: "documents", at: "13 Oct 2026, 15:05" },
];

const blockedEvents: StageTrackEvent[] = [
  ...inProgressEvents,
  { stage: "scrutiny", at: "14 Oct 2026, 11:40", blocked: true },
];

const ringExamples: Array<{
  value: number;
  daysLeft: number;
  state: SlaState;
  label: string;
  detail: string;
}> = [
  {
    value: 28,
    daysLeft: 18,
    state: "ok",
    label: "18 days left",
    detail: "Within the scrutiny window",
  },
  {
    value: 72,
    daysLeft: 5,
    state: "watch",
    label: "5 days left",
    detail: "Follow up with the institution",
  },
  {
    value: 94,
    daysLeft: 1,
    state: "breach",
    label: "1 day left",
    detail: "Escalation is due today",
  },
];

const gaugeExamples: Array<{
  value: number;
  band: ScoreBand;
  label: string;
}> = [
  { value: 46, band: "breach", label: "Breach band" },
  { value: 72, band: "watch", label: "Watch band" },
  { value: 88, band: "compliant", label: "Compliant band" },
];

interface ApplicationRow {
  id: string;
  institution: string;
  type: string;
  submitted: string;
  submittedOrder: number;
  daysLeft: number;
  status: StatusPillTone;
}

const applications: ApplicationRow[] = [
  {
    id: "demo-1",
    institution: "Sunrise Institute of Technology (demo)",
    type: "New approval",
    submitted: "12 Oct 2026",
    submittedOrder: 20261012,
    daysLeft: 18,
    status: "compliant",
  },
  {
    id: "demo-2",
    institution: "Riverbend Institute of Management (demo)",
    type: "Extension",
    submitted: "14 Oct 2026",
    submittedOrder: 20261014,
    daysLeft: 5,
    status: "watch",
  },
  {
    id: "demo-3",
    institution: "Greenfield Technical Campus (demo)",
    type: "New approval",
    submitted: "15 Oct 2026",
    submittedOrder: 20261015,
    daysLeft: 2,
    status: "breach",
  },
  {
    id: "demo-4",
    institution: "Lakeview Institute of Engineering (demo)",
    type: "Extension",
    submitted: "16 Oct 2026",
    submittedOrder: 20261016,
    daysLeft: 21,
    status: "compliant",
  },
  {
    id: "demo-5",
    institution: "Northstar Institute of Management (demo)",
    type: "New approval",
    submitted: "17 Oct 2026",
    submittedOrder: 20261017,
    daysLeft: 7,
    status: "info",
  },
  {
    id: "demo-6",
    institution: "Cedar Ridge Institute of Technology (demo)",
    type: "Extension",
    submitted: "18 Oct 2026",
    submittedOrder: 20261018,
    daysLeft: 0,
    status: "breach",
  },
];

type TableSortKey = "institution" | "submitted" | "daysLeft";

const selectOptions = [
  { value: "engineering", label: "Engineering" },
  { value: "management", label: "Management" },
];

const regionOptions = [
  { value: "north", label: "North region" },
  { value: "south", label: "South region" },
  { value: "west", label: "West region" },
  { value: "east", label: "East region" },
];

function DemoCard({
  title,
  description,
  children,
  className,
  contentClassName,
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
  className?: string;
  contentClassName?: string;
}) {
  const titleId = React.useId();

  return (
    <section
      aria-labelledby={titleId}
      className={cn(
        "rounded-panel border border-line bg-surface p-5 sm:p-6",
        className,
      )}
    >
      <h3
        id={titleId}
        className="text-16 font-semibold text-ink"
      >
        {title}
      </h3>
      {description ? (
        <p className="mt-1 max-w-2xl text-13 text-ink-700">{description}</p>
      ) : null}
      <div className={cn("mt-4", contentClassName)}>{children}</div>
    </section>
  );
}

function SectionHeader({
  id,
  index,
  title,
  description,
}: {
  id: string;
  index: string;
  title: string;
  description: string;
}) {
  return (
    <div className="mb-4">
      <p className="text-12 font-medium text-ink-500">
        {index} / Design system
      </p>
      <h2 id={id} className="mt-1 text-28 font-semibold text-ink">
        {title}
      </h2>
      <p className="mt-1 max-w-3xl text-14 text-ink-700">{description}</p>
    </div>
  );
}

function TokenSwatch({
  name,
  note,
  swatchClassName,
}: {
  name: string;
  note: string;
  swatchClassName: string;
}) {
  return (
    <div className="flex items-center gap-3 rounded-input border border-line p-2">
      <span
        aria-hidden="true"
        className={cn(
          "size-10 shrink-0 rounded-input border border-line",
          swatchClassName,
        )}
      />
      <span className="min-w-0">
        <code className="rounded-input bg-ink-100 px-1.5 py-0.5 text-12 font-medium text-ink-700">
          {name}
        </code>
        <span className="mt-1 block text-12 text-ink-500">{note}</span>
      </span>
    </div>
  );
}

export default function DesignSystemPage() {
  const { toast } = useToast();
  const [density, setDensity] = React.useState<TableDensity>("comfortable");
  const [sort, setSort] = React.useState<{
    key: TableSortKey;
    direction: "asc" | "desc";
  }>({ key: "daysLeft", direction: "asc" });

  React.useEffect(() => {
    const previousTitle = document.title;
    document.title = "Design system · AICTE Approval Workflow";
    return () => {
      document.title = previousTitle;
    };
  }, []);

  const sortedApplications = React.useMemo(() => {
    const rows = [...applications];
    rows.sort((first, second) => {
      let comparison = 0;

      if (sort.key === "institution") {
        comparison = first.institution.localeCompare(second.institution);
      } else if (sort.key === "submitted") {
        comparison = first.submittedOrder - second.submittedOrder;
      } else {
        comparison = first.daysLeft - second.daysLeft;
      }

      return sort.direction === "asc" ? comparison : -comparison;
    });
    return rows;
  }, [sort]);

  function handleSort(key: TableSortKey) {
    setSort((current) =>
      current.key === key
        ? {
            key,
            direction: current.direction === "asc" ? "desc" : "asc",
          }
        : { key, direction: "asc" },
    );
  }

  function sortDirectionFor(key: TableSortKey): TableSortDirection {
    return sort.key === key ? sort.direction : "none";
  }

  function raiseDeficiencyToast() {
    toast({
      title: "Deficiency raised",
      description:
        "The institution can now respond with the requested document.",
      variant: "success",
    });
  }

  return (
    <div className="min-h-screen bg-paper text-ink">
      <header className="border-b border-line bg-surface">
        <div className="mx-auto flex max-w-6xl flex-col gap-4 px-4 py-8 sm:px-6 md:flex-row md:items-end md:justify-between lg:px-8">
          <div>
            <p className="text-12 font-medium text-ink-500">
              AICTE approval workflow
            </p>
            <h1 className="mt-1 text-40 font-semibold text-ink">
              Design system
            </h1>
            <p className="mt-2 max-w-2xl text-16 text-ink-700">
              Tokens, accessible components and the signature SLA, stage and
              score views for the approval workflow.
            </p>
          </div>
          <span className="inline-flex w-fit items-center rounded-input border border-line bg-paper px-3 py-1.5 text-13 font-medium text-ink-700">
            Light theme only
          </span>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-4 py-8 sm:px-6 lg:px-8">
        <nav
          aria-label="Design system sections"
          className="rounded-panel border border-line bg-surface px-4 py-3"
        >
          <ul className="flex flex-wrap gap-x-5 gap-y-2">
            {navItems.map((item) => (
              <li key={item.id}>
                <a
                  href={`#${item.id}`}
                  className="inline-flex py-1 text-13 font-medium text-ink-700 underline decoration-line underline-offset-4 hover:text-ink hover:decoration-ink"
                >
                  {item.label}
                </a>
              </li>
            ))}
          </ul>
        </nav>

        <div className="mt-10 space-y-14">
          <section id="foundations" aria-labelledby="foundations-heading">
            <SectionHeader
              id="foundations-heading"
              index="01"
              title="Foundations"
              description="The shared palette, type scale and material rules that every component draws from."
            />
            <div className="grid gap-4 lg:grid-cols-2">
              <DemoCard
                title="Core colour tokens"
                description="Colour is applied through tokens, never raw hex values. Saffron is reserved for the primary action."
              >
                <div className="grid gap-2 sm:grid-cols-2">
                  {coreTokens.map((token) => (
                    <TokenSwatch key={token.name} {...token} />
                  ))}
                </div>
              </DemoCard>

              <DemoCard
                title="Status colour tokens"
                description="Soft tints hold the background while the strong text variant keeps every label above 4.5:1 contrast."
              >
                <div className="space-y-2">
                  {statusTokens.map((token) => (
                    <div
                      key={token.name}
                      className={cn(
                        "flex flex-wrap items-center justify-between gap-2 rounded-input border border-line px-3 py-2",
                        token.className,
                      )}
                    >
                      <StatusPill status={token.tone} />
                      <code className="text-12 text-ink-700">{token.name}</code>
                    </div>
                  ))}
                </div>
              </DemoCard>

              <DemoCard
                title="Type scale"
                description="IBM Plex Sans carries the interface. Source Serif 4 is limited to headings and key figures."
              >
                <dl className="divide-y divide-line">
                  {typeScale.map((item) => (
                    <div
                      key={item.token}
                      className="flex flex-wrap items-baseline justify-between gap-2 py-3 first:pt-0 last:pb-0"
                    >
                      <dt className="min-w-0">
                        <span className={cn("block text-ink", item.className)}>
                          {item.sample}
                        </span>
                      </dt>
                      <dd className="flex items-center gap-2 text-12 text-ink-500">
                        <code className="rounded-input bg-ink-100 px-1.5 py-0.5 text-ink-700">
                          {item.token}
                        </code>
                        <span>{item.note}</span>
                      </dd>
                    </div>
                  ))}
                </dl>
              </DemoCard>

              <DemoCard
                title="Space, radius and elevation"
                description="Spacing starts at 4px. Radius is 4 for controls, 8 for panels and 999 only for status pills. The single shadow is for popovers and menus."
              >
                <div className="space-y-6">
                  <div>
                    <p className="text-13 font-medium text-ink-700">
                      Spacing scale
                    </p>
                    <div className="mt-3 space-y-2">
                      {spacingScale.map((space) => (
                        <div
                          key={space.label}
                          className="flex items-center gap-3"
                        >
                          <span className="w-8 text-12 tabular-nums text-ink-500">
                            {space.label}
                          </span>
                          <span
                            aria-hidden="true"
                            className={cn(
                              "h-2 rounded-input bg-ink-300",
                              space.className,
                            )}
                          />
                        </div>
                      ))}
                    </div>
                  </div>
                  <div>
                    <p className="text-13 font-medium text-ink-700">
                      Radius samples
                    </p>
                    <div className="mt-3 flex flex-wrap items-center gap-3">
                      <span className="rounded-input border border-line bg-surface px-3 py-2 text-12 text-ink-700">
                        Control · 4px
                      </span>
                      <span className="rounded-panel border border-line bg-surface px-3 py-2 text-12 text-ink-700">
                        Panel · 8px
                      </span>
                      <StatusPill status="compliant">Pill · 999px</StatusPill>
                    </div>
                  </div>
                  <div>
                    <p className="text-13 font-medium text-ink-700">
                      Popover elevation
                    </p>
                    <div className="mt-3 rounded-input border border-line bg-surface p-3 text-13 text-ink-700 shadow-popover">
                      Menus and popovers use this elevation. Panels stay flat.
                    </div>
                  </div>
                </div>
              </DemoCard>
            </div>
          </section>

          <section id="actions" aria-labelledby="actions-heading">
            <SectionHeader
              id="actions-heading"
              index="02"
              title="Actions"
              description="Every button names the action it performs. The primary style is the only place saffron appears."
            />
            <div className="grid gap-4 lg:grid-cols-2">
              <DemoCard
                title="Button variants"
                description="Primary, secondary, quiet and destructive actions, plus the disabled state."
              >
                <div className="flex flex-wrap items-center gap-3">
                  <Button type="button" onClick={raiseDeficiencyToast}>
                    Raise deficiency
                  </Button>
                  <Button type="button" variant="secondary">
                    Send to committee
                  </Button>
                  <Button type="button" variant="quiet">
                    Save draft
                  </Button>
                  <Button type="button" variant="destructive">
                    Withdraw application
                  </Button>
                  <Button type="button" disabled>
                    Submit decision
                  </Button>
                </div>
                <div className="mt-4 flex flex-wrap items-center gap-3">
                  <Button type="button" size="sm">
                    Add document
                  </Button>
                  <Button type="button" size="lg" variant="secondary">
                    Start inspection
                  </Button>
                </div>
                <p className="mt-3 text-12 text-ink-500">
                  Disabled actions stay visible until the required step is
                  complete.
                </p>
              </DemoCard>

              <DemoCard
                title="Tooltip"
                description="Tooltips explain a term without hiding the action itself."
              >
                <Tooltip content="The SLA is the working-day limit for the current approval stage.">
                  <Button type="button" variant="quiet">
                    View SLA definition
                  </Button>
                </Tooltip>
                <p className="mt-3 text-12 text-ink-500">
                  Focus or hover the button to reveal the definition.
                </p>
              </DemoCard>
            </div>
          </section>

          <section id="form-controls" aria-labelledby="form-controls-heading">
            <SectionHeader
              id="form-controls-heading"
              index="03"
              title="Form controls"
              description="Labels, hints and inline errors are part of every field. Errors state what happened and how to fix it."
            />
            <div className="grid gap-4 lg:grid-cols-2">
              <DemoCard
                title="Input"
                description="Default, error and disabled states with their visible messages."
              >
                <div className="grid gap-4">
                  <Input
                    label="AICTE institution ID"
                    defaultValue="DEMO-INST-0001"
                    hint="Use the ID shown on the latest approval letter."
                  />
                  <Input
                    label="Registrar email"
                    defaultValue="registrar@sunrise"
                    error="Enter a complete email address, such as registrar@sunrise.example."
                  />
                  <Input
                    label="Application reference"
                    defaultValue="DEMO-2026-001"
                    hint="Assigned after the application is submitted."
                    disabled
                  />
                </div>
              </DemoCard>

              <DemoCard
                title="Select"
                description="A Radix select keeps keyboard and screen-reader behaviour intact."
              >
                <div className="grid gap-4">
                  <Select
                    label="Institution type"
                    placeholder="Select institution type"
                    options={selectOptions}
                    hint="This sets the approval checklist."
                  />
                  <Select
                    label="Reviewing region"
                    placeholder="Select reviewing region"
                    options={regionOptions}
                    error="Select the region that will review this application."
                  />
                  <Select
                    label="Assigned region"
                    options={regionOptions}
                    defaultValue="west"
                    hint="Assigned by the regional office."
                    disabled
                  />
                </div>
              </DemoCard>

              <DemoCard
                title="Textarea"
                description="Multi-line input for deficiency details and inspection notes."
              >
                <div className="grid gap-4">
                  <Textarea
                    label="Deficiency details"
                    defaultValue="The land use certificate is unsigned."
                    hint="Name the missing document and the correction required."
                  />
                  <Textarea
                    label="Inspection notes"
                    defaultValue="The workshop equipment list does not match the submitted inventory."
                    error="Add the corrected inventory before sending the report."
                  />
                </div>
              </DemoCard>

              <DemoCard
                title="Date picker"
                description="A native date input keeps the platform's calendar and keyboard support."
              >
                <div className="grid gap-4">
                  <DatePicker
                    label="Inspection date"
                    defaultValue="2026-11-04"
                    hint="Choose a date at least seven days from today."
                  />
                  <DatePicker
                    label="Response deadline"
                    defaultValue="2026-10-20"
                    error="Choose 29 October 2026 or later."
                  />
                </div>
              </DemoCard>
            </div>
          </section>

          <section id="data-display" aria-labelledby="data-display-heading">
            <SectionHeader
              id="data-display-heading"
              index="04"
              title="Data display"
              description="Status, risk, progress and the signature SLA and compliance views."
            />
            <div className="grid gap-4 lg:grid-cols-2">
              <DemoCard
                title="Stats"
                description="A figure, its caption and a delta with an explicit direction."
              >
                <div className="grid gap-3 sm:grid-cols-3">
                  <Stat
                    figure="24"
                    caption="Applications in view"
                    delta="3 more than last week"
                    deltaTone="positive"
                  />
                  <Stat
                    figure="6.4 days"
                    caption="Median scrutiny time"
                    delta="No change from last week"
                    deltaTone="neutral"
                  />
                  <Stat
                    figure="2"
                    caption="Open SLA breaches"
                    delta="1 more than yesterday"
                    deltaTone="negative"
                  />
                </div>
              </DemoCard>

              <DemoCard
                title="Status and risk"
                description="Status pills use soft tints. Risk badges use the same status tokens with a 4px radius."
              >
                <div className="space-y-5">
                  <div>
                    <p className="mb-2 text-12 font-medium text-ink-500">
                      Status pills
                    </p>
                    <div className="flex flex-wrap gap-2">
                      <StatusPill status="compliant" />
                      <StatusPill status="watch" />
                      <StatusPill status="breach" />
                      <StatusPill status="info" />
                      <StatusPill status="neutral" />
                    </div>
                  </div>
                  <div>
                    <p className="mb-2 text-12 font-medium text-ink-500">
                      Risk badges
                    </p>
                    <div className="flex flex-wrap gap-2">
                      <RiskBadge level="low" />
                      <RiskBadge level="medium" />
                      <RiskBadge level="high" />
                    </div>
                  </div>
                </div>
              </DemoCard>

              <DemoCard
                title="Progress bars"
                description="Progress is labelled and exposes its value to assistive technology."
              >
                <div className="grid gap-4">
                  <ProgressBar label="Documents verified" value={68} status="ok" />
                  <ProgressBar label="Compliance score" value={72} status="watch" />
                  <ProgressBar
                    label="Inspection coverage"
                    value={46}
                    status="breach"
                  />
                </div>
              </DemoCard>

              <DemoCard
                title="SLA rings"
                description="The 40px ring fills as the SLA elapses and changes to watch or breach colours."
              >
                <div className="space-y-4">
                  {ringExamples.map((example) => (
                    <div
                      key={example.state}
                      className="flex items-center gap-3"
                    >
                      <SlaRing
                        value={example.value}
                        daysLeft={example.daysLeft}
                        state={example.state}
                      />
                      <span>
                        <span className="block text-13 font-medium text-ink">
                          {example.label}
                        </span>
                        <span className="block text-12 text-ink-500">
                          {example.detail}
                        </span>
                      </span>
                    </div>
                  ))}
                </div>
              </DemoCard>
            </div>

            <DemoCard
              title="Compliance gauge"
              description="A half-circle score from 0 to 100 with the RAG band marks visible behind the value arc."
              className="mt-4"
            >
              <div className="grid gap-6 sm:grid-cols-3">
                {gaugeExamples.map((example) => (
                  <div key={example.band}>
                    <ScoreGauge value={example.value} band={example.band} />
                    <p className="mt-1 text-center text-12 font-medium text-ink-700">
                      {example.label}
                    </p>
                  </div>
                ))}
              </div>
            </DemoCard>
          </section>

          <section id="navigation" aria-labelledby="navigation-heading">
            <SectionHeader
              id="navigation-heading"
              index="05"
              title="Navigation"
              description="Tabs, step progress and the stage track that carries the approval journey."
            />
            <div className="grid gap-4 lg:grid-cols-2">
              <DemoCard
                title="Tabs"
                description="Keyboard arrow keys move between tabs."
              >
                <Tabs defaultValue="summary">
                  <TabsList
                    aria-label="Application details"
                    className="w-full sm:w-auto"
                  >
                    <TabsTrigger
                      value="summary"
                      className="flex-1 sm:flex-none"
                    >
                      Application summary
                    </TabsTrigger>
                    <TabsTrigger
                      value="checks"
                      className="flex-1 sm:flex-none"
                    >
                      Compliance checks
                    </TabsTrigger>
                  </TabsList>
                  <TabsContent value="summary">
                    <p>
                      Sunrise Institute of Technology (demo) submitted a new
                      approval application for the 2026–27 cycle.
                    </p>
                  </TabsContent>
                  <TabsContent value="checks">
                    <p>
                      The land record and faculty list are verified. The
                      laboratory equipment list is still under review.
                    </p>
                  </TabsContent>
                </Tabs>
              </DemoCard>

              <DemoCard
                title="Stepper"
                description="A compact progress model for a single task or form."
              >
                <Stepper
                  current={1}
                  steps={[
                    {
                      id: "application",
                      label: "Application",
                      description: "Submitted",
                    },
                    {
                      id: "scrutiny",
                      label: "Scrutiny",
                      description: "In progress",
                    },
                    {
                      id: "inspection",
                      label: "Inspection",
                      description: "Committee visit",
                    },
                    {
                      id: "decision",
                      label: "Decision",
                      description: "Final order",
                    },
                  ]}
                />
              </DemoCard>
            </div>

            <DemoCard
              title="Stage track"
              description="Completed stages keep their timestamp. The current stage pulses. A deficiency blocks the track with a breach state."
              className="mt-4"
            >
              <div className="space-y-8">
                <div>
                  <p className="mb-4 text-13 font-medium text-ink-700">
                    In progress at scrutiny
                  </p>
                  <StageTrack
                    stages={applicationStages}
                    current="scrutiny"
                    events={inProgressEvents}
                  />
                </div>
                <div>
                  <p className="mb-4 text-13 font-medium text-ink-700">
                    Blocked by a deficiency
                  </p>
                  <StageTrack
                    stages={applicationStages}
                    current="scrutiny"
                    events={blockedEvents}
                    label="Application stages with a deficiency"
                  />
                </div>
              </div>
            </DemoCard>
          </section>

          <section id="feedback" aria-labelledby="feedback-heading">
            <SectionHeader
              id="feedback-heading"
              index="06"
              title="Feedback and overlays"
              description="Dialogs, drawers, toasts, loading states and the icon-less empty state."
            />
            <div className="grid gap-4 lg:grid-cols-2">
              <DemoCard
                title="Dialog"
                description="A modal for a focused decision. Focus stays inside until it closes."
              >
                <Dialog>
                  <DialogTrigger asChild>
                    <Button type="button" variant="secondary">
                      Review deficiency
                    </Button>
                  </DialogTrigger>
                  <DialogContent>
                    <DialogHeader>
                      <DialogTitle>Raise a deficiency</DialogTitle>
                      <DialogDescription>
                        Tell the institution which document is missing and what
                        to correct before scrutiny resumes.
                      </DialogDescription>
                    </DialogHeader>
                    <div className="mt-4 grid gap-4">
                      <Input
                        label="Missing document"
                        defaultValue="Signed land use certificate"
                      />
                      <Textarea
                        label="Correction required"
                        defaultValue="Upload the certificate with the authorised signatory and the current campus address."
                      />
                    </div>
                    <DialogFooter>
                      <DialogClose asChild>
                        <Button type="button" variant="quiet">
                          Cancel
                        </Button>
                      </DialogClose>
                      <DialogClose asChild>
                        <Button type="button" onClick={raiseDeficiencyToast}>
                          Raise deficiency
                        </Button>
                      </DialogClose>
                    </DialogFooter>
                  </DialogContent>
                </Dialog>
              </DemoCard>

              <DemoCard
                title="Drawer"
                description="A side panel for reviewing a report without losing the page behind it."
              >
                <Drawer>
                  <DrawerTrigger asChild>
                    <Button type="button" variant="secondary">
                      Open inspection report
                    </Button>
                  </DrawerTrigger>
                  <DrawerContent>
                    <DrawerHeader>
                      <DrawerTitle>Inspection report</DrawerTitle>
                      <DrawerDescription>
                        Sunrise Institute of Technology (demo) · Visit on 20
                        October 2026
                      </DrawerDescription>
                    </DrawerHeader>
                    <dl className="mt-6 grid gap-3 text-13">
                      <div className="flex items-start justify-between gap-4 border-b border-line pb-3">
                        <dt className="text-ink-500">Committee</dt>
                        <dd className="text-right font-medium text-ink">
                          Regional inspection committee
                        </dd>
                      </div>
                      <div className="flex items-start justify-between gap-4 border-b border-line pb-3">
                        <dt className="text-ink-500">Finding</dt>
                        <dd className="text-right font-medium text-ink">
                          Laboratory equipment list needs an update
                        </dd>
                      </div>
                      <div className="flex items-start justify-between gap-4">
                        <dt className="text-ink-500">Risk</dt>
                        <dd>
                          <RiskBadge level="medium" />
                        </dd>
                      </div>
                    </dl>
                    <DrawerFooter>
                      <DrawerClose asChild>
                        <Button type="button" variant="quiet">
                          Close
                        </Button>
                      </DrawerClose>
                      <DrawerClose asChild>
                        <Button type="button">Send to committee</Button>
                      </DrawerClose>
                    </DrawerFooter>
                  </DrawerContent>
                </Drawer>
              </DemoCard>

              <DemoCard
                title="Toasts"
                description="The success toast reuses the action verb. Errors name the fix."
              >
                <div className="flex flex-wrap gap-3">
                  <Button type="button" onClick={raiseDeficiencyToast}>
                    Raise deficiency
                  </Button>
                  <Button
                    type="button"
                    variant="secondary"
                    onClick={() =>
                      toast({
                        title: "Inspection scheduled",
                        description:
                          "The committee will receive the visit details.",
                        variant: "info",
                      })
                    }
                  >
                    Schedule inspection
                  </Button>
                  <Button
                    type="button"
                    variant="quiet"
                    onClick={() =>
                      toast({
                        title: "Reminder not sent",
                        description:
                          "Add a contact email for the institution, then try again.",
                        variant: "error",
                      })
                    }
                  >
                    Send reminder
                  </Button>
                </div>
              </DemoCard>

              <DemoCard
                title="Skeleton"
                description="Loading placeholders preserve the final layout without announcing decorative shapes."
              >
                <div
                  role="status"
                  aria-label="Loading application summary"
                  className="max-w-md space-y-3"
                >
                  <Skeleton className="h-4 w-28" />
                  <Skeleton className="h-8 w-3/4" />
                  <Skeleton className="h-4 w-full" />
                  <Skeleton className="h-4 w-5/6" />
                  <Skeleton className="h-20 w-full rounded-panel" />
                </div>
              </DemoCard>
            </div>

            <DemoCard
              title="Empty state"
              description="No icon, one line of explanation and one action."
              className="mt-4"
            >
              <EmptyState
                message="No inspections are scheduled this week."
                action={
                  <Button
                    type="button"
                    variant="secondary"
                    onClick={() =>
                      toast({
                        title: "Inspection scheduling opened",
                        description:
                          "Choose an institution to schedule an inspection.",
                        variant: "info",
                      })
                    }
                  >
                    Schedule inspection
                  </Button>
                }
              />
            </DemoCard>
          </section>

          <section id="table" aria-labelledby="table-heading">
            <SectionHeader
              id="table-heading"
              index="07"
              title="Application table"
              description="A sortable, sticky-headed table with comfortable and dense modes. All institutions are fictional demo data."
            />
            <DemoCard
              title="Approval applications"
              description="Sort a column, switch density, and scroll the body while the header stays in place."
            >
              <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
                <p className="text-13 text-ink-700">
                  Sorted by{" "}
                  <span className="font-medium text-ink">
                    {sort.key === "daysLeft"
                      ? "days left"
                      : sort.key === "submitted"
                        ? "submitted date"
                        : "institution"}
                  </span>
                  , {sort.direction === "asc" ? "ascending" : "descending"}.
                </p>
                <div
                  role="group"
                  aria-label="Table density"
                  className="flex items-center gap-2"
                >
                  <Button
                    type="button"
                    size="sm"
                    variant={
                      density === "comfortable" ? "secondary" : "quiet"
                    }
                    aria-pressed={density === "comfortable"}
                    onClick={() => setDensity("comfortable")}
                  >
                    Comfortable
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    variant={density === "dense" ? "secondary" : "quiet"}
                    aria-pressed={density === "dense"}
                    onClick={() => setDensity("dense")}
                  >
                    Dense
                  </Button>
                </div>
              </div>
              <Table density={density} containerClassName="max-h-64">
                <TableCaption className="sr-only">
                  Illustrative applications for fictional institutions.
                </TableCaption>
                <TableHeader>
                  <TableRow>
                    <TableHead
                      sortDirection={sortDirectionFor("institution")}
                      onSort={() => handleSort("institution")}
                    >
                      Institution
                    </TableHead>
                    <TableHead>Application</TableHead>
                    <TableHead
                      sortDirection={sortDirectionFor("submitted")}
                      onSort={() => handleSort("submitted")}
                    >
                      Submitted
                    </TableHead>
                    <TableHead
                      sortDirection={sortDirectionFor("daysLeft")}
                      onSort={() => handleSort("daysLeft")}
                    >
                      Days left
                    </TableHead>
                    <TableHead>Status</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {sortedApplications.map((application) => (
                    <TableRow key={application.id}>
                      <TableCell className="font-medium">
                        {application.institution}
                      </TableCell>
                      <TableCell className="text-ink-700">
                        {application.type}
                      </TableCell>
                      <TableCell className="text-ink-700">
                        {application.submitted}
                      </TableCell>
                      <TableCell>{application.daysLeft}</TableCell>
                      <TableCell>
                        <StatusPill status={application.status} />
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </DemoCard>
          </section>
        </div>
      </main>

      <footer className="mt-14 border-t border-line bg-surface">
        <div className="mx-auto max-w-6xl px-4 py-6 text-13 text-ink-500 sm:px-6 lg:px-8">
          <p>
            Design system preview. Copy rules are documented in{" "}
            <code className="rounded-input bg-ink-100 px-1.5 py-0.5 text-12 text-ink-700">
              docs/UI_COPY_GUIDE.md
            </code>
            .
          </p>
        </div>
      </footer>
    </div>
  );
}
