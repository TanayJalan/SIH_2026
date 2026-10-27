import { useEffect, useId, useRef, useState, type DragEvent } from "react";
import { FileUp, Loader2, UploadCloud } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";

import {
  Button,
  DatePicker,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  Input,
  ProgressBar,
  useToast,
} from "../ui";
import DocumentStatusChip, { REJECTION_REASON_LABELS } from "./DocumentStatusChip";
import { DOCUMENT_ACCEPT, MAX_DOCUMENT_BYTES, formatBytes } from "@/lib/application";
import {
  ApiError,
  apiFieldErrors,
  reuploadApplicationDocument,
  type DocumentRecord,
  type DocumentRejectionReason,
} from "@/lib/api";
import { formatDate } from "@/lib/format";
import { cn } from "@/lib/utils";

const ALLOWED_TYPES = new Set(["application/pdf", "image/jpeg", "image/png"]);
const ALLOWED_EXTENSIONS = [".pdf", ".jpg", ".jpeg", ".png"];
const VALIDITY_FAMILIES = ["FIRE", "OCCUPANCY", "STRUCTURAL"];

/** Certificate families that must carry a validity date (APH Annexure-2.1). */
export function certificateRequiresValidity(docType: string): boolean {
  const upper = docType.toUpperCase();
  return VALIDITY_FAMILIES.some((family) => upper.includes(family));
}

function fileError(file: File): string | null {
  const extension = `.${file.name.split(".").pop()?.toLowerCase() ?? ""}`;
  if (!ALLOWED_TYPES.has(file.type) && !ALLOWED_EXTENSIONS.includes(extension)) {
    return "Choose a PDF, JPG or PNG file.";
  }
  if (file.size > MAX_DOCUMENT_BYTES) {
    return "The file must be 10 MB or smaller.";
  }
  if (file.size === 0) {
    return "The selected file is empty.";
  }
  return null;
}

export interface ReuploadTarget {
  id: string;
  docType: string;
  label: string;
  version: number | null;
  rejectionReasonCode?: DocumentRejectionReason | null;
  rejectionComment?: string | null;
  apHclause?: string | null;
  rejectedAt?: string | null;
  dueDate?: string | null;
  maxReuploads?: number;
  reuploadCount?: number;
}

interface ReuploadDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  token: string;
  applicationId: string;
  document: ReuploadTarget | null;
  onReuploaded: (document: DocumentRecord) => void;
}

/**
 * Replace a rejected or flagged document with version N+1.
 *
 * The dialog mirrors the server's strict contract: a DSC attestation, the
 * signer's name and, for certificates, a current validity date. Per-field
 * errors returned by the API are shown inline (APH 1.4.3, 1.8f, 2.4).
 */
export default function ReuploadDialog({
  open,
  onOpenChange,
  token,
  applicationId,
  document,
  onReuploaded,
}: ReuploadDialogProps) {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const inputRef = useRef<HTMLInputElement>(null);
  const fileInputId = useId();

  const [file, setFile] = useState<File | null>(null);
  const [signedWithDsc, setSignedWithDsc] = useState(false);
  const [signerName, setSignerName] = useState("");
  const [validUntil, setValidUntil] = useState("");
  const [progress, setProgress] = useState(0);
  const [uploading, setUploading] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    if (!open) {
      return;
    }
    setFile(null);
    setSignedWithDsc(false);
    setSignerName("");
    setValidUntil("");
    setProgress(0);
    setUploading(false);
    setDragActive(false);
    setErrors({});
  }, [open, document?.id]);

  if (!document) {
    return null;
  }

  const requiresValidity = certificateRequiresValidity(document.docType);
  const nextVersion = (document.version ?? 1) + 1;
  const reasonLabel = document.rejectionReasonCode
    ? (REJECTION_REASON_LABELS[document.rejectionReasonCode] ??
      document.rejectionReasonCode)
    : null;

  const chooseFile = (picked: File | undefined) => {
    if (!picked) {
      return;
    }
    const problem = fileError(picked);
    if (problem) {
      setErrors((current) => ({ ...current, file: problem }));
      return;
    }
    setFile(picked);
    setErrors((current) => {
      const next = { ...current };
      delete next.file;
      return next;
    });
  };

  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragActive(false);
    if (!uploading) {
      chooseFile(event.dataTransfer.files?.[0]);
    }
  };

  const submit = async () => {
    if (uploading) {
      return;
    }
    const nextErrors: Record<string, string> = {};
    if (!file) {
      nextErrors.file = "Choose the replacement file.";
    }
    if (!signedWithDsc) {
      nextErrors.signed_with_dsc =
        "Tick the DSC attestation. Every upload must be digitally signed (APH 1.4.3).";
    }
    if (!signerName.trim()) {
      nextErrors.signer_name =
        "Enter the name of the person who signed the document.";
    }
    if (requiresValidity) {
      if (!validUntil) {
        nextErrors.valid_until =
          "Enter the certificate's validity date (APH Annexure-2.1).";
      } else if (validUntil < new Date().toISOString().slice(0, 10)) {
        nextErrors.valid_until =
          "The certificate has already expired. Upload a current certificate (APH Annexure-2.1).";
      }
    }
    if (Object.keys(nextErrors).length > 0 || !file) {
      setErrors(nextErrors);
      return;
    }

    setErrors({});
    setUploading(true);
    setProgress(0);
    try {
      const uploaded = await reuploadApplicationDocument(
        token,
        applicationId,
        document.id,
        file,
        {
          signedWithDsc,
          signerName: signerName.trim(),
          validUntil: validUntil || null,
        },
        setProgress,
      );
      await queryClient.invalidateQueries({ queryKey: ["document-checklist", applicationId] });
      await queryClient.invalidateQueries({ queryKey: ["document-records", applicationId] });
      await queryClient.invalidateQueries({ queryKey: ["document-versions", applicationId] });
      await queryClient.invalidateQueries({ queryKey: ["deficiencies", applicationId] });
      onReuploaded(uploaded);
      toast({
        title: `Document re-uploaded (version ${uploaded.version})`,
        description:
          uploaded.warnings.length > 0
            ? uploaded.warnings.join(" ")
            : "The reviewer has been notified that a replacement is waiting for verification.",
        variant: "success",
      });
      onOpenChange(false);
    } catch (error) {
      const fieldErrors = apiFieldErrors(error);
      setErrors(
        Object.keys(fieldErrors).length > 0
          ? fieldErrors
          : {
              file:
                error instanceof ApiError
                  ? error.message
                  : "The document could not be re-uploaded.",
            },
      );
    } finally {
      setUploading(false);
      setProgress(0);
    }
  };

  return (
    <Dialog open={open} onOpenChange={(next) => !uploading && onOpenChange(next)}>
      <DialogContent className="max-w-xl" aria-describedby={undefined}>
        <DialogHeader>
          <DialogTitle>Re-upload {document.label}</DialogTitle>
          <DialogDescription>
            {reasonLabel
              ? `Rejected: ${reasonLabel}. `
              : "Replace this document. "}
            The new file becomes version {nextVersion}. Earlier versions stay
            available in the version history (APH 1.8f, 2.4).
          </DialogDescription>
        </DialogHeader>

        <div className="mt-4 space-y-4">
          {document.rejectionReasonCode || document.rejectionComment ? (
            <div className="rounded-input border border-breach bg-breach-soft p-3">
              <DocumentStatusChip
                status="REJECTED"
                rejectionReasonCode={document.rejectionReasonCode}
                rejectionComment={document.rejectionComment}
                apHclause={document.apHclause}
                rejectedAt={document.rejectedAt}
                dueDate={document.dueDate}
              />
              {document.dueDate ? (
                <p className="mt-2 text-12 text-breach-strong">
                  Re-upload by {formatDate(document.dueDate)} so the Scrutiny
                  Committee can verify it (APH 2.4).
                </p>
              ) : null}
            </div>
          ) : null}

          <div
            onDragEnter={(event) => {
              event.preventDefault();
              if (!uploading) setDragActive(true);
            }}
            onDragOver={(event) => {
              event.preventDefault();
              if (!uploading) setDragActive(true);
            }}
            onDragLeave={() => setDragActive(false)}
            onDrop={handleDrop}
            className={cn(
              "rounded-input border-2 border-dashed p-4 text-center transition-colors",
              dragActive ? "border-info bg-info-soft" : "border-line bg-paper",
              errors.file ? "border-breach" : "",
            )}
          >
            <UploadCloud aria-hidden="true" className="mx-auto size-6 text-ink-500" />
            <p className="mt-2 text-13 text-ink-700">
              {file
                ? `${file.name} · ${formatBytes(file.size)}`
                : "Drag the replacement file here, or choose a file."}
            </p>
            <p className="mt-0.5 text-11 text-ink-500">PDF, JPG or PNG · maximum 10 MB</p>
            <input
              ref={inputRef}
              id={fileInputId}
              type="file"
              accept={DOCUMENT_ACCEPT}
              className="hidden"
              disabled={uploading}
              onChange={(event) => chooseFile(event.target.files?.[0])}
            />
            <Button
              type="button"
              variant="secondary"
              size="sm"
              className="mt-2"
              onClick={() => inputRef.current?.click()}
              disabled={uploading}
            >
              <FileUp aria-hidden="true" className="size-4" />
              {file ? "Choose another file" : "Choose file"}
            </Button>
            {errors.file ? (
              <p className="mt-2 text-12 text-breach-strong" role="alert">
                {errors.file}
              </p>
            ) : null}
          </div>

          <label className="flex items-start gap-2 rounded-input border border-line bg-paper p-3 text-13 text-ink">
            <input
              type="checkbox"
              className="mt-0.5 size-4 rounded border-line"
              checked={signedWithDsc}
              disabled={uploading}
              onChange={(event) => setSignedWithDsc(event.target.checked)}
            />
            <span>
              <span className="font-medium">
                The file is digitally signed (DSC).
              </span>
              <span className="mt-0.5 block text-12 leading-5 text-ink-500">
                APH 1.4.3 requires every upload to be signed with a valid Digital
                Signature Certificate.
              </span>
            </span>
          </label>
          {errors.signed_with_dsc ? (
            <p className="-mt-2 text-12 text-breach-strong" role="alert">
              {errors.signed_with_dsc}
            </p>
          ) : null}

          <Input
            label="Signed by"
            value={signerName}
            onChange={(event) => setSignerName(event.target.value)}
            placeholder="Name on the digital signature"
            disabled={uploading}
            required
            error={errors.signer_name}
            hint="The person whose DSC signed this upload (APH 1.4.3)."
          />

          <DatePicker
            label={requiresValidity ? "Certificate valid until" : "Valid until (optional)"}
            value={validUntil}
            onChange={(event) => setValidUntil(event.target.value)}
            disabled={uploading}
            required={requiresValidity}
            error={errors.valid_until}
            hint={
              requiresValidity
                ? "Fire, occupancy and structural certificates must still be current (APH Annexure-2.1)."
                : "Leave blank for documents without an expiry date."
            }
          />

          {uploading ? (
            <ProgressBar label={`Uploading version ${nextVersion}`} value={progress} status="info" />
          ) : null}
        </div>

        <DialogFooter>
          <Button
            type="button"
            variant="quiet"
            onClick={() => onOpenChange(false)}
            disabled={uploading}
          >
            Cancel
          </Button>
          <Button type="button" onClick={() => void submit()} disabled={uploading}>
            {uploading ? (
              <Loader2 aria-hidden="true" className="size-4 animate-spin" />
            ) : (
              <FileUp aria-hidden="true" className="size-4" />
            )}
            {uploading ? "Uploading…" : `Re-upload as version ${nextVersion}`}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
