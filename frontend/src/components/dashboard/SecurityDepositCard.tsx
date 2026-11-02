import { useQuery } from "@tanstack/react-query";
import { Landmark } from "lucide-react";
import { Link } from "react-router-dom";

import { Skeleton, StatusPill, type StatusPillTone } from "@/components/ui";
import { getApplications, listSecurityDeposits } from "@/lib/api";
import { formatDate, formatInr, humanizeEnum } from "@/lib/format";
import { calendarDaysUntil, useSimulatedNow } from "@/lib/useSimulatedNow";

const STATUS_TONES: Record<string, StatusPillTone> = {
  PENDING: "watch",
  PAID: "compliant",
  PENALTY_10: "watch",
  PENALTY_20: "breach",
  WITHDRAWN: "breach",
  RELEASED: "compliant",
  FORFEITED: "breach",
};

const OPEN_STATUSES = new Set(["SECURITY_DEPOSIT_PENDING", "ACTIVE_LOA", "FINAL_LOA"]);

/** Only an unpaid deposit runs the 15-day clock and the penalty ladder. */
const UNSETTLED = new Set(["PENDING", "PENALTY_10", "PENALTY_20"]);

/** APH 2.25f fixes the 15-day proof window and the 10%/20% penalty ceilings. */
const GRACE_DAYS = 15;
const PENALTY_WINDOWS =
  "Penalty 10% up to 31 May and 20% up to 31 July; beyond that the approval is withdrawn (APH 2.25f).";

function dueDate(createdOn: string): string {
  const date = new Date(createdOn);
  date.setUTCDate(date.getUTCDate() + GRACE_DAYS);
  return date.toISOString().slice(0, 10);
}

export default function SecurityDepositCard({
  token,
  className,
}: {
  token: string;
  className?: string;
}) {
  const now = useSimulatedNow();
  const applicationsQuery = useQuery({
    queryKey: ["applications", "deposit-card"],
    queryFn: () => getApplications(token, { page: 1, pageSize: 20 }),
    retry: false,
  });

  const openApplications = (applicationsQuery.data?.items ?? []).filter((application) =>
    OPEN_STATUSES.has(application.status),
  );

  const depositsQuery = useQuery({
    queryKey: ["security-deposits", "card", openApplications.map((a) => a.id)],
    queryFn: () =>
      Promise.all(
        openApplications.map(async (application) => ({
          application,
          deposits: await listSecurityDeposits(token, application.id),
        })),
      ),
    enabled: Boolean(token) && openApplications.length > 0,
    retry: false,
  });

  const rows = (depositsQuery.data ?? []).flatMap(({ application, deposits }) =>
    deposits.map((deposit) => ({ application, deposit })),
  );

  return (
    <section
      className={`rounded-panel border border-line bg-surface p-5 ${className ?? ""}`}
      aria-label="Security Deposit tracker"
    >
      <div className="flex items-center gap-2">
        <Landmark aria-hidden="true" className="size-4 text-ink-500" />
        <h2 className="text-14 font-semibold text-ink">Security Deposit tracker</h2>
      </div>
      <p className="mt-1 text-12 text-ink-500">
        Table 1.4 amounts, the 15-day clock and the penalty ladder. Illustrative demo values —
        verify against the current AICTE handbook.
      </p>

      {applicationsQuery.isPending || depositsQuery.isPending ? (
        <div className="mt-4 space-y-2" role="status">
          <Skeleton className="h-4 w-3/4" />
          <Skeleton className="h-4 w-1/2" />
          <span className="sr-only">Loading Security Deposits</span>
        </div>
      ) : rows.length === 0 ? (
        <p className="mt-4 rounded-input border border-line bg-paper p-4 text-13 leading-5 text-ink-700">
          No Security Deposit is on record. A deposit appears after an LoA is recommended
          (APH 1.12).
        </p>
      ) : (
        <ul className="mt-4 space-y-2">
          {rows.map(({ application, deposit }) => {
            const due = dueDate(deposit.created_on);
            const daysLeft = calendarDaysUntil(now, due);
            return (
              <li
                key={deposit.id}
                className="rounded-input border border-line bg-paper p-3"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <StatusPill status={STATUS_TONES[deposit.status] ?? "neutral"}>
                    {humanizeEnum(deposit.status)}
                  </StatusPill>
                  <span className="text-12 tabular-nums font-medium text-ink">
                    {formatInr(deposit.required_paise)}
                  </span>
                  {deposit.doubled_for_leased ? (
                    <span className="text-11 text-watch-strong">Doubled (leased)</span>
                  ) : null}
                  <span className="rounded-pill bg-neutral-soft px-2 py-0.5 text-11 font-medium text-ink-700">
                    {deposit.apH_clause}
                  </span>
                </div>
                <p className="mt-1 text-13 font-medium text-ink">
                  {application.reference ?? `Application ${application.id.slice(0, 8)}`} ·{" "}
                  {humanizeEnum(deposit.programme_family)} {deposit.level}
                </p>
                <div className="mt-1 flex flex-wrap items-center justify-between gap-2 text-12">
                  <span className="text-ink-500">
                    {UNSETTLED.has(deposit.status) ? (
                      <>
                        Proof + Affidavit 3 due {formatDate(due)}
                        {daysLeft === null
                          ? ""
                          : daysLeft < 0
                            ? ` · ${-daysLeft} day${daysLeft === -1 ? "" : "s"} past`
                            : ` · ${daysLeft} day${daysLeft === 1 ? "" : "s"} left`}
                      </>
                    ) : (
                      "Deposit settled; release can be requested with the 6.46b clearances"
                    )}
                  </span>
                  <Link
                    to={`/applications/${application.id}`}
                    className="text-ink-700 underline-offset-4 hover:text-ink hover:underline"
                  >
                    Open case file
                  </Link>
                </div>
                {UNSETTLED.has(deposit.status) ? (
                  <p className="mt-1 text-11 leading-4 text-ink-500">{PENALTY_WINDOWS}</p>
                ) : null}
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
