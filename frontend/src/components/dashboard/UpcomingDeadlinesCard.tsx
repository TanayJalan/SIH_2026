import { useQuery } from "@tanstack/react-query";
import { CalendarClock } from "lucide-react";
import { Link } from "react-router-dom";

import { Skeleton, StatusPill, type StatusPillTone } from "@/components/ui";
import {
  getApplicationDeadlines,
  getApplications,
  type ApplicationRecord,
} from "@/lib/api";
import { formatDate, shortId } from "@/lib/format";
import { isClosedStatus } from "@/lib/status";

interface DeadlineRow {
  key: string;
  kind: "appeal" | "deposit" | "loa-validity";
  kindLabel: string;
  apH_clause: string;
  due: string | null;
  daysLeft: number | null;
  applicationId: string;
  reference: string;
}

const KIND_TONES: Record<DeadlineRow["kind"], StatusPillTone> = {
  appeal: "breach",
  deposit: "watch",
  "loa-validity": "info",
};

function rowsForApplication(
  application: ApplicationRecord,
  deadlines: Awaited<ReturnType<typeof getApplicationDeadlines>>,
): DeadlineRow[] {
  const rows: DeadlineRow[] = [];
  const reference = application.reference ?? `Application ${shortId(application.id)}`;
  if (deadlines.appeal?.deadline !== null && deadlines.appeal) {
    rows.push({
      key: `${application.id}-appeal`,
      kind: "appeal",
      kindLabel: "Appeal window closes",
      apH_clause: deadlines.appeal.apH_clause,
      due: deadlines.appeal.deadline,
      daysLeft: deadlines.appeal.days_left,
      applicationId: application.id,
      reference,
    });
  }
  const deposit = deadlines.security_deposit;
  if (deposit && deposit.due_on && deposit.current_stage !== "paid") {
    rows.push({
      key: `${application.id}-deposit`,
      kind: "deposit",
      kindLabel:
        deposit.current_stage === "withdrawal"
          ? "Deposit withdrawal date"
          : "Security Deposit due",
      apH_clause: deposit.apH_clause,
      due: deposit.due_on,
      daysLeft: deposit.days_left,
      applicationId: application.id,
      reference,
    });
  }
  const validity = deadlines.loa_validity;
  if (validity && !validity.expired) {
    rows.push({
      key: `${application.id}-loa-validity`,
      kind: "loa-validity",
      kindLabel: "LoA validity ends",
      apH_clause: validity.apH_clause,
      due: validity.valid_until,
      daysLeft: validity.days_left,
      applicationId: application.id,
      reference,
    });
  }
  return rows;
}

function daysTone(daysLeft: number | null): StatusPillTone {
  if (daysLeft === null) {
    return "neutral";
  }
  if (daysLeft < 0) {
    return "breach";
  }
  return daysLeft <= 3 ? "watch" : "compliant";
}

export default function UpcomingDeadlinesCard({
  token,
  className,
}: {
  token: string;
  className?: string;
}) {
  const applicationsQuery = useQuery({
    queryKey: ["applications", "deadlines-card"],
    queryFn: () => getApplications(token, { page: 1, pageSize: 20 }),
    retry: false,
  });

  const openApplications = (applicationsQuery.data?.items ?? [])
    .filter(
      (application) =>
        !isClosedStatus(application.status) && !application.is_withdrawn,
    );

  // One small read per open file: the deadlines endpoint is the single
  // configuration-driven source for every countdown shown here.
  const deadlinesQueries = useQuery({
    queryKey: ["application-deadlines", "card", openApplications.map((a) => a.id)],
    queryFn: () =>
      Promise.all(
        openApplications.map((application) =>
          getApplicationDeadlines(token, application.id),
        ),
      ),
    enabled: Boolean(token) && openApplications.length > 0,
    retry: false,
  });

  const rows = deadlineRows(openApplications, deadlinesQueries.data);

  return (
    <section
      className={`rounded-panel border border-line bg-surface p-5 ${className ?? ""}`}
      aria-label="Upcoming statutory deadlines"
    >
      <div className="flex items-center gap-2">
        <CalendarClock aria-hidden="true" className="size-4 text-ink-500" />
        <h2 className="text-14 font-semibold text-ink">Upcoming deadlines</h2>
      </div>
      <p className="mt-1 text-12 text-ink-500">
        Appeal, Security Deposit and LoA clocks from the configured deadline rules (illustrative
        demo dates — verify against the current AICTE handbook).
      </p>

      {applicationsQuery.isPending || deadlinesQueries.isPending ? (
        <div className="mt-4 space-y-2" role="status">
          <Skeleton className="h-4 w-3/4" />
          <Skeleton className="h-4 w-1/2" />
          <span className="sr-only">Loading deadlines</span>
        </div>
      ) : rows.length === 0 ? (
        <p className="mt-4 rounded-input border border-line bg-paper p-4 text-13 leading-5 text-ink-700">
          No statutory deadline is currently running on your open applications. Deadlines appear
          when a decision letter is issued or an appeal window opens.
        </p>
      ) : (
        <ul className="mt-4 space-y-2">
          {rows.map((row) => (
            <li
              key={row.key}
              className="rounded-input border border-line bg-paper p-3"
            >
              <div className="flex flex-wrap items-center gap-2">
                <StatusPill status={KIND_TONES[row.kind]}>{row.kindLabel}</StatusPill>
                <span className="text-12 tabular-nums text-ink-500">
                  {row.due ? formatDate(row.due) : "—"}
                </span>
                <StatusPill status={daysTone(row.daysLeft)}>
                  {row.daysLeft === null
                    ? "No clock"
                    : row.daysLeft < 0
                      ? `${-row.daysLeft} day${row.daysLeft === -1 ? "" : "s"} past`
                      : `${row.daysLeft} day${row.daysLeft === 1 ? "" : "s"} left`}
                </StatusPill>
              </div>
              <p className="mt-1 text-13 font-medium text-ink">{row.reference}</p>
              <div className="mt-1 flex items-center justify-between gap-2 text-12">
                <span className="rounded-pill bg-neutral-soft px-2 py-0.5 text-11 font-medium text-ink-700">
                  {row.apH_clause}
                </span>
                <Link
                  to={`/applications/${row.applicationId}`}
                  className="text-ink-700 underline-offset-4 hover:text-ink hover:underline"
                >
                  Open case file
                </Link>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function deadlineRows(
  openApplications: ApplicationRecord[],
  deadlines: Awaited<ReturnType<typeof getApplicationDeadlines>>[] | undefined,
): DeadlineRow[] {
  if (!deadlines) {
    return [];
  }
  const rows = openApplications.flatMap((application, index) => {
    const data = deadlines[index];
    if (data === undefined) {
      return [];
    }
    return rowsForApplication(application, data);
  });
  return rows
    .sort((left, right) => {
      const leftDue = left.due ? left.due : "9999-12-31";
      const rightDue = right.due ? right.due : "9999-12-31";
      return leftDue.localeCompare(rightDue);
    })
    .slice(0, 5);
}
