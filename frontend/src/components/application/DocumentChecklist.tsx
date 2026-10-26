import { useMemo, useRef, useState, type DragEvent } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronDown, Download, FileCheck2, FileUp, History, Loader2 } from "lucide-react";

import { Button, ProgressBar, useToast } from "@/components/ui";
import DocumentVerificationBadge from "@/components/application/DocumentVerificationBadge";
import {
  DOCUMENT_ACCEPT,
  MAX_DOCUMENT_BYTES,
  formatBytes,
} from "@/lib/application";
import {
  ApiError,
  downloadApplicationDocument,
  listApplicationDocuments,
  uploadApplicationDocument,
  type ChecklistDocument,
  type DocumentRecord,
  type DocumentVerificationStatus,
} from "@/lib/api";
import { formatDateTime } from "@/lib/format";
import { cn } from "@/lib/utils";

interface DocumentChecklistProps {
  applicationId: string;
  token: string;
  documents: ChecklistDocument[];
  disabled?: boolean;
  onUploaded: () => void;
}

interface VerificationSnapshot {
  status: DocumentVerificationStatus;
  reason: string | null;
}

const ALLOWED_TYPES = new Set(["application/pdf", "image/jpeg", "image/png"]);
const ALLOWED_EXTENSIONS = [".pdf", ".jpg", ".jpeg", ".png"];

function clientFileError(file: File): string | null {
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

function DocumentRow({
  applicationId,
  token,
  document,
  versions,
  disabled,
  signedWithDsc,
  onUploaded,
}: {
  applicationId: string;
  token: string;
  document: ChecklistDocument;
  versions: DocumentRecord[];
  disabled?: boolean;
  signedWithDsc: boolean;
  onUploaded: () => void;
}) {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const inputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [downloadingVersionId, setDownloadingVersionId] = useState<string | null>(null);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [lastVerification, setLastVerification] = useState<VerificationSnapshot | null>(null);

  const verificationStatus = lastVerification?.status ?? document.verification_status;
  const verificationReason = lastVerification?.reason ?? document.verification_reason;

  const handleFile = async (file: File | undefined) => {
    if (!file || disabled || uploading) {
      return;
    }
    const validationError = clientFileError(file);
    if (validationError) {
      setError(validationError);
      return;
    }

    setError(null);
    setUploading(true);
    setProgress(0);
    try {
      const uploaded = await uploadApplicationDocument(
        token,
        applicationId,
        document.doc_type,
        file,
        setProgress,
        signedWithDsc,
      );
      setLastVerification({
        status: uploaded.verification_status,
        reason: uploaded.verification_reason,
      });
      await queryClient.invalidateQueries({
        queryKey: ["document-versions", applicationId],
      });
      onUploaded();

      const verified = uploaded.verification_status === "VERIFIED";
      toast({
        title: verified
          ? document.uploaded
            ? "Document replaced and verified"
            : "Document uploaded and verified"
          : document.uploaded
            ? "Document replaced — review flagged"
            : "Document uploaded — review flagged",
        description: verified
          ? `${uploaded.filename} is version ${uploaded.version}. The AI check found the expected document reference.`
          : (uploaded.verification_reason ??
            "The automated check could not verify this file. Replace it if the copy is unclear."),
        variant: verified ? "success" : "info",
      });
    } catch (uploadError) {
      setError(
        uploadError instanceof ApiError
          ? uploadError.message
          : "The document could not be uploaded.",
      );
    } finally {
      setUploading(false);
      setProgress(0);
      setDragActive(false);
      if (inputRef.current) {
        inputRef.current.value = "";
      }
    }
  };

  const handleDownload = async () => {
    if (!document.document_id) {
      return;
    }
    setDownloading(true);
    setError(null);
    try {
      await downloadApplicationDocument(token, document);
    } catch (downloadError) {
      setError(
        downloadError instanceof ApiError
          ? downloadError.message
          : "The document could not be downloaded.",
      );
    } finally {
      setDownloading(false);
    }
  };

  const handleVersionDownload = async (version: DocumentRecord) => {
    setDownloadingVersionId(version.id);
    setError(null);
    try {
      await downloadApplicationDocument(token, version);
    } catch (downloadError) {
      setError(
        downloadError instanceof ApiError
          ? downloadError.message
          : "The document version could not be downloaded.",
      );
    } finally {
      setDownloadingVersionId(null);
    }
  };

  const handleDrop = (event: DragEvent<HTMLLIElement>) => {
    event.preventDefault();
    setDragActive(false);
    void handleFile(event.dataTransfer.files?.[0]);
  };

  const handleDragLeave = (event: DragEvent<HTMLLIElement>) => {
    if (event.currentTarget.contains(event.relatedTarget as Node | null)) {
      return;
    }
    setDragActive(false);
  };

  return (
    <li
      className={cn(
        "relative rounded-input border bg-surface p-4 transition-colors sm:p-5",
        dragActive ? "border-info bg-info-soft" : "border-line",
      )}
      onDragEnter={(event) => {
        event.preventDefault();
        if (!disabled && !uploading) {
          setDragActive(true);
        }
      }}
      onDragOver={(event) => {
        event.preventDefault();
        if (!disabled && !uploading) {
          setDragActive(true);
        }
      }}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      {dragActive ? (
        <div className="pointer-events-none absolute inset-1 z-10 flex items-center justify-center rounded-input border-2 border-dashed border-info bg-info-soft px-4 text-center text-12 font-medium text-info-strong">
          Drop to {document.uploaded ? "replace" : "upload"} {document.label.toLowerCase()}
        </div>
      ) : null}

      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex min-w-0 gap-3">
          <span
            className={cn(
              "mt-0.5 flex size-9 shrink-0 items-center justify-center rounded-input",
              document.uploaded ? "bg-ok-soft text-ok-strong" : "bg-paper text-ink-300",
            )}
          >
            <FileCheck2 aria-hidden="true" className="size-4" />
          </span>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <p className="text-14 font-medium text-ink">{document.label}</p>
              <span
                className={cn(
                  "rounded-pill px-2 py-0.5 text-11 font-medium",
                  document.mandatory
                    ? "bg-saffron-50 text-saffron-strong"
                    : "bg-paper text-ink-500",
                )}
              >
                {document.mandatory ? "Mandatory" : "Optional"}
              </span>
            </div>
            {document.uploaded ? (
              <p className="mt-1 break-all text-12 text-ink-500">
                {document.filename} · {formatBytes(document.size_bytes)} · version{" "}
                {document.version} · uploaded {formatDateTime(document.uploaded_at)}
              </p>
            ) : (
              <p className="mt-1 text-12 text-ink-500">
                Drag a PDF, JPG or PNG here, or choose a file. Maximum 10 MB.
              </p>
            )}
            {document.uploaded ? (
              <p
                className={cn(
                  "mt-1 text-12",
                  document.signed_with_dsc
                    ? "text-ok-strong"
                    : "text-breach-strong",
                )}
              >
                {document.signed_with_dsc
                  ? "Digitally signed (DSC) — APH 1.4.6 satisfied."
                  : "Not digitally signed — this upload is invalid under APH 1.4.6. Replace it with a DSC-signed file."}
              </p>
            ) : null}
            {uploading ? (
              <p className="mt-2 flex items-center gap-1.5 text-12 text-ink-500">
                <Loader2 aria-hidden="true" className="size-3.5 animate-spin" />
                Uploading version {(document.version ?? 0) + 1}…
              </p>
            ) : null}
            <DocumentVerificationBadge
              status={verificationStatus}
              reason={verificationReason}
              className="mt-2"
            />
            {uploading ? (
              <ProgressBar
                label="Uploading"
                value={progress}
                status="info"
                className="mt-3 max-w-sm"
              />
            ) : null}
            {error ? (
              <p className="mt-2 text-12 text-breach-strong" role="alert">
                {error}
              </p>
            ) : null}
          </div>
        </div>

        <div className="flex shrink-0 flex-wrap items-center gap-2 sm:justify-end">
          {document.uploaded && document.document_id ? (
            <Button
              variant="quiet"
              size="sm"
              onClick={() => void handleDownload()}
              disabled={downloading || uploading}
            >
              {downloading ? (
                <Loader2 aria-hidden="true" className="size-4 animate-spin" />
              ) : (
                <Download aria-hidden="true" className="size-4" />
              )}
              View
            </Button>
          ) : null}
          <input
            ref={inputRef}
            id={`document-file-${document.doc_type}`}
            type="file"
            accept={DOCUMENT_ACCEPT}
            className="hidden"
            aria-hidden="true"
            tabIndex={-1}
            disabled={disabled || uploading}
            onChange={(event) => void handleFile(event.target.files?.[0])}
          />
          <Button
            id={`document-upload-${document.doc_type}`}
            variant={document.uploaded ? "secondary" : "primary"}
            size="sm"
            onClick={() => inputRef.current?.click()}
            disabled={disabled || uploading}
          >
            {uploading ? (
              <Loader2 aria-hidden="true" className="size-4 animate-spin" />
            ) : (
              <FileUp aria-hidden="true" className="size-4" />
            )}
            {uploading ? "Uploading…" : document.uploaded ? "Replace" : "Upload"}
          </Button>
        </div>
      </div>

      {versions.length > 1 ? (
        <details className="group mt-4 rounded-input border border-line bg-paper">
          <summary className="flex cursor-pointer list-none items-center justify-between gap-2 px-3 py-2 text-12 font-medium text-ink-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focus [&::-webkit-details-marker]:hidden">
            <span className="flex items-center gap-1.5">
              <History aria-hidden="true" className="size-3.5 text-ink-500" />
              Version history ({versions.length})
            </span>
            <ChevronDown
              aria-hidden="true"
              className="size-3.5 text-ink-500 transition-transform group-open:rotate-180"
            />
          </summary>
          <ul className="divide-y divide-line border-t border-line px-3">
            {versions.map((version) => {
              const isLatest = version.id === document.document_id;
              return (
                <li
                  key={version.id}
                  className="flex flex-wrap items-center justify-between gap-2 py-2.5"
                >
                  <div className="min-w-0">
                    <p className="flex flex-wrap items-center gap-1.5 text-12 font-medium text-ink">
                      Version {version.version}
                      {isLatest ? (
                        <span className="rounded-pill bg-ok-soft px-1.5 py-0.5 text-10 font-semibold uppercase tracking-wide text-ok-strong">
                          Latest
                        </span>
                      ) : null}
                    </p>
                    <p className="mt-0.5 break-all text-11 text-ink-500">
                      {version.filename} · {formatBytes(version.size_bytes)} ·{" "}
                      {formatDateTime(version.created_at)}
                    </p>
                    <DocumentVerificationBadge
                      status={version.verification_status}
                      reason={version.verification_reason}
                      compact
                      className="mt-1"
                    />
                  </div>
                  <Button
                    variant="quiet"
                    size="sm"
                    onClick={() => void handleVersionDownload(version)}
                    disabled={downloadingVersionId === version.id}
                  >
                    {downloadingVersionId === version.id ? (
                      <Loader2 aria-hidden="true" className="size-3.5 animate-spin" />
                    ) : (
                      <Download aria-hidden="true" className="size-3.5" />
                    )}
                    Download
                  </Button>
                </li>
              );
            })}
          </ul>
        </details>
      ) : null}
    </li>
  );
}

export default function DocumentChecklist({
  applicationId,
  token,
  documents,
  disabled,
  onUploaded,
}: DocumentChecklistProps) {
  const [signedWithDsc, setSignedWithDsc] = useState(true);
  const versionsQuery = useQuery({
    queryKey: ["document-versions", applicationId],
    queryFn: () => listApplicationDocuments(token, applicationId),
    enabled: Boolean(token && applicationId),
    retry: false,
  });

  const versionsByType = useMemo(() => {
    const grouped: Record<string, DocumentRecord[]> = {};
    for (const version of versionsQuery.data ?? []) {
      (grouped[version.doc_type] ??= []).push(version);
    }
    return grouped;
  }, [versionsQuery.data]);

  if (documents.length === 0) {
    return (
      <div className="rounded-input border border-line bg-paper p-4 text-13 text-ink-700">
        No document rules are configured for this application type.
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="rounded-input border border-line bg-paper p-3">
        <label className="flex items-start gap-2 text-13 text-ink">
          <input
            type="checkbox"
            className="mt-0.5 size-4 rounded border-line"
            checked={signedWithDsc}
            disabled={disabled}
            onChange={(event) => setSignedWithDsc(event.target.checked)}
          />
          <span>
            <span className="font-medium">The file I am uploading is digitally signed (DSC).</span>
            <span className="mt-0.5 block text-12 leading-5 text-ink-500">
              APH 1.4.6 requires every uploaded document to be signed with a valid Digital
              Signature Certificate. An unsigned upload is stored as invalid and blocks final
              submission.
            </span>
          </span>
        </label>
      </div>
      <p className="text-12 leading-5 text-ink-500">
        Drag a file directly onto a document row, or use the upload button. Replacing a required
        document creates a new version and keeps the earlier files available.
      </p>
      <ul className="space-y-3">
        {documents.map((document) => (
          <DocumentRow
            key={document.doc_type}
            applicationId={applicationId}
            token={token}
            document={document}
            versions={versionsByType[document.doc_type] ?? []}
            disabled={disabled}
            signedWithDsc={signedWithDsc}
            onUploaded={onUploaded}
          />
        ))}
      </ul>
    </div>
  );
}
