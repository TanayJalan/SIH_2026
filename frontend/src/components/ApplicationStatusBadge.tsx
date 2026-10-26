import { StatusPill, type StatusPillTone } from "./ui";
import type { ApplicationStatus } from "../lib/api";
import { humanizeEnum } from "../lib/format";

/**
 * Tone for every APH state, including the legacy pre-APH values that remain
 * readable on historical rows. Keep this map exhaustive so a backend state
 * cannot reach the UI without a deliberate tone.
 */
const STATUS_TONES: Record<ApplicationStatus, StatusPillTone> = {
  // Track A.
  DRAFT: "neutral",
  SUBMITTED: "info",
  SCRUTINY: "watch",
  DEFICIENCY_COMMUNICATED: "breach",
  INSTITUTION_COMPLIANCE: "watch",
  RE_SCRUTINY: "watch",
  EVC_CONSTITUTED: "info",
  EVC_DONE: "info",
  REGULATION_BUREAU_OBSERVATIONS: "watch",
  EC_DECISION: "watch",
  COUNCIL_RATIFICATION: "watch",
  LOA_ISSUED: "compliant",
  LOD_ISSUED: "breach",
  LOR_ISSUED: "breach",
  APPEAL_WINDOW: "watch",
  SAC_REVIEW: "watch",
  COUNCIL_FINAL: "watch",
  REGIONAL_ENDORSEMENT: "watch",
  FINAL_LOA: "compliant",
  FINAL_LOD: "breach",
  FINAL_LOR: "breach",
  SECURITY_DEPOSIT_PENDING: "watch",
  ACTIVE_LOA: "compliant",
  CANCELLED: "breach",
  WITHDRAWN: "neutral",
  // Track B.
  SELF_DISCLOSURE_CHECK: "info",
  RANDOM_EVC: "info",
  COMPLIANCE_WINDOW: "watch",
  EC_LISTING: "watch",
  EOA_ISSUED: "compliant",
  SPEAKING_ORDER: "watch",
  ACTIVE_EOA: "compliant",
  // Track C / D.
  SHC_HEARING: "watch",
  CLOSED: "neutral",
  // Legacy pre-APH values (read-only).
  DOCUMENT_VERIFICATION: "info",
  DEFICIENCY_RAISED: "breach",
  DEFICIENCY_RESPONDED: "watch",
  INSPECTION_SCHEDULED: "info",
  INSPECTION_DONE: "info",
  COMMITTEE_REVIEW: "watch",
  APPROVED: "compliant",
  REJECTED: "breach",
};

export default function ApplicationStatusBadge({
  status,
  isWithdrawn = false,
  className,
}: {
  status: ApplicationStatus;
  isWithdrawn?: boolean;
  className?: string;
}) {
  if (isWithdrawn) {
    return (
      <StatusPill status="neutral" className={className}>
        Withdrawn
      </StatusPill>
    );
  }

  return (
    <StatusPill
      status={STATUS_TONES[status] ?? "neutral"}
      className={className}
    >
      {humanizeEnum(status)}
    </StatusPill>
  );
}
