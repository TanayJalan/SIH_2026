import {
  AlertTriangle,
  CalendarClock,
  Check,
  Gavel,
  Landmark,
  ShieldCheck,
} from "lucide-react";

import {
  AppealDeadline,
  DepositDeadline,
  LoaValidity,
} from "@/lib/api";
import { cn } from "@/lib/utils";
import { formatDate } from "@/lib/format";

export interface StageTrackStage {
  id: string;
  label: string;
}

export interface StageTrackEvent {
  stage: string;
  at?: string;
  blocked?: boolean;
}

export interface StageTrackProps {
  stages: StageTrackStage[];
  current: string;
  events?: StageTrackEvent[];
  label?: string;
  className?: string;
  /** The seven-day appeal clock, shown on the stage track when the current
   *  state is APPEAL_WINDOW (APH 1.11a). */
  appeal?: AppealDeadline | null;
  /** The Security Deposit clock (15-day grace, 31 May / 31 July penalty
   *  windows), shown when the current state is SECURITY_DEPOSIT_PENDING
   *  (APH 2.25f). */
  deposit?: DepositDeadline | null;
  /** LoA validity end (two academic years), shown once an LoA has been issued
   *  (APH 1.10b). */
  loaValidity?: LoaValidity | null;
}

type StageState = "completed" | "current" | "blocked" | "future";

const APPEAL_STATE = "APPEAL_WINDOW";
const DEPOSIT_STATE = "SECURITY_DEPOSIT_PENDING";
const LOA_STATES = new Set(["LOA_ISSUED", "ACTIVE_LOA"]);

function daysLabel(days: number | null): string {
  if (days === null) {
    return "No clock running";
  }
  if (days < 0) {
    return `${-days} day${-days === 1 ? "" : "s"} past`;
  }
  if (days === 0) {
    return "Due today";
  }
  return `${days} day${days === 1 ? "" : "s"} left`;
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

function AppealClock({
  appeal,
}: {
  appeal: AppealDeadline;
}) {
  const days = appeal.days_left ?? null;
  return (
    <div
      className="flex items-center gap-3 rounded-input border border-watch bg-watch-soft p-3"
    >
      <Gavel aria-hidden="true" className="size-4 text-watch-strong" />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1.5">
          <h3 className="text-12 font-semibold text-watch-strong">
            Appeal window open
          </h3>
          <span className="rounded-pill border border-watch bg-watch/20 px-2 py-0.5 text-10 font-medium text-watch-strong">
            7 days
          </span>
        </div>
        <p className="mt-1 text-11 leading-5 text-watch-strong">
          {days === null
            ? "The clock has not started yet."
            : days < 0
              ? `Window closed ${daysLabel(days)} — the decision becomes final with no appeal.`
              : `Closes ${formatDate(appeal.deadline ?? "")} · ${daysLabel(days)}.`}
        </p>
        <div className="mt-1.5 flex flex-wrap gap-1.5">
          <Clause text={appeal.apH_clause} />
        </div>
      </div>
    </div>
  );
}

function DepositClock({
  deposit,
}: {
  deposit: DepositDeadline;
}) {
  const paid = deposit.current_stage === "paid";
  const days = deposit.days_left ?? null;
  return (
    <div
      className={cn(
        "flex items-center gap-3 rounded-input border p-3",
        paid ? "border-ok bg-ok-soft/50" : "border-watch bg-watch-soft/50",
      )}
    >
      <Landmark aria-hidden="true" className="size-4 text-ink-500" />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1.5">
          <h3 className="text-12 font-semibold text-ink">
            Security Deposit clock
          </h3>
          <span
            className={cn(
              "rounded-pill px-2 py-0.5 text-10 font-medium",
              paid
                ? "bg-ok-soft text-ok-strong"
                : "bg-breach-soft text-breach-strong",
            )}
          >
            {paid ? "Paid" : daysLabel(days)}
          </span>
        </div>
        <p className="mt-1 text-11 leading-5 text-ink-700">
          {paid
            ? "Security Deposit paid — the LoA is active."
            : `Intimated ${formatDate(deposit.intimated_on ?? "")}. Grace is 15 days (APH 2.25f); the 10% penalty window runs to ${formatDate(deposit.first_penalty_until ?? "")} and the 20% window to ${formatDate(deposit.second_penalty_until ?? "")}, after which the case is withdrawn.`}
        </p>
        <dl className="mt-1.5 grid grid-cols-2 gap-x-2 gap-y-1 text-10 text-ink-500">
          <div>
            <dt className="font-medium text-ink-700">10% until</dt>
            <dd className="tabular-nums">
              {formatDate(deposit.first_penalty_until ?? "")}
            </dd>
          </div>
          <div>
            <dt className="font-medium text-ink-700">20% until</dt>
            <dd className="tabular-nums">
              {formatDate(deposit.second_penalty_until ?? "")}
            </dd>
          </div>
        </dl>
        <div className="mt-1.5 flex flex-wrap gap-1.5">
          <Clause text={deposit.apH_clause} />
        </div>
      </div>
    </div>
  );
}

function LoaValidityClock({ loaValidity }: { loaValidity: LoaValidity }) {
  return (
    <div
      className="flex items-center gap-3 rounded-input border border-line bg-paper p-3"
    >
      <ShieldCheck aria-hidden="true" className="size-4 text-ink-500" />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-1.5">
          <h3 className="text-12 font-semibold text-ink">LoA validity</h3>
          <span
            className={cn(
              "rounded-pill px-2 py-0.5 text-10 font-medium",
              loaValidity.expired
                ? "bg-breach-soft text-breach-strong"
                : "bg-ok-soft text-ok-strong",
            )}
          >
            {loaValidity.expired ? "Expired" : `${loaValidity.days_left} day${loaValidity.days_left === 1 ? "" : "s"} left`}
          </span>
        </div>
        <p className="mt-1 text-11 leading-5 text-ink-700">
          Valid until {formatDate(loaValidity.valid_until)} — two academic years
          (APH 1.10b).
        </p>
        <div className="mt-1.5 flex flex-wrap gap-1.5">
          <Clause text={loaValidity.apH_clause} />
        </div>
      </div>
    </div>
  );
}

export function StageTrack({
  stages,
  current,
  events = [],
  label = "Application stages",
  className,
  appeal = null,
  deposit = null,
  loaValidity = null,
}: StageTrackProps) {
  const eventByStage = new Map(events.map((event) => [event.stage, event]));

  const showAppeal = current === APPEAL_STATE && appeal?.deadline != null;
  const showDeposit = current === DEPOSIT_STATE && deposit != null;
  const showLoaValidity = LOA_STATES.has(current) && loaValidity != null;

  return (
    <div className={cn("flex flex-col gap-4", className)}>
      <ol
        aria-label={label}
        className="flex flex-col md:flex-row md:items-start"
      >
        {stages.map((stage, index) => {
          const event = eventByStage.get(stage.id);
          const state: StageState = event?.blocked
            ? "blocked"
            : stage.id === current
              ? "current"
              : event?.at
                ? "completed"
                : "future";
          const meta =
            state === "completed"
              ? (event?.at ?? "Completed")
              : state === "blocked"
                ? event?.at
                  ? `Deficiency raised · ${event.at}`
                  : "Deficiency raised"
                : state === "current"
                  ? (event?.at ?? "In progress")
                  : null;

          return (
            <li
              key={stage.id}
              aria-current={stage.id === current ? "step" : undefined}
              className="relative flex flex-1 gap-3 pb-6 last:pb-0 md:flex-col md:items-center md:gap-0 md:pb-0 md:text-center"
            >
              {index < stages.length - 1 ? (
                <span
                  aria-hidden="true"
                  className={cn(
                    "absolute left-4 top-8 h-[calc(100%-1rem)] w-px transition-colors duration-300 md:left-1/2 md:top-4 md:h-px md:w-full",
                    state === "completed" ? "bg-ink-300" : "bg-line",
                  )}
                />
              ) : null}
              <span className="relative z-10 flex size-8 shrink-0 items-center justify-center">
                {state === "current" ? (
                  <span
                    aria-hidden="true"
                    className="absolute -inset-1 rounded-input border border-info motion-safe:animate-pulse"
                  />
                ) : null}
                <span
                  className={cn(
                    "flex size-8 items-center justify-center rounded-input border text-13 font-semibold transition-colors duration-300",
                    state === "completed" && "border-ink bg-ink text-surface",
                    state === "current" &&
                      "border-info bg-info-soft text-info-strong",
                    state === "blocked" &&
                      "border-breach bg-breach-soft text-breach-strong",
                    state === "future" &&
                      "border-line bg-surface text-ink-500",
                  )}
                >
                  {state === "completed" ? (
                    <>
                      <Check aria-hidden="true" className="size-4" />
                      <span className="sr-only">Completed</span>
                    </>
                  ) : state === "blocked" ? (
                    <>
                      <AlertTriangle aria-hidden="true" className="size-4" />
                      <span className="sr-only">Blocked</span>
                    </>
                  ) : (
                    index + 1
                  )}
                </span>
              </span>
              <span className="pt-0.5 md:pt-3">
                <span
                  className={cn(
                    "block text-13 font-medium transition-colors duration-300",
                    state === "future" && "text-ink-500",
                    state === "blocked" && "text-breach-strong",
                    (state === "completed" || state === "current") && "text-ink",
                  )}
                >
                  {stage.label}
                </span>
                {meta ? (
                  <span
                    className={cn(
                      "mt-0.5 block text-12 transition-colors duration-300",
                      state === "blocked"
                        ? "text-breach-strong"
                        : state === "current"
                          ? "text-info-strong"
                          : "text-ink-500",
                    )}
                  >
                    {meta}
                  </span>
                ) : null}
              </span>
            </li>
          );
        })}
      </ol>

      <section
        aria-label="Statutory clocks"
        className="flex flex-col gap-3"
        hidden={!showAppeal && !showDeposit && !showLoaValidity}
      >
        <div className="flex items-center gap-2">
          <CalendarClock aria-hidden="true" className="size-4 text-ink-500" />
          <h3 className="text-13 font-semibold text-ink">Statutory clocks</h3>
        </div>
        {showAppeal && appeal ? <AppealClock appeal={appeal} /> : null}
        {showDeposit && deposit ? <DepositClock deposit={deposit} /> : null}
        {showLoaValidity && loaValidity ? (
          <LoaValidityClock loaValidity={loaValidity} />
        ) : null}
      </section>
    </div>
  );
}
