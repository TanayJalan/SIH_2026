import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, ChevronDown, MoreHorizontal, Pencil, ScrollText } from "lucide-react";
import { Link } from "react-router-dom";

import ApplicationStatusBadge from "../ApplicationStatusBadge";
import EscalationBadge from "../EscalationBadge";
import { Button, RiskBadge, SlaRing, Tooltip, type RiskLevel, type SlaState } from "../ui";
import { useWorkflowActions } from "../workflow/WorkflowDialogHost";
import {
  ApiError,
  getAllowedActions,
  type ApplicationDetail,
  type AllowedAction,
  type WorkflowDefinition,
} from "@/lib/api";
import { humanizeEnum } from "@/lib/format";
import { calendarDaysUntil, useSimulatedNow } from "@/lib/useSimulatedNow";

interface SlaSummary {
  value: number;
  daysLeft: number;
  state: SlaState;
}

function slaSummary(application: ApplicationDetail, now: Date): SlaSummary | null {
  const { sla_due_at, submitted_at } = application;
  if (!sla_due_at || !submitted_at || application.current_stage === "COMPLETED") {
    return null;
  }
  const due = new Date(sla_due_at).getTime();
  if (Number.isNaN(due) || submitted_at === null) {
    return null;
  }
  const startedAt = new Date(submitted_at).getTime();
  const daysLeft = calendarDaysUntil(now, sla_due_at) ?? 0;
  const state: SlaState =
    daysLeft < 0 ? "breach" : daysLeft <= 3 ? "watch" : "ok";
  const window = due - startedAt;
  const value =
    Number.isFinite(window) && window > 0
      ? ((now.getTime() - startedAt) / window) * 100
      : 100;
  return { value, daysLeft, state };
}

const SLA_LABEL =
  "Share of the stage SLA that has elapsed, with the days remaining before it is due";

export interface RiskSummary {
  level: RiskLevel;
  reasons: string[];
}

export default function CaseFileHeader({
  application,
  token,
  userRole,
  risk,
  definition,
}: {
  application: ApplicationDetail;
  token: string;
  userRole: string;
  risk: RiskSummary;
  definition?: WorkflowDefinition;
}) {
  const { openAction } = useWorkflowActions();
  const allowedQuery = useQuery({
    queryKey: ["allowed-actions", application.id],
    queryFn: () => getAllowedActions(token, application.id),
    enabled: Boolean(token && application.id),
    retry: false,
  });

  const actions = allowedQuery.data?.actions ?? [];
  const normalActions = actions.filter((action) => action.tone !== "danger");
  const dangerActions = actions.filter((action) => action.tone === "danger");
  const canEditDraft =
    userRole === "INSTITUTION_ADMIN" && application.status === "DRAFT";
  const now = useSimulatedNow();
  const sla = slaSummary(application, now);

  return (
    <section className="rounded-panel border border-line bg-surface p-5 sm:p-6">
      <div className="flex min-w-0 flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="text-12 font-medium text-ink-500">
            {application.reference ?? "Application"} ·{" "}
            {humanizeEnum(application.application_type)} ·{" "}
            {humanizeEnum(application.category)} ·{" "}
            {application.academic_year}
          </p>
          <h1 className="mt-1 font-serif text-24 font-semibold leading-tight text-ink">
            {application.institution.name}
          </h1>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <ApplicationStatusBadge
              status={application.status}
              isWithdrawn={application.is_withdrawn}
            />
            {definition ? (
              <Tooltip
                content={definition.label}
              >
                <span
                  tabIndex={0}
                  className="rounded-pill bg-neutral-soft px-2 py-0.5 text-11 font-medium text-ink-700"
                >
                  {definition.track.replace("TRACK_", "Track ")}
                </span>
              </Tooltip>
            ) : null}
            {application.decision_type ? (
              <Tooltip
                content={
                  application.decision_uploaded_at
                    ? `Decision recorded on ${new Date(application.decision_uploaded_at).toLocaleDateString("en-IN")}`
                    : "A final decision has been recorded on this file."
                }
              >
                <span
                  tabIndex={0}
                  className="inline-flex items-center gap-1.5 rounded-pill border border-line bg-paper px-2 py-0.5 text-11 font-medium text-ink-700"
                >
                  <ScrollText aria-hidden="true" className="size-3" />
                  Decision: {application.decision_type}
                </span>
              </Tooltip>
            ) : null}
            {application.portal_application_no ? (
              <span className="text-12 text-ink-500">
                Portal no. <span className="font-medium text-ink-700">{application.portal_application_no}</span>
              </span>
            ) : null}
            {application.is_escalated ? (
              <EscalationBadge />
            ) : null}
            <Tooltip
              content={
                risk.reasons.length === 0
                  ? "No configured compliance rule is currently failing."
                  : risk.reasons.slice(0, 3).join(" · ")
              }
            >
              <span tabIndex={0} className="inline-flex">
                <RiskBadge level={risk.level} />
              </span>
            </Tooltip>
            {application.assigned_officer ? (
              <span className="text-12 text-ink-500">
                Officer {application.assigned_officer.name}
              </span>
            ) : (
              <span className="text-12 text-ink-500">No officer assigned</span>
            )}
          </div>
        </div>

        <div className="flex shrink-0 items-center gap-4">
          {sla ? (
            <span className="flex flex-col items-center gap-1">
              <SlaRing
                value={sla.value}
                daysLeft={sla.daysLeft}
                state={sla.state}
                label={SLA_LABEL}
              />
              <span
                className={
                  sla.daysLeft < 0
                    ? "text-12 font-medium text-breach-strong"
                    : "text-12 text-ink-500"
                }
              >
                {sla.daysLeft < 0
                  ? `${-sla.daysLeft} day${sla.daysLeft === -1 ? "" : "s"} over SLA`
                  : `${sla.daysLeft} day${sla.daysLeft === 1 ? "" : "s"} left`}
              </span>
            </span>
          ) : null}

          <div className="flex flex-wrap justify-end items-center gap-2">
            {canEditDraft ? (
              <Button asChild variant="secondary" size="sm">
                <Link to={`/applications/${application.id}/edit`}>
                  <Pencil aria-hidden="true" className="size-4" />
                  Continue draft
                </Link>
              </Button>
            ) : null}
            {allowedQuery.isPending ? (
              <span className="text-12 text-ink-500">Loading actions…</span>
            ) : allowedQuery.isError ? (
              <Tooltip
                content={
                  allowedQuery.error instanceof ApiError
                    ? allowedQuery.error.message
                    : "Available actions could not be loaded."
                }
              >
                <span
                  tabIndex={0}
                  className="rounded-input border border-breach bg-breach-soft px-2 py-1 text-12 text-breach-strong"
                >
                  Actions unavailable
                </span>
              </Tooltip>
            ) : (
              <>
                {normalActions.map((action) => (
                  <Button
                    key={action.action}
                    variant={action.tone === "primary" ? "primary" : "secondary"}
                    size="sm"
                    onClick={() => openAction(action)}
                  >
                    {action.label}
                  </Button>
                ))}
                {dangerActions.length > 0 ? (
                  <OverflowMenu actions={dangerActions} />
                ) : null}
              </>
            )}
            <Button asChild variant="quiet" size="sm">
              <Link to="/applications">
                <ArrowLeft aria-hidden="true" className="size-4" />
                Back
              </Link>
            </Button>
          </div>
        </div>
      </div>
    </section>
  );
}

function OverflowMenu({ actions }: { actions: AllowedAction[] }) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const { openAction } = useWorkflowActions();

  useEffect(() => {
    if (!open) {
      return;
    }
    const onPointerDown = (event: PointerEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
      }
    };
    window.addEventListener("pointerdown", onPointerDown);
    window.addEventListener("keydown", onKeyDown);
    return () => {
      window.removeEventListener("pointerdown", onPointerDown);
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  return (
    <div ref={containerRef} className="relative">
      <Button
        variant="quiet"
        size="sm"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((current) => !current)}
      >
        <MoreHorizontal aria-hidden="true" className="size-4" />
        More
        <ChevronDown aria-hidden="true" className="size-3" />
      </Button>
      {open ? (
        <div
          role="menu"
          className="absolute right-0 z-20 mt-1 w-64 rounded-input border border-line bg-surface p-1 shadow-popover"
        >
          {actions.map((action) => (
            <button
              key={action.action}
              type="button"
              role="menuitem"
              className="flex w-full flex-col gap-0.5 rounded-input px-3 py-2 text-left hover:bg-paper"
              onClick={() => {
                setOpen(false);
                openAction(action);
              }}
            >
              <span className="text-13 font-medium text-breach-strong">
                {action.label}
              </span>
              <span className="text-12 leading-4 text-ink-500">
                {action.description}
              </span>
            </button>
          ))}
        </div>
      ) : null}
    </div>
  );
}
