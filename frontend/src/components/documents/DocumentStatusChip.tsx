import { StatusPill, type StatusPillTone } from "../ui";
import type {
  DocumentRejectionReason,
  DocumentVerificationStatus,
} from "@/lib/api";
import { formatDate } from "@/lib/format";
import { cn } from "@/lib/utils";

/** Institution-facing wording for the reviewer's reason code (APH 1.8f). */
export const REJECTION_REASON_LABELS: Record<DocumentRejectionReason, string> = {
  UNREADABLE: "Unreadable scan",
  NO_DSC: "Not digitally signed",
  EXPIRED: "Expired certificate",
  WRONG_DOCUMENT: "Wrong document",
  NAME_MISMATCH: "Name mismatch",
  INCOMPLETE: "Incomplete document",
  OTHER: "Other reason",
};

export const DOCUMENT_STATUS_LABELS: Record<DocumentVerificationStatus, string> = {
  PENDING: "Pending",
  VERIFIED: "Verified",
  FLAGGED: "Flagged",
  REJECTED: "Rejected",
};

const STATUS_TONES: Record<DocumentVerificationStatus, StatusPillTone> = {
  VERIFIED: "compliant",
  FLAGGED: "watch",
  REJECTED: "breach",
  PENDING: "neutral",
};

interface DocumentStatusChipProps {
  status: DocumentVerificationStatus | null | undefined;
  rejectionReasonCode?: DocumentRejectionReason | null;
  rejectionComment?: string | null;
  apHclause?: string | null;
  rejectedAt?: string | null;
  dueDate?: string | null;
  compact?: boolean;
  className?: string;
}

/**
 * The one status chip used by both the wizard Documents step and the case file.
 *
 * It shows the verification status plus, when a reviewer rejected the file, the
 * controlled reason code, their comment and the APH clause so the institution
 * knows exactly what to replace (APH 1.8f, 1.8g).
 */
export default function DocumentStatusChip({
  status,
  rejectionReasonCode,
  rejectionComment,
  apHclause,
  rejectedAt,
  dueDate,
  compact = false,
  className,
}: DocumentStatusChipProps) {
  if (!status) {
    return null;
  }
  const tone = STATUS_TONES[status] ?? "neutral";
  const showDetail =
    !compact &&
    (status === "REJECTED" || status === "FLAGGED") &&
    Boolean(rejectionReasonCode || rejectionComment);

  return (
    <div className={cn("min-w-0", className)}>
      <StatusPill status={tone} className="text-11">
        {DOCUMENT_STATUS_LABELS[status] ?? status}
      </StatusPill>
      {showDetail ? (
        <div className="mt-1.5 rounded-input border border-line bg-paper p-2.5 text-12 leading-5 text-ink-700">
          {rejectionReasonCode ? (
            <p className="font-medium text-ink">
              {REJECTION_REASON_LABELS[rejectionReasonCode] ?? rejectionReasonCode}
              {apHclause ? (
                <span className="ml-1 font-normal text-ink-500">({apHclause})</span>
              ) : null}
            </p>
          ) : null}
          {rejectionComment ? <p className="mt-0.5">{rejectionComment}</p> : null}
          <p className="mt-1 text-11 text-ink-500">
            {rejectedAt ? `Rejected ${formatDate(rejectedAt)} · ` : ""}
            {dueDate ? `Re-upload due ${formatDate(dueDate)}` : "Awaiting a replacement"}
          </p>
        </div>
      ) : null}
    </div>
  );
}
