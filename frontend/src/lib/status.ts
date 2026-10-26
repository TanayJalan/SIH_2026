import type { ApplicationStatus } from "./api";

/**
 * States in which the approval cycle is finished, so no SLA clock or overdue
 * badge applies. Mirrors the terminal states of the active workflow
 * definitions plus the legacy pre-APH outcomes.
 */
export const CLOSED_STATUSES: ApplicationStatus[] = [
  "FINAL_LOD",
  "FINAL_LOR",
  "ACTIVE_LOA",
  "ACTIVE_EOA",
  "CANCELLED",
  "CLOSED",
  "WITHDRAWN",
  // Legacy pre-APH values (read-only).
  "APPROVED",
  "REJECTED",
];

export function isClosedStatus(status: string): boolean {
  return CLOSED_STATUSES.includes(status as ApplicationStatus);
}

/**
 * States where the Regulation Bureau may reopen a wrongly submitted
 * application once (APH 2.3.3d-e). Terminal decisions are excluded.
 */
export const REOPENABLE_STATUSES: ApplicationStatus[] = [
  "SUBMITTED",
  "SCRUTINY",
  "DEFICIENCY_COMMUNICATED",
  "INSTITUTION_COMPLIANCE",
  "RE_SCRUTINY",
  // Legacy pre-APH values (read-only).
  "DOCUMENT_VERIFICATION",
  "DEFICIENCY_RAISED",
  "DEFICIENCY_RESPONDED",
];

export function isReopenableStatus(status: string): boolean {
  return REOPENABLE_STATUSES.includes(status as ApplicationStatus);
}
