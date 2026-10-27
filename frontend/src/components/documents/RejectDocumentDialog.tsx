import { useEffect, useState } from "react";
import { Loader2, XCircle } from "lucide-react";

import {
  Button,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  Input,
  Select,
  Textarea,
  useToast,
} from "../ui";
import { REJECTION_REASON_LABELS } from "./DocumentStatusChip";
import {
  ApiError,
  rejectApplicationDocument,
  type DocumentRecord,
  type DocumentRejectionReason,
} from "@/lib/api";

const REASON_OPTIONS = (
  Object.keys(REJECTION_REASON_LABELS) as DocumentRejectionReason[]
).map((value) => ({ value, label: REJECTION_REASON_LABELS[value] }));

export interface RejectTarget {
  id: string;
  label: string;
  docType: string;
  version: number | null;
}

interface RejectDocumentDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  token: string;
  applicationId: string;
  document: RejectTarget | null;
  onRejected: (document: DocumentRecord) => void;
}

/**
 * Reviewer rejection of one document.
 *
 * The reason code is copied into the deficiency the institution must answer, so
 * it is required and the comment is mandatory (APH 1.8f, 2.4).
 */
export default function RejectDocumentDialog({
  open,
  onOpenChange,
  token,
  applicationId,
  document,
  onRejected,
}: RejectDocumentDialogProps) {
  const { toast } = useToast();
  const [reasonCode, setReasonCode] = useState<DocumentRejectionReason>("EXPIRED");
  const [comment, setComment] = useState("");
  const [apHclause, setApHclause] = useState("APH 1.8f");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    if (!open) {
      return;
    }
    setReasonCode("EXPIRED");
    setComment("");
    setApHclause("APH 1.8f");
    setSubmitting(false);
    setError(null);
    setFieldErrors({});
  }, [open, document?.id]);

  if (!document) {
    return null;
  }

  const submit = async () => {
    if (submitting) {
      return;
    }
    if (!comment.trim()) {
      setFieldErrors({ comment: "Explain the rejection so the institution can comply." });
      return;
    }
    setFieldErrors({});
    setError(null);
    setSubmitting(true);
    try {
      const rejected = await rejectApplicationDocument(
        token,
        applicationId,
        document.id,
        { reasonCode, comment: comment.trim(), apHclause: apHclause.trim() || "APH 1.8f" },
      );
      onRejected(rejected);
      toast({
        title: "Document rejected",
        description:
          "The institution has been notified and a deficiency item was opened for the replacement.",
        variant: "info",
      });
      onOpenChange(false);
    } catch (rejectionError) {
      setError(
        rejectionError instanceof ApiError
          ? rejectionError.message
          : "The document could not be rejected.",
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(next) => !submitting && onOpenChange(next)}>
      <DialogContent aria-describedby={undefined}>
        <DialogHeader>
          <DialogTitle>Reject {document.label}</DialogTitle>
          <DialogDescription>
            Version {document.version ?? 1}. The institution is asked to re-upload this
            document and a deficiency item is opened (APH 1.8f, 2.4).
          </DialogDescription>
        </DialogHeader>

        <div className="mt-4 space-y-4">
          <Select
            label="Reason"
            options={REASON_OPTIONS}
            value={reasonCode}
            onValueChange={(value) => setReasonCode(value as DocumentRejectionReason)}
            disabled={submitting}
            required
            error={fieldErrors.reason_code}
            hint="Copied into the Deficiency Report so the institution knows what to fix."
          />
          <Textarea
            label="Comment for the institution"
            value={comment}
            onChange={(event) => setComment(event.target.value)}
            disabled={submitting}
            required
            rows={4}
            error={fieldErrors.comment}
            placeholder="For example: the fire certificate expired on 31 December 2025; upload a current certificate."
          />
          <Input
            label="APH clause"
            value={apHclause}
            onChange={(event) => setApHclause(event.target.value)}
            disabled={submitting}
            hint="The handbook clause that authorises the rejection."
          />
          {error ? (
            <p className="rounded-input border border-breach bg-breach-soft p-3 text-13 text-breach-strong">
              {error}
            </p>
          ) : null}
        </div>

        <DialogFooter>
          <Button
            type="button"
            variant="quiet"
            onClick={() => onOpenChange(false)}
            disabled={submitting}
          >
            Cancel
          </Button>
          <Button type="button" onClick={() => void submit()} disabled={submitting}>
            {submitting ? (
              <Loader2 aria-hidden="true" className="size-4 animate-spin" />
            ) : (
              <XCircle aria-hidden="true" className="size-4" />
            )}
            {submitting ? "Rejecting…" : "Reject document"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
