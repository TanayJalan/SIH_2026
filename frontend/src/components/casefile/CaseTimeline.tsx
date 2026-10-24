import { useQuery } from "@tanstack/react-query";

import { Skeleton } from "../ui";
import {
  ApiError,
  getWorkflowTimeline,
  type WorkflowEventRecord,
} from "@/lib/api";
import { formatDateTime, humanizeEnum } from "@/lib/format";
import { cn } from "@/lib/utils";

function eventHeading(event: WorkflowEventRecord): string {
  if (event.action) {
    return humanizeEnum(event.action);
  }
  if (event.from_status) {
    return `${humanizeEnum(event.from_status)} → ${humanizeEnum(event.to_status)}`;
  }
  return humanizeEnum(event.to_status);
}

function eventDetail(event: WorkflowEventRecord): string | null {
  const details = event.details;
  if (!details) {
    return null;
  }
  const officerName = details.officer_name;
  if (typeof officerName === "string") {
    return `Assigned to ${officerName}`;
  }
  const committeeName = details.committee_name;
  if (typeof committeeName === "string") {
    return `Committee: ${committeeName}`;
  }
  const recommendation = details.recommendation;
  if (typeof recommendation === "string") {
    return `Recommendation: ${humanizeEnum(recommendation)}`;
  }
  const count = details.count;
  if (typeof count === "number") {
    return null;
  }
  const remaining = details.remaining;
  if (typeof remaining === "number") {
    return remaining === 0
      ? "All deficiency items closed"
      : `${remaining} deficiency item${remaining === 1 ? "" : "s"} still open`;
  }
  const conditions = details.conditions;
  if (typeof conditions === "string" && conditions.trim()) {
    return `Conditions: ${conditions}`;
  }
  return null;
}

function TimelineEntry({
  event,
  last,
}: {
  event: WorkflowEventRecord;
  last: boolean;
}) {
  const detail = eventDetail(event);
  const statusChanged = event.from_status !== event.to_status;
  const hasAuditPayload = Boolean(event.details) || Boolean(event.comment);

  return (
    <li className="relative flex gap-3 pb-5 last:pb-0">
      {!last ? (
        <span
          aria-hidden="true"
          className="absolute left-[7px] top-5 h-[calc(100%-1.25rem)] w-px bg-line"
        />
      ) : null}
      <span
        aria-hidden="true"
        className={cn(
          "relative mt-1 size-3.5 shrink-0 rounded-full border-2 bg-surface",
          last ? "border-ink" : "border-ink-300",
        )}
      />
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
          <p className="text-13 font-semibold text-ink">{eventHeading(event)}</p>
          <time
            dateTime={event.created_at}
            className="text-11 tabular-nums text-ink-500"
          >
            {formatDateTime(event.created_at)}
          </time>
        </div>
        <p className="mt-0.5 text-12 text-ink-500">
          {event.actor_name ?? "System"}
          {statusChanged && event.from_status
            ? ` · ${humanizeEnum(event.from_status)} → ${humanizeEnum(event.to_status)}`
            : null}
        </p>
        {event.comment ? (
          <p className="mt-1.5 text-13 leading-5 text-ink-700">{event.comment}</p>
        ) : null}
        {detail ? (
          <p className="mt-1 text-12 leading-5 text-ink-500">{detail}</p>
        ) : null}
        {hasAuditPayload ? (
          <details className="mt-1 text-12">
            <summary className="cursor-pointer text-ink-500 hover:text-ink">
              Audit detail
            </summary>
            <pre className="mt-1 max-w-full overflow-x-auto rounded-input border border-line bg-paper p-2 text-11 text-ink-700">
              {JSON.stringify(
                {
                  action: event.action,
                  from_status: event.from_status,
                  to_status: event.to_status,
                  comment: event.comment,
                  details: event.details,
                },
                null,
                2,
              )}
            </pre>
          </details>
        ) : null}
      </div>
    </li>
  );
}

export default function CaseTimeline({
  applicationId,
  token,
}: {
  applicationId: string;
  token: string;
}) {
  const timelineQuery = useQuery({
    queryKey: ["workflow-timeline", applicationId],
    queryFn: () => getWorkflowTimeline(token, applicationId),
    enabled: Boolean(token && applicationId),
    retry: false,
  });

  const events = timelineQuery.data?.events ?? [];

  return (
    <section className="rounded-panel border border-line bg-surface p-5 sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="font-serif text-20 font-semibold text-ink">Timeline</h2>
          <p className="mt-1 text-13 text-ink-500">
            Every state change, actor and decision recorded against this case.
          </p>
        </div>
        {timelineQuery.data ? (
          <span className="rounded-pill bg-paper px-2.5 py-1 text-12 text-ink-700">
            {events.length} event{events.length === 1 ? "" : "s"}
          </span>
        ) : null}
      </div>

      {timelineQuery.isPending ? (
        <div className="mt-5 space-y-3" role="status">
          {[0, 1, 2].map((item) => (
            <Skeleton key={item} className="h-16 w-full" />
          ))}
          <span className="sr-only">Loading workflow timeline</span>
        </div>
      ) : timelineQuery.isError ? (
        <p className="mt-4 rounded-input border border-breach bg-breach-soft p-3 text-13 text-breach-strong">
          {timelineQuery.error instanceof ApiError
            ? timelineQuery.error.message
            : "The workflow timeline could not be loaded."}
        </p>
      ) : events.length === 0 ? (
        <p className="mt-4 rounded-input border border-line bg-paper p-4 text-13 text-ink-700">
          No workflow events have been recorded yet.
        </p>
      ) : (
        <ol className="mt-5" aria-label="Workflow events">
          {events.map((event, index) => (
            <TimelineEntry
              key={event.id}
              event={event}
              last={index === events.length - 1}
            />
          ))}
        </ol>
      )}
    </section>
  );
}
