import { useQuery } from "@tanstack/react-query";

import { Button, Skeleton, StatusPill, type StatusPillTone } from "../ui";
import { useWorkflowActions } from "../workflow/WorkflowDialogHost";
import {
  ApiError,
  listInspections,
  type InspectionRecord,
} from "@/lib/api";
import { formatDate, formatDateTime, humanizeEnum } from "@/lib/format";

const INSPECTION_TONES: Record<InspectionRecord["status"], StatusPillTone> = {
  SCHEDULED: "info",
  COMPLETED: "compliant",
  CANCELLED: "neutral",
};

export default function CaseInspection({
  applicationId,
  token,
  canSchedule,
}: {
  applicationId: string;
  token: string;
  canSchedule: boolean;
}) {
  const { findAction, openAction } = useWorkflowActions();
  const inspectionsQuery = useQuery({
    queryKey: ["inspections", applicationId],
    queryFn: () => listInspections(token, applicationId),
    enabled: Boolean(token && applicationId),
    retry: false,
  });

  const inspections = inspectionsQuery.data ?? [];
  const scheduleAction = findAction("schedule_inspection");

  return (
    <section className="rounded-panel border border-line bg-surface p-5 sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="font-serif text-20 font-semibold text-ink">Inspection</h2>
          <p className="mt-1 text-13 text-ink-500">
            Scheduled visits and the committee's structured report.
          </p>
        </div>
        {canSchedule && scheduleAction ? (
          <Button variant="primary" size="sm" onClick={() => openAction(scheduleAction)}>
            Schedule inspection
          </Button>
        ) : null}
      </div>

      {inspectionsQuery.isPending ? (
        <div className="mt-4 space-y-3" role="status">
          {[0, 1].map((item) => (
            <Skeleton key={item} className="h-24 w-full" />
          ))}
          <span className="sr-only">Loading inspections</span>
        </div>
      ) : inspectionsQuery.isError ? (
        <p className="mt-4 rounded-input border border-breach bg-breach-soft p-3 text-13 text-breach-strong">
          {inspectionsQuery.error instanceof ApiError
            ? inspectionsQuery.error.message
            : "Inspections could not be loaded."}
        </p>
      ) : inspections.length === 0 ? (
        <p className="mt-4 rounded-input border border-line bg-paper p-4 text-13 text-ink-700">
          No inspection has been scheduled yet.
        </p>
      ) : (
        <ul className="mt-4 space-y-3">
          {inspections.map((inspection) => (
            <li key={inspection.id} className="rounded-input border border-line p-4">
              <div className="flex flex-wrap items-center gap-2">
                <StatusPill status={INSPECTION_TONES[inspection.status]}>
                  {humanizeEnum(inspection.status)}
                </StatusPill>
                <span className="text-12 text-ink-500">
                  Scheduled {formatDateTime(inspection.scheduled_on)}
                </span>
              </div>
              <p className="mt-2 text-13 font-medium text-ink">
                {inspection.committee_name ?? "Inspection committee"}
              </p>
              {inspection.report ? (
                <div className="mt-3 space-y-2 rounded-input border border-line bg-paper p-3">
                  <p className="text-11 font-semibold uppercase tracking-wide text-ink-500">
                    Structured report · {formatDate(inspection.created_at)}
                  </p>
                  <ul className="grid gap-1 text-12 text-ink-700 sm:grid-cols-3">
                    <li>
                      Infrastructure:{" "}
                      <strong className="font-semibold">
                        {inspection.report.infrastructure_ok ? "Verified" : "Not verified"}
                      </strong>
                    </li>
                    <li>
                      Faculty:{" "}
                      <strong className="font-semibold">
                        {inspection.report.faculty_verified ? "Verified" : "Not verified"}
                      </strong>
                    </li>
                    <li>
                      Laboratories:{" "}
                      <strong className="font-semibold">
                        {inspection.report.lab_verified ? "Verified" : "Not verified"}
                      </strong>
                    </li>
                  </ul>
                  <p className="text-13 leading-5 text-ink-700">
                    {inspection.report.observations}
                  </p>
                  <p className="text-12 font-semibold text-ink">
                    Recommendation:{" "}
                    {humanizeEnum(inspection.report.recommendation)}
                  </p>
                </div>
              ) : inspection.status === "SCHEDULED" ? (
                <p className="mt-2 text-12 text-ink-500">
                  The committee has not submitted a report yet.
                </p>
              ) : null}
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
