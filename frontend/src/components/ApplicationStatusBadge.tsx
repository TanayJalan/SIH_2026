import { StatusPill, type StatusPillTone } from "./ui";
import type { ApplicationStatus } from "../lib/api";
import { humanizeEnum } from "../lib/format";

const STATUS_TONES: Record<ApplicationStatus, StatusPillTone> = {
  DRAFT: "neutral",
  SUBMITTED: "info",
  DOCUMENT_VERIFICATION: "info",
  SCRUTINY: "watch",
  DEFICIENCY_RAISED: "breach",
  DEFICIENCY_RESPONDED: "watch",
  INSPECTION_SCHEDULED: "info",
  INSPECTION_DONE: "info",
  COMMITTEE_REVIEW: "watch",
  APPROVED: "compliant",
  CONDITIONALLY_APPROVED: "watch",
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
    <StatusPill status={STATUS_TONES[status]} className={className}>
      {humanizeEnum(status)}
    </StatusPill>
  );
}
