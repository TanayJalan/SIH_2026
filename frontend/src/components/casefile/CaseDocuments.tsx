import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Download, FileText, Loader2, RefreshCw } from "lucide-react";

import DocumentVerificationBadge from "../application/DocumentVerificationBadge";
import { Button, Skeleton, StatusPill } from "../ui";
import {
  ApiError,
  downloadApplicationDocument,
  getDocumentChecklist,
  type ChecklistDocument,
  type DocumentVerificationStatus,
} from "@/lib/api";
import { formatBytes } from "@/lib/application";
import { formatDateTime, humanizeEnum } from "@/lib/format";

const STATUS_TONES: Record<DocumentVerificationStatus, "compliant" | "breach" | "watch" | "neutral"> = {
  VERIFIED: "compliant",
  FLAGGED: "breach",
  PENDING: "neutral",
  REJECTED: "watch",
};

/** One deterministic upload check, as stored on the document. */
function verificationChecks(document: ChecklistDocument) {
  if (!document.uploaded) {
    return [];
  }
  const checks: { label: string; passed: boolean | null; reason: string }[] = [
    {
      label: "Upload received",
      passed: true,
      reason: `${document.filename ?? "File"} · ${formatBytes(document.size_bytes)} · version ${document.version}`,
    },
    {
      label: document.label,
      passed:
        document.verification_status === "VERIFIED" ||
        document.verification_status === "PENDING"
          ? document.verification_status === "VERIFIED"
          : false,
      reason:
        document.verification_status === "PENDING"
          ? "The automated verification has not run for this upload yet."
          : (document.verification_reason ??
            humanizeEnum(document.verification_status ?? "PENDING")),
    },
  ];
  return checks;
}

export default function CaseDocuments({
  applicationId,
  token,
}: {
  applicationId: string;
  token: string;
}) {
  const [selectedDocType, setSelectedDocType] = useState<string | null>(null);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const checklistQuery = useQuery({
    queryKey: ["document-checklist", applicationId],
    queryFn: () => getDocumentChecklist(token, applicationId),
    enabled: Boolean(token && applicationId),
    retry: false,
  });

  const checklist = checklistQuery.data;
  const selected = checklist?.documents.find(
    (document) => document.doc_type === selectedDocType,
  );

  const handleDownload = async (document: ChecklistDocument) => {
    setDownloadingId(document.doc_type);
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
      setDownloadingId(null);
    }
  };

  return (
    <section className="rounded-panel border border-line bg-surface p-5 sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="font-serif text-20 font-semibold text-ink">Documents</h2>
          <p className="mt-1 text-13 text-ink-500">
            Uploaded evidence and the automated verification result for each
            required document. Select a document to open the verification view.
          </p>
        </div>
        <Button
          variant="quiet"
          size="sm"
          onClick={() => void checklistQuery.refetch()}
          disabled={checklistQuery.isFetching}
        >
          <RefreshCw
            aria-hidden="true"
            className={checklistQuery.isFetching ? "size-4 animate-spin" : "size-4"}
          />
          Refresh
        </Button>
      </div>

      {error ? (
        <p className="mt-3 rounded-input border border-breach bg-breach-soft p-3 text-13 text-breach-strong">
          {error}
        </p>
      ) : null}

      {checklistQuery.isPending ? (
        <div className="mt-5 space-y-3" role="status">
          {[0, 1, 2].map((item) => (
            <Skeleton key={item} className="h-16 w-full" />
          ))}
          <span className="sr-only">Loading documents</span>
        </div>
      ) : checklistQuery.isError ? (
        <p className="mt-4 rounded-input border border-breach bg-breach-soft p-3 text-13 text-breach-strong">
          {checklistQuery.error instanceof ApiError
            ? checklistQuery.error.message
            : "The document checklist could not be loaded."}
        </p>
      ) : !checklist || checklist.documents.length === 0 ? (
        <p className="mt-4 rounded-input border border-line bg-paper p-4 text-13 text-ink-700">
          No document rules are configured for this application type.
        </p>
      ) : selected ? (
        <DocumentSplitView
          document={selected}
          onBack={() => setSelectedDocType(null)}
          onDownload={() => void handleDownload(selected)}
          downloading={downloadingId === selected.doc_type}
          token={token}
        />
      ) : (
        <ul className="mt-4 divide-y divide-line rounded-input border border-line">
          {checklist.documents.map((document) => (
            <li key={document.doc_type}>
              <button
                type="button"
                className="flex w-full flex-col gap-3 p-4 text-left sm:flex-row sm:items-start sm:justify-between hover:bg-paper"
                onClick={() => setSelectedDocType(document.doc_type)}
              >
                <div className="flex min-w-0 gap-3">
                  <span className="mt-0.5 flex size-9 shrink-0 items-center justify-center rounded-input bg-paper text-ink-500">
                    <FileText aria-hidden="true" className="size-4" />
                  </span>
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="text-13 font-medium text-ink">
                        {document.label}
                      </p>
                      <span className="rounded-pill bg-paper px-2 py-0.5 text-11 text-ink-500">
                        {document.mandatory ? "Mandatory" : "Optional"}
                      </span>
                    </div>
                    {document.uploaded ? (
                      <p className="mt-1 break-all text-12 text-ink-500">
                        {document.filename} · {formatBytes(document.size_bytes)} ·
                        version {document.version} · uploaded{" "}
                        {formatDateTime(document.uploaded_at)}
                      </p>
                    ) : (
                      <p className="mt-1 text-12 text-ink-500">Not uploaded</p>
                    )}
                    <DocumentVerificationBadge
                      status={document.verification_status}
                      reason={document.verification_reason}
                      className="mt-2"
                    />
                  </div>
                </div>
                {document.uploaded && document.document_id ? (
                  <span
                    role="button"
                    tabIndex={0}
                    className="inline-flex items-center gap-2 text-13 text-info-strong"
                    onClick={(event) => {
                      event.stopPropagation();
                      void handleDownload(document);
                    }}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" || event.key === " ") {
                        event.stopPropagation();
                        void handleDownload(document);
                      }
                    }}
                  >
                    {downloadingId === document.doc_type ? (
                      <Loader2
                        aria-hidden="true"
                        className="size-4 animate-spin"
                      />
                    ) : (
                      <Download aria-hidden="true" className="size-4" />
                    )}
                    Download
                  </span>
                ) : null}
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function DocumentSplitView({
  document,
  onBack,
  onDownload,
  downloading,
  token,
}: {
  document: ChecklistDocument;
  onBack: () => void;
  onDownload: () => void;
  downloading: boolean;
  token: string;
}) {
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);

  useEffect(() => {
    let revoked: string | null = null;
    let cancelled = false;
    setPreviewUrl(null);
    setPreviewError(null);

    const loadPreview = async () => {
      if (!document.download_url) {
        setPreviewError("The document file is not available for preview.");
        return;
      }
      try {
        const response = await fetch(document.download_url, {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!response.ok) {
          setPreviewError("The document could not be opened for preview.");
          return;
        }
        const blob = await response.blob();
        if (cancelled) {
          return;
        }
        revoked = window.URL.createObjectURL(blob);
        setPreviewUrl(revoked);
      } catch {
        if (!cancelled) {
          setPreviewError("The document could not be opened for preview.");
        }
      }
    };

    void loadPreview();
    return () => {
      cancelled = true;
      if (revoked) {
        window.URL.revokeObjectURL(revoked);
      }
    };
  }, [document.download_url, token]);

  const checks = verificationChecks(document);

  return (
    <div className="mt-4">
      <Button variant="quiet" size="sm" onClick={onBack}>
        <ArrowLeft aria-hidden="true" className="size-4" />
        All documents
      </Button>

      <div className="mt-3 grid min-w-0 gap-4 lg:grid-cols-2">
        <div className="min-w-0 rounded-input border border-line bg-paper p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 className="text-13 font-semibold text-ink">{document.label}</h3>
            <Button variant="secondary" size="sm" onClick={onDownload} disabled={downloading}>
              {downloading ? (
                <Loader2 aria-hidden="true" className="size-4 animate-spin" />
              ) : (
                <Download aria-hidden="true" className="size-4" />
              )}
              Download
            </Button>
          </div>
          {previewUrl ? (
            <object
              data={previewUrl}
              type={document.content_type ?? "application/pdf"}
              className="mt-3 h-96 w-full rounded-input border border-line bg-surface"
              aria-label={`Preview of ${document.label}`}
            >
              <p className="p-4 text-13 text-ink-700">
                This file cannot be previewed inline. Use Download to open it.
              </p>
            </object>
          ) : (
            <p className="mt-3 rounded-input border border-line bg-surface p-4 text-13 text-ink-500">
              {previewError ?? "Loading preview…"}
            </p>
          )}
          <dl className="mt-3 space-y-1 text-12 text-ink-500">
            <div>File {document.filename ?? "—"}</div>
            <div>
              {formatBytes(document.size_bytes)} · version {document.version} ·
              uploaded {formatDateTime(document.uploaded_at)}
            </div>
          </dl>
        </div>

        <div className="min-w-0 rounded-input border border-line bg-surface p-4">
          <div className="flex items-center justify-between gap-2">
            <h3 className="text-13 font-semibold text-ink">AI verification</h3>
            {document.verification_status ? (
              <StatusPill status={STATUS_TONES[document.verification_status]}>
                {humanizeEnum(document.verification_status)}
              </StatusPill>
            ) : null}
          </div>
          <ul className="mt-3 space-y-3">
            {checks.map((check) => (
              <li
                key={check.label}
                className="rounded-input border border-line bg-paper p-3"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <StatusPill
                    status={
                      check.passed === null
                        ? "neutral"
                        : check.passed
                          ? "compliant"
                          : "breach"
                    }
                  >
                    {check.passed === null
                      ? "Not assessed"
                      : check.passed
                        ? "Pass"
                        : "Flag"}
                  </StatusPill>
                  <span className="text-13 font-medium text-ink">
                    {check.label}
                  </span>
                </div>
                <p className="mt-1 text-12 leading-5 text-ink-700">
                  {check.reason}
                </p>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}
