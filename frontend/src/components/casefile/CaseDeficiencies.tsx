import { useQuery } from "@tanstack/react-query";

import { Button, Skeleton, StatusPill, type StatusPillTone } from "../ui";
import { useWorkflowActions } from "../workflow/WorkflowDialogHost";
import { ApiError, listDeficiencies, type DeficiencyRecord } from "@/lib/api";
import { formatDate, formatDateTime, humanizeEnum } from "@/lib/format";
import { useSimulatedNow } from "@/lib/useSimulatedNow";

const DEFICIENCY_TONES: Record<DeficiencyRecord["status"], StatusPillTone> = {
  OPEN: "breach",
  RESPONDED: "watch",
  CLOSED: "compliant",
};

function daysUntil(now: Date, dueDate: string): number {
  const due = new Date(`${dueDate}T00:00:00`).getTime();
  if (Number.isNaN(due)) {
    return 0;
  }
  const today = new Date(now);
  today.setHours(0, 0, 0, 0);
  return Math.round((due - today.getTime()) / 86_400_000);
}

function DueCountdown({ dueDate }: { dueDate: string }) {
  const now = useSimulatedNow();
  const days = daysUntil(now, dueDate);
  const label =
    days < 0
      ? `${-days} day${days === -1 ? "" : "s"} overdue`
      : days === 0
        ? "Due today"
        : `${days} day${days === 1 ? "" : "s"} left`;
  return (
    <StatusPill status={days < 0 ? "breach" : days <= 3 ? "watch" : "info"}>
      {label}
    </StatusPill>
  );
}

export default function CaseDeficiencies({
  applicationId,
  token,
  canRespond,
  canClose,
}: {
  applicationId: string;
  token: string;
  canRespond: boolean;
  canClose: boolean;
}) {
  const { findAction, openAction } = useWorkflowActions();
  const deficienciesQuery = useQuery({
    queryKey: ["deficiencies", applicationId],
    queryFn: () => listDeficiencies(token, applicationId),
    enabled: Boolean(token && applicationId),
    retry: false,
  });

  const deficiencies = deficienciesQuery.data ?? [];
  const open = deficiencies.filter((item) => item.status === "OPEN").length;
  const respondAction = findAction("submit_compliance");
  const closeAction = findAction("re_scrutiny_verify");

  return (
    <section className="rounded-panel border border-line bg-surface p-5 sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="font-serif text-20 font-semibold text-ink">Deficiencies</h2>
          <p className="mt-1 text-13 text-ink-500">
            Gaps raised during scrutiny and the institution's responses.
          </p>
        </div>
        <span className="rounded-pill bg-paper px-2.5 py-1 text-12 text-ink-700">
          {open} open
        </span>
      </div>

      {deficienciesQuery.isPending ? (
        <div className="mt-4 space-y-3" role="status">
          {[0, 1].map((item) => (
            <Skeleton key={item} className="h-20 w-full" />
          ))}
          <span className="sr-only">Loading deficiencies</span>
        </div>
      ) : deficienciesQuery.isError ? (
        <p className="mt-4 rounded-input border border-breach bg-breach-soft p-3 text-13 text-breach-strong">
          {deficienciesQuery.error instanceof ApiError
            ? deficienciesQuery.error.message
            : "Deficiencies could not be loaded."}
        </p>
      ) : deficiencies.length === 0 ? (
        <p className="mt-4 rounded-input border border-line bg-paper p-4 text-13 text-ink-700">
          No deficiencies have been raised for this application.
        </p>
      ) : (
        <ul className="mt-4 space-y-3">
          {deficiencies.map((deficiency) => (
            <li key={deficiency.id} className="rounded-input border border-line p-4">
              <div className="flex flex-wrap items-center gap-2">
                <StatusPill status={DEFICIENCY_TONES[deficiency.status]}>
                  {humanizeEnum(deficiency.status)}
                </StatusPill>
                <span className="text-12 font-medium text-ink-700">
                  {deficiency.category}
                </span>
                <DueCountdown dueDate={deficiency.due_date} />
                <span className="text-12 text-ink-500">
                  Due {formatDate(deficiency.due_date)}
                </span>
              </div>
              <p className="mt-2 text-13 leading-5 text-ink-700">
                {deficiency.description}
              </p>
              <p className="mt-1 text-11 text-ink-500">
                Raised by {deficiency.raised_by_name ?? "officer"} on{" "}
                {formatDate(deficiency.created_at)}
              </p>
              {deficiency.response_text ? (
                <div className="mt-3 rounded-input border border-line bg-paper p-3">
                  <p className="text-11 font-semibold uppercase tracking-wide text-ink-500">
                    Institution response
                  </p>
                  <p className="mt-1 text-13 leading-5 text-ink-700">
                    {deficiency.response_text}
                  </p>
                  {deficiency.response_document_filename ? (
                    <p className="mt-1 text-12 text-ink-500">
                      Attachment: {deficiency.response_document_filename}
                    </p>
                  ) : null}
                  <p className="mt-1 text-11 text-ink-500">
                    Responded {formatDateTime(deficiency.responded_at)}
                    {deficiency.closed_at
                      ? ` · Closed ${formatDateTime(deficiency.closed_at)}`
                      : null}
                  </p>
                </div>
              ) : null}
              <div className="mt-3 flex flex-wrap gap-2">
                {deficiency.status === "OPEN" &&
                canRespond &&
                respondAction ? (
                  <Button
                    variant="primary"
                    size="sm"
                    onClick={() => openAction(respondAction)}
                  >
                    Respond
                  </Button>
                ) : null}
                {deficiency.status === "RESPONDED" &&
                canClose &&
                closeAction ? (
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={() =>
                      openAction(closeAction, { deficiencyId: deficiency.id })
                    }
                  >
                    Review and close
                  </Button>
                ) : null}
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
