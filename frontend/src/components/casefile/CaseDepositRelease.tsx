import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { Button, Input, Skeleton, StatusPill, useToast } from "@/components/ui";
import { useAuth } from "@/auth/AuthContext";
import {
  ApiError,
  approveDepositRelease,
  listSecurityDeposits,
  recordDepositClearance,
  requestDepositRelease,
  withdrawSecurityDeposit,
  type ApplicationDetail,
  type SecurityDepositRecord,
} from "@/lib/api";
import { formatDate, formatInr, humanizeEnum } from "@/lib/format";
import { calendarDaysUntil, useSimulatedNow } from "@/lib/useSimulatedNow";

function Clause({ text }: { text: string | null | undefined }) {
  if (!text) {
    return null;
  }
  return (
    <span className="rounded-pill bg-neutral-soft px-2 py-0.5 text-11 font-medium text-ink-700">
      {text}
    </span>
  );
}

const RELEASABLE = new Set(["PAID", "PENALTY_10", "PENALTY_20"]);

/** Proof and Affidavit 3 are due 15 days after intimation (APH 2.25f). */
const GRACE_DAYS = 15;
const SETTLED = new Set(["PAID", "PENALTY_10", "PENALTY_20", "RELEASED"]);

function proofDueDate(createdOn: string): string {
  const date = new Date(createdOn);
  date.setUTCDate(date.getUTCDate() + GRACE_DAYS);
  return date.toISOString().slice(0, 10);
}

export default function CaseDepositRelease({
  application,
  token,
}: {
  application: ApplicationDetail;
  token: string;
}) {
  const { user } = useAuth();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const role = user?.role ?? "";

  const query = useQuery({
    queryKey: ["security-deposits", application.id],
    queryFn: () => listSecurityDeposits(token, application.id),
    retry: false,
  });

  const canRequest = role === "INSTITUTION_ADMIN";
  const canClear = ["REGULATION_BUREAU_OFFICER", "COMPLAINT_SCRUTINY_MEMBER", "SUPER_ADMIN"].includes(role);
  const canApprove = ["REGIONAL_OFFICER", "SUPER_ADMIN"].includes(role);

  const refresh = async () => {
    await queryClient.invalidateQueries({ queryKey: ["security-deposits", application.id] });
  };

  if (query.isPending) {
    return <Skeleton className="h-24 w-full" />;
  }
  if (query.isError || (query.data ?? []).length === 0) {
    return null;
  }

  return (
    <section className="rounded-panel border border-line bg-surface p-5 sm:p-6">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-14 font-semibold text-ink">Security Deposit release</h2>
        <Clause text="APH 6.46" />
      </div>
      <p className="mt-1 text-13 text-ink-500">
        Release needs clearances from PGRC, the Vigilance Cell and the grants cell; the NOC or
        sanction order follows (APH 6.46b-d).
      </p>
      <ul className="mt-4 space-y-3">
        {(query.data ?? []).map((deposit) => (
          <DepositRow
            key={deposit.id}
            deposit={deposit}
            applicationId={application.id}
            token={token}
            canRequest={canRequest}
            canClear={canClear}
            canApprove={canApprove}
            onChanged={refresh}
            onToast={toast}
          />
        ))}
      </ul>
    </section>
  );
}

function DepositRow({
  deposit,
  applicationId,
  token,
  canRequest,
  canClear,
  canApprove,
  onChanged,
  onToast,
}: {
  deposit: SecurityDepositRecord;
  applicationId: string;
  token: string;
  canRequest: boolean;
  canClear: boolean;
  canApprove: boolean;
  onChanged: () => Promise<void>;
  onToast: ReturnType<typeof useToast>["toast"];
}) {
  const [busy, setBusy] = useState(false);
  const [nocNumber, setNocNumber] = useState("");
  const [error, setError] = useState<string | null>(null);
  const now = useSimulatedNow();
  const clearances = deposit.release_clearances ?? [];
  const due = proofDueDate(deposit.created_on);
  const daysLeft = calendarDaysUntil(now, due);

  const run = async (fn: () => Promise<unknown>, title: string) => {
    setBusy(true);
    setError(null);
    try {
      await fn();
      await onChanged();
      onToast({ title, variant: "success" });
    } catch (mutationError) {
      setError(
        mutationError instanceof ApiError
          ? mutationError.message
          : "The Security Deposit step could not be recorded.",
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <li className="rounded-input border border-line bg-paper p-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-13 font-medium text-ink">
          {humanizeEnum(deposit.programme_family)} · {deposit.level}
        </span>
        <StatusPill
          status={
            deposit.status === "RELEASED"
              ? "compliant"
              : deposit.status.startsWith("PENALTY")
                ? "watch"
                : deposit.status === "WITHDRAWN" || deposit.status === "FORFEITED"
                  ? "breach"
                  : "info"
          }
        >
          {humanizeEnum(deposit.status)}
        </StatusPill>
        <Clause text={deposit.apH_clause} />
        {deposit.doubled_for_leased ? (
          <span className="text-12 text-watch-strong">Doubled (leased)</span>
        ) : null}
      </div>

      <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-12 sm:grid-cols-4">
        <div>
          <dt className="text-ink-500">Required</dt>
          <dd className="tabular-nums font-medium text-ink">{formatInr(deposit.required_paise)}</dd>
        </div>
        <div>
          <dt className="text-ink-500">Intimated</dt>
          <dd className="text-ink-700">{formatDate(deposit.created_on)}</dd>
        </div>
        <div>
          <dt className="text-ink-500">Maturity</dt>
          <dd className="text-ink-700">{formatDate(deposit.maturity_on)}</dd>
        </div>
        <div>
          <dt className="text-ink-500">Penalty</dt>
          <dd className="text-ink-700">{deposit.penalty_percent ? `${deposit.penalty_percent}%` : "—"}</dd>
        </div>
      </dl>

      <p className="mt-2 flex flex-wrap items-center gap-2 text-12 text-ink-500">
        {SETTLED.has(deposit.status) ? (
          <span>
            Deposit paid; proof and Affidavit 3 were due {formatDate(due)} (APH 2.25f).
          </span>
        ) : (
          <>
            <span>
              Proof + Affidavit 3 due {formatDate(due)}
              {daysLeft === null
                ? ""
                : daysLeft < 0
                  ? ` · ${-daysLeft} day${daysLeft === -1 ? "" : "s"} past`
                  : ` · ${daysLeft} day${daysLeft === 1 ? "" : "s"} left`}
            </span>
            <StatusPill status={daysLeft !== null && daysLeft < 0 ? "breach" : "watch"}>
              {daysLeft !== null && daysLeft < 0 ? "Overdue" : "15-day clock"}
            </StatusPill>
          </>
        )}
      </p>

      {clearances.length > 0 ? (
        <ul className="mt-3 space-y-1">
          {clearances.map((clearance) => {
            const code = String(clearance.code);
            const status = String(clearance.status);
            return (
              <li
                key={code}
                className="flex flex-wrap items-center justify-between gap-2 rounded-input border border-line bg-surface px-3 py-2 text-12"
              >
                <span className="text-ink-700">
                  {String(clearance.label)}{" "}
                  <Clause text={String(clearance.apH_clause)} />
                </span>
                <span className="flex items-center gap-2">
                  <StatusPill
                    status={status === "CLEARED" ? "compliant" : status === "BLOCKED" ? "breach" : "watch"}
                  >
                    {humanizeEnum(status)}
                  </StatusPill>
                  {canClear && status !== "CLEARED" ? (
                    <Button
                      size="sm"
                      variant="secondary"
                      disabled={busy}
                      onClick={() =>
                        run(
                          () =>
                            recordDepositClearance(token, applicationId, deposit.id, {
                              code,
                              cleared: true,
                            }),
                          `${code} clearance recorded`,
                        )
                      }
                    >
                      Mark cleared
                    </Button>
                  ) : null}
                </span>
              </li>
            );
          })}
        </ul>
      ) : null}

      {canRequest && !deposit.release_requested_on ? (
        <div className="mt-3 flex flex-wrap justify-end gap-2">
          {deposit.status !== "RELEASED" && deposit.status !== "WITHDRAWN" ? (
            <Button
              size="sm"
              variant="secondary"
              disabled={busy}
              onClick={() =>
                run(
                  () => withdrawSecurityDeposit(token, applicationId, deposit.id),
                  "Security Deposit marked withdrawn",
                )
              }
            >
              Withdraw deposit (APH 2.25f)
            </Button>
          ) : null}
          {RELEASABLE.has(deposit.status) ? (
            <Button
              size="sm"
              disabled={busy}
              onClick={() =>
                run(
                  () => requestDepositRelease(token, applicationId, deposit.id),
                  "Release request recorded",
                )
              }
            >
              Request release (APH 6.46a)
            </Button>
          ) : null}
        </div>
      ) : null}

      {deposit.release_requested_on ? (
        <p className="mt-2 text-12 text-ink-500">
          Requested on {formatDate(deposit.release_requested_on)}
          {deposit.released_on ? ` · released ${formatDate(deposit.released_on)}` : ""}
          {deposit.noc_number ? ` · NOC ${deposit.noc_number}` : ""}
        </p>
      ) : null}

      {canApprove && deposit.release_requested_on && deposit.status !== "RELEASED" ? (
        <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-[1fr_auto]">
          <Input
            label="NOC / sanction order number"
            value={nocNumber}
            onChange={(event) => setNocNumber(event.target.value)}
          />
          <div className="flex items-end">
            <Button
              size="sm"
              disabled={busy || !nocNumber.trim()}
              onClick={() =>
                run(
                  () =>
                    approveDepositRelease(token, applicationId, deposit.id, {
                      noc_number: nocNumber,
                    }),
                  "Security Deposit released",
                )
              }
            >
              Approve release
            </Button>
          </div>
        </div>
      ) : null}

      {error ? <p className="mt-2 text-13 text-breach-strong">{error}</p> : null}
    </li>
  );
}
