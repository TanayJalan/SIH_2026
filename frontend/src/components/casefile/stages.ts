import type { ApplicationDetail, DeficiencyRecord, WorkflowEventRecord } from "@/lib/api";
import { formatDate } from "@/lib/format";
import type { StageTrackEvent, StageTrackStage } from "@/components/ui";

/** The seven stages a case moves through; decisions land in COMPLETED. */
export const CASE_STAGES: StageTrackStage[] = [
  { id: "APPLICATION", label: "Application" },
  { id: "DOCUMENT_VERIFICATION", label: "Doc verification" },
  { id: "SCRUTINY", label: "Scrutiny" },
  { id: "DEFICIENCY", label: "Deficiency" },
  { id: "INSPECTION", label: "Inspection" },
  { id: "COMMITTEE_REVIEW", label: "Committee" },
  { id: "COMPLETED", label: "Completed" },
];

type StageLeavingAction = "verify_documents" | "start_scrutiny" | "raise_deficiency" | "schedule_inspection" | "send_to_committee" | "approve" | "conditionally_approve" | "reject" | "submit";

const STAGE_EXITING: Record<string, StageLeavingAction[]> = {
  APPLICATION: ["submit"],
  DOCUMENT_VERIFICATION: ["verify_documents", "start_scrutiny"],
  SCRUTINY: ["raise_deficiency", "schedule_inspection"],
  DEFICIENCY: ["schedule_inspection"],
  INSPECTION: ["send_to_committee"],
  COMMITTEE_REVIEW: ["approve", "conditionally_approve", "reject"],
};

/**
 * Build StageTrack events from the workflow timeline, the live SLA and open
 * deficiencies. Rules:
 * - a stage is completed at the time of the first event whose action left it,
 * - the current stage carries its SLA due text,
 * - open deficiencies mark the DEFICIENCY node as blocked.
 */
export function buildStageEvents(
  application: ApplicationDetail,
  events: WorkflowEventRecord[],
  deficiencies: DeficiencyRecord[],
): StageTrackEvent[] {
  const stageEvents: StageTrackEvent[] = [];

  for (const [stage, actions] of Object.entries(STAGE_EXITING)) {
    const exit = events.find(
      (event) => event.action && (actions as string[]).includes(event.action),
    );
    if (exit) {
      stageEvents.push({ stage, at: formatDate(exit.created_at) });
    }
  }

  if (
    application.status !== "DRAFT" &&
    application.current_stage !== "COMPLETED" &&
    application.sla_due_at
  ) {
    stageEvents.push({
      stage: application.current_stage,
      at: `SLA due ${formatDate(application.sla_due_at)}`,
    });
  }

  if (deficiencies.some((item) => item.status !== "CLOSED")) {
    stageEvents.push({ stage: "DEFICIENCY", blocked: true });
  }

  return stageEvents;
}
