import { CalendarClock, Gavel, Landmark, ShieldCheck } from "lucide-react";

import {
  Skeleton,
  StatusPill,
  type StatusPillTone,
} from "@/components/ui";
import type {
  ApplicationDeadlines,
  DepositDeadline,
} from "@/lib/api";
import { formatDate, formatDateTime } from "@/lib/format";
import { cn } from "@/lib/utils";

/**
 * Deadlines are configuration (deadline_rules + academic_calendar_events), so
 * every date shown here arrives from `GET /applications/{id}/deadlines`.
 * The card renders what the server read back; it invents no AICTE date itself.
 */

const DEPOSIT_STEPS: { key: string; label: string; percent: string }[] = [
  { key: "grace", label: "Within 15 days of intimation", percent: "No penalty" },
  { key: "penalty_10", label: "Up to the first penalty date", percent: "10% penalty" },
  { key: "penalty_20", label: "Up to the final deposit date", percent: "20% penalty" },
  { key: "withdrawal", label: "After the final deposit date", percent: "Withdrawal" },
];

function daysLabel(days: number | null): string {
  if (days === null) {
    return "No clock running";
  }
  if (days < 0) {
    return `${-days} day${days === -1 ? "" : "s"} past`;
  }
  if (days === 0) {
    return "Due today";
  }
  return `${days} day${days === 1 ? "" : "s"} left`;
}

function daysTone(days: number | null): StatusPillTone {
  if (days === null) {
    return "neutral";
  }
  if (days < 0) {
    return "breach";
  }
  return days <= 3 ? "watch" : "compliant";
}

function Clause({ text }: { text: string | null }) {
  if (!text) {
    return null;
  }
  return (
    <span className="rounded-pill bg-neutral-soft px-2 py-0.5 text-11 font-medium text-ink-700">
      {text}
    </span>
  );
}

function AppealCard({ deadlines }: { deadlines: ApplicationDeadlines }) {
  const appeal = deadlines.appeal;
  if (!appeal) {
    return null;
  }
  const open = appeal.deadline !== null;
  return (
    <div className="flex h-full flex-col rounded-input border border-line bg-paper p-4">
      <div className="flex items-center gap-2">
        <Gavel aria-hidden="true" className="size-4 text-ink-500" />
        <h3 className="text-13 font-semibold text-ink">Appeal window</h3>
        <StatusPill status={open ? daysTone(appeal.days_left) : "neutral"}>
          {open ? daysLabel(appeal.days_left) : "Not started"}
        </StatusPill>
      </div>
      <p className="mt-2 text-12 leading-5 text-ink-700">
        {appeal.deadline
          ? `Closes on ${formatDateTime(appeal.deadline)}. The decision becomes final when it passes with no appeal.`
          : "The window opens when a final decision letter is issued."}
      </p>
      {appeal.letter_type ? (
        <p className="mt-2 text-12 text-ink-500">
          Decision on the clock: {appeal.letter_type.replace("_", " ")}
        </p>
      ) : null}
      <div className="mt-auto flex flex-wrap gap-1.5 pt-2">
        <Clause text={appeal.apH_clause} />
      </div>
    </div>
  );
}

function DepositCard({ deposit }: { deposit: DepositDeadline | null }) {
  if (!deposit) {
    return null;
  }
  const paid = deposit.current_stage === "paid";
  const stage = deposit.current_stage ?? null;
  const stageIndex = stage
    ? DEPOSIT_STEPS.findIndex((step) => step.key === stage)
    : -1;
  return (
    <div
      className={cn(
        "flex h-full flex-col rounded-input border p-4",
        paid ? "border-ok bg-ok-soft/40" : "border-line bg-paper",
      )}
    >
      <div className="flex flex-wrap items-center gap-2">
        <Landmark aria-hidden="true" className="size-4 text-ink-500" />
        <h3 className="text-13 font-semibold text-ink">Security Deposit</h3>
        <StatusPill status={paid ? "compliant" : daysTone(deposit.days_left)}>
          {paid ? "Paid" : daysLabel(deposit.days_left)}
        </StatusPill>
      </div>
      <p className="mt-2 text-12 leading-5 text-ink-700">
        {deposit.due_on
          ? `Due on ${formatDate(deposit.due_on)}${deposit.intimated_on ? `, intimated ${formatDate(deposit.intimated_on)}` : ""}.`
          : "The clock starts when the approval is intimated."}
      </p>
      <ol className="mt-3 space-y-1.5" aria-label="Security Deposit penalty ladder">
        {DEPOSIT_STEPS.map((step, index) => {
          const active = stageIndex === index;
          const passed = paid || stageIndex > index;
          return (
            <li
              key={step.key}
              className="flex items-center gap-2 text-12"
              aria-current={active ? "step" : undefined}
            >
              <span
                aria-hidden="true"
                className={cn(
                  "size-2 shrink-0 rounded-full",
                  active ? "bg-info ring-2 ring-info-soft" : passed ? "bg-ok" : "bg-line",
                )}
              />
              <span
                className={cn(
                  "min-w-0 flex-1 truncate",
                  active ? "font-semibold text-ink" : passed ? "text-ok-strong" : "text-ink-500",
                )}
              >
                {step.label}
              </span>
              <span className="shrink-0 text-ink-500">{step.percent}</span>
            </li>
          );
        })}
      </ol>
      <dl className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-12 text-ink-500">
        {deposit.first_penalty_until ? (
          <div className="flex gap-1">
            <dt className="font-medium text-ink-700">10% until</dt>
            <dd className="tabular-nums">{formatDate(deposit.first_penalty_until)}</dd>
          </div>
        ) : null}
        {deposit.second_penalty_until ? (
          <div className="flex gap-1">
            <dt className="font-medium text-ink-700">20% until</dt>
            <dd className="tabular-nums">{formatDate(deposit.second_penalty_until)}</dd>
          </div>
        ) : null}
      </dl>
      <div className="mt-auto flex flex-wrap gap-1.5 pt-2">
        <Clause text={deposit.apH_clause} />
      </div>
    </div>
  );
}

export default function CaseDeadlinesStrip({
  deadlines,
  pending,
}: {
  deadlines: ApplicationDeadlines | undefined;
  pending?: boolean;
}) {
  if (pending || !deadlines) {
    return (
      <section className="rounded-panel border border-line bg-surface p-5 sm:p-6" role="status">
        <div className="space-y-2" aria-hidden="true">
          <Skeleton className="h-4 w-40" />
          <Skeleton className="h-4 w-64" />
        </div>
        <span className="sr-only">Loading statutory deadlines</span>
      </section>
    );
  }

  const hasAny =
    (deadlines.appeal?.deadline != null) ||
    deadlines.security_deposit !== null ||
    deadlines.loa_validity !== null;
  if (!hasAny) {
    return null;
  }

  return (
    <section
      className="rounded-panel border border-line bg-surface p-5 sm:p-6"
      aria-label="Statutory deadlines"
    >
      <div className="flex flex-wrap items-center gap-2">
        <CalendarClock aria-hidden="true" className="size-4 text-ink-500" />
        <h2 className="text-14 font-semibold text-ink">Statutory deadlines</h2>
        <p className="text-12 text-ink-500">
          Dates come from the configured deadline rules and academic calendar — illustrative demo
          values, verify against the current AICTE handbook.
        </p>
      </div>
      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-3">
        <AppealCard deadlines={deadlines} />
        <DepositCard deposit={deadlines.security_deposit} />
        {deadlines.loa_validity ? (
          <div className="flex h-full flex-col rounded-input border border-line bg-paper p-4">
            <div className="flex items-center gap-2">
              <ShieldCheck aria-hidden="true" className="size-4 text-ink-500" />
              <h3 className="text-13 font-semibold text-ink">LoA validity</h3>
              <StatusPill
                status={
                  deadlines.loa_validity.expired ? "breach" : daysTone(deadlines.loa_validity.days_left)
                }
              >
                {deadlines.loa_validity.expired
                  ? "Expired"
                  : `${deadlines.loa_validity.days_left} day${deadlines.loa_validity.days_left === 1 ? "" : "s"} left`}
              </StatusPill>
            </div>
            <p className="mt-2 text-12 leading-5 text-ink-700">
              Valid until {formatDate(deadlines.loa_validity.valid_until)} — two academic years
              (APH 1.10b).
            </p>
            <div className="mt-auto flex flex-wrap gap-1.5 pt-2">
              <Clause text={deadlines.loa_validity.apH_clause} />
            </div>
          </div>
        ) : null}
      </div>
    </section>
  );
}
