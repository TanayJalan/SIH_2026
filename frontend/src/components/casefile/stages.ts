import type {
  ApplicationDetail,
  DeficiencyRecord,
  WorkflowDefinition,
  WorkflowEventRecord,
  WorkflowStage,
} from "@/lib/api";
import { formatDate } from "@/lib/format";
import type { StageTrackEvent, StageTrackStage } from "@/components/ui";

/**
 * Presentation order for the APH stages. The stages that actually appear come
 * from `GET /workflow/definition`, so a configured workflow can add or drop a
 * stage without a frontend change.
 */
const STAGE_RANK: Record<WorkflowStage, number> = {
  APPLICATION: 0,
  DOCUMENT_VERIFICATION: 1,
  SCRUTINY: 2,
  DEFICIENCY: 3,
  INSPECTION: 4,
  COMMITTEE_REVIEW: 5,
  DECISION: 6,
  COMPLETED: 7,
};

const STAGE_LABEL: Record<WorkflowStage, string> = {
  APPLICATION: "Application",
  DOCUMENT_VERIFICATION: "Documents",
  SCRUTINY: "Scrutiny",
  DEFICIENCY: "Deficiency",
  INSPECTION: "Inspection",
  COMMITTEE_REVIEW: "Committee",
  DECISION: "Decision",
  COMPLETED: "Completed",
};

/** Build the stage track for the workflow configured for this application. */
export function stagesFromDefinition(
  definition: WorkflowDefinition | undefined,
): StageTrackStage[] {
  if (!definition) {
    return [];
  }
  const present = new Set<WorkflowStage>(
    definition.states.map((state) => state.stage),
  );
  return [...present]
    .sort((left, right) => STAGE_RANK[left] - STAGE_RANK[right])
    .map((stage) => ({ id: stage, label: STAGE_LABEL[stage] }));
}

/**
 * Build StageTrack events from the workflow timeline, the live SLA and open
 * deficiencies. Rules:
 * - a stage is completed at the time an event moved the case to another stage,
 * - the current stage carries its SLA due text,
 * - open deficiencies mark the DEFICIENCY node as blocked.
 */
export function buildStageEvents(
  application: ApplicationDetail,
  events: WorkflowEventRecord[],
  deficiencies: DeficiencyRecord[],
  definition?: WorkflowDefinition,
): StageTrackEvent[] {
  const stageByStatus = new Map(
    (definition?.states ?? []).map((state) => [state.code, state.stage]),
  );
  const completedAt = new Map<string, string>();

  for (const event of events) {
    if (!event.action || !event.from_status) {
      continue;
    }
    const fromStage = stageByStatus.get(event.from_status);
    const toStage = stageByStatus.get(event.to_status);
    if (fromStage && toStage && fromStage !== toStage) {
      completedAt.set(fromStage, formatDate(event.created_at));
    }
  }

  const stageEvents: StageTrackEvent[] = [...completedAt].map(([stage, at]) => ({
    stage,
    at,
  }));

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
