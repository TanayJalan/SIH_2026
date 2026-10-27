import { useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  Download,
  FileText,
  History,
  Loader2,
  RefreshCw,
  ShieldCheck,
  UploadCloud,
  XCircle,
} from "lucide-react";

import { useAuth } from "@/auth/AuthContext";
import DocumentStatusChip from "../documents/DocumentStatusChip";
import DocumentVersionDrawer from "../documents/DocumentVersionDrawer";
import RejectDocumentDialog, {
  type RejectTarget,
} from "../documents/RejectDocumentDialog";
import ReuploadDialog, { type ReuploadTarget } from "../documents/ReuploadDialog";
import { Button, Skeleton, useToast } from "../ui";
import {
  ApiError,
  API_BASE_URL,
  downloadApplicationDocument,
  getDocumentChecklist,
  listApplicationDocuments,
  verifyApplicationDocument,
  type ChecklistDocument,
  type DocumentRecord,
} from "@/lib/api";
import { formatBytes } from "@/lib/application";
import { formatDate, formatDateTime } from "@/lib/format";

const REVIEWER_ROLES = new Set(["SCRUTINY_COMMITTEE_MEMBER", "REGULATION_BUREAU_OFFICER"]);

interface DocumentRow {
  docType: string;
  label: string;
  mandatory: boolean;
  checklist: ChecklistDocument | undefined;
  versions: DocumentRecord[];
  latest: DocumentRecord | undefined;
}

function toReuploadTarget(row: DocumentRow): ReuploadTarget | null {
  if (!row.latest) {
    return null;
  }
  return {
    id: row.latest.id,
    docType: row.latest.doc_type,
    label: row.label,
    version: row.latest.version,
    rejectionReasonCode: row.latest.rejection_reason_code,
    rejectionComment: row.latest.rejection_comment,
    apHclause: row.latest.apH_clause,
    rejectedAt: row.latest.rejected_at,
    dueDate: row.latest.deficiency_due_date,
    maxReuploads: row.latest.max_reuploads,
    reuploadCount: row.latest.reupload_count,
  };
}

function toRejectTarget(row: DocumentRow): RejectTarget | null {
  if (!row.latest) {
    return null;
  }
  return {
    id: row.latest.id,
    label: row.label,
    docType: row.latest.doc_type,
    version: row.latest.version,
  };
}

export default function CaseDocuments({
  applicationId,
  token,
}: {
  applicationId: string;
  token: string;
}) {
  const { user } = useAuth();
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [onlyToRecheck, setOnlyToRecheck] = useState(false);
  const [selectedDocType, setSelectedDocType] = useState<string | null>(null);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);
  const [verifyingId, setVerifyingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reuploadTarget, setReuploadTarget] = useState<ReuploadTarget | null>(null);
  const [rejectTarget, setRejectTarget] = useState<RejectTarget | null>(null);
  const [versionTarget, setVersionTarget] = useState<{ id: string; label: string } | null>(
    null,
  );

  const isReviewer = Boolean(user && REVIEWER_ROLES.has(user.role));

  const checklistQuery = useQuery({
    queryKey: ["document-checklist", applicationId],
    queryFn: () => getDocumentChecklist(token, applicationId),
    enabled: Boolean(token && applicationId),
    retry: false,
  });

  const recordsQuery = useQuery({
    queryKey: ["document-records", applicationId, "all"],
    queryFn: () => listApplicationDocuments(token, applicationId),
    enabled: Boolean(token && applicationId),
    retry: false,
  });

  const recheckQuery = useQuery({
    queryKey: ["document-records", applicationId, "recheck"],
    queryFn: () => listApplicationDocuments(token, applicationId, { onlyToRecheck: true }),
    enabled: Boolean(token && applicationId && isReviewer && onlyToRecheck),
    retry: false,
  });

  const checklist = checklistQuery.data;
  const records = useMemo(
    () =>
      onlyToRecheck ? (recheckQuery.data ?? []) : (recordsQuery.data ?? []),
    [onlyToRecheck, recheckQuery.data, recordsQuery.data],
  );

  const rows = useMemo<DocumentRow[]>(() => {
    const labels = new Map<string, ChecklistDocument>();
    for (const document of checklist?.documents ?? []) {
      labels.set(document.doc_type, document);
    }
    const grouped = new Map<string, DocumentRecord[]>();
    for (const record of records) {
      const bucket = grouped.get(record.doc_type) ?? [];
      bucket.push(record);
      grouped.set(record.doc_type, bucket);
    }
    const docTypes = onlyToRecheck
      ? new Set<string>(grouped.keys())
      : new Set<string>([...labels.keys(), ...grouped.keys()]);
    return [...docTypes].map((docType) => {
      const versions = (grouped.get(docType) ?? [])
        .slice()
        .sort((a, b) => b.version - a.version);
      const checklistRow = labels.get(docType);
      return {
        docType,
        label:
          checklistRow?.label ??
          docType.replaceAll("_", " ").toLowerCase().replace(/^./, (c) => c.toUpperCase()),
        mandatory: checklistRow?.mandatory ?? false,
        checklist: checklistRow,
        versions,
        latest: versions[0],
      };
    });
  }, [checklist, records, onlyToRecheck]);

  // The reviewer's waiting state uses the unfiltered list, so the banner keeps
  // reporting every outstanding replacement while a filter is active.
  const waiting = useMemo(() => {
    const all = recordsQuery.data ?? [];
    const latest = all.filter((record) => record.is_latest);
    const rejected = latest.filter(
      (record) =>
        record.verification_status === "REJECTED" && record.superseded_by === null,
    );
    const due = rejected
      .map((record) => record.deficiency_due_date)
      .filter((value): value is string => Boolean(value))
      .sort()[0];
    return { count: rejected.length, due: due ?? null };
  }, [recordsQuery.data]);

  const applyResult = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ["document-checklist", applicationId] }),
      queryClient.invalidateQueries({ queryKey: ["document-records", applicationId] }),
      queryClient.invalidateQueries({ queryKey: ["document-versions", applicationId] }),
      queryClient.invalidateQueries({ queryKey: ["deficiencies", applicationId] }),
      queryClient.invalidateQueries({ queryKey: ["application", applicationId] }),
      queryClient.invalidateQueries({ queryKey: ["workflow-timeline", applicationId] }),
    ]);
  };

  const handleDownload = async (document: DocumentRecord | ChecklistDocument) => {
    setDownloadingId(
      "id" in document && document.id ? document.id : document.doc_type,
    );
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

  const handleVerify = async (document: DocumentRecord) => {
    setVerifyingId(document.id);
    setError(null);
    try {
      await verifyApplicationDocument(token, applicationId, document.id, {
        comment: "Replacement checked against the communicated deficiency.",
        apHclause: "APH 1.8g",
      });
      await applyResult();
      toast({
        title: "Document verified",
        description: `${document.doc_type.replaceAll("_", " ").toLowerCase()} version ${document.version} meets the communicated deficiency (APH 1.8g).`,
        variant: "success",
      });
    } catch (verifyError) {
      setError(
        verifyError instanceof ApiError
          ? verifyError.message
          : "The document could not be verified.",
      );
    } finally {
      setVerifyingId(null);
    }
  };

  const selected = rows.find((row) => row.docType === selectedDocType);
  const loading = checklistQuery.isPending || recordsQuery.isPending;
  const queryError = checklistQuery.isError
    ? checklistQuery.error
    : recordsQuery.isError
      ? recordsQuery.error
      : onlyToRecheck && recheckQuery.isError
        ? recheckQuery.error
        : null;

  return (
    <section className="rounded-panel border border-line bg-surface p-5 sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="font-serif text-20 font-semibold text-ink">Documents</h2>
          <p className="mt-1 text-13 text-ink-500">
            Every required document, its review status and the full version trail.
            A reviewer can reject a file and the institution replaces exactly that
            document (APH 1.8f, 1.8g, 2.4).
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          {isReviewer ? (
            <label className="flex items-center gap-2 text-12 text-ink-700">
              <input
                type="checkbox"
                className="size-4 rounded border-line"
                checked={onlyToRecheck}
                onChange={(event) => setOnlyToRecheck(event.target.checked)}
              />
              Only documents to re-check
            </label>
          ) : null}
          <Button
            variant="quiet"
            size="sm"
            onClick={() => {
              void checklistQuery.refetch();
              void recordsQuery.refetch();
              if (onlyToRecheck) void recheckQuery.refetch();
            }}
            disabled={checklistQuery.isFetching || recordsQuery.isFetching}
          >
            <RefreshCw
              aria-hidden="true"
              className={
                checklistQuery.isFetching || recordsQuery.isFetching
                  ? "size-4 animate-spin"
                  : "size-4"
              }
            />
            Refresh
          </Button>
        </div>
      </div>

      {isReviewer && waiting.count > 0 ? (
        <p className="mt-3 rounded-input border border-watch bg-watch-soft p-3 text-13 text-watch-strong">
          Waiting for the institution to re-upload {waiting.count}{" "}
          {waiting.count === 1 ? "document" : "documents"}
          {waiting.due ? ` (due ${formatDate(waiting.due)}` : " ("}
          {waiting.due ? ", APH 1.8f / 2.4)" : "APH 1.8f / 2.4)"}
        </p>
      ) : null}

      {error ? (
        <p className="mt-3 rounded-input border border-breach bg-breach-soft p-3 text-13 text-breach-strong">
          {error}
        </p>
      ) : null}

      {loading ? (
        <div className="mt-5 space-y-3" role="status">
          {[0, 1, 2].map((item) => (
            <Skeleton key={item} className="h-16 w-full" />
          ))}
          <span className="sr-only">Loading documents</span>
        </div>
      ) : queryError ? (
        <p className="mt-4 rounded-input border border-breach bg-breach-soft p-3 text-13 text-breach-strong">
          {queryError instanceof ApiError
            ? queryError.message
            : "The document checklist could not be loaded."}
        </p>
      ) : rows.length === 0 ? (
        <p className="mt-4 rounded-input border border-line bg-paper p-4 text-13 text-ink-700">
          {onlyToRecheck
            ? "No documents are waiting to be re-checked."
            : "No document rules are configured for this application type."}
        </p>
      ) : selected ? (
        <DocumentSplitView
          row={selected}
          onBack={() => setSelectedDocType(null)}
          onDownload={() => void handleDownload(selected.latest ?? selected.checklist!)}
          downloading={
            downloadingId === (selected.latest?.id ?? selected.docType)
          }
          token={token}
        />
      ) : (
        <ul className="mt-4 space-y-3">
          {rows.map((row) => (
            <DocumentRowCard
              key={row.docType}
              row={row}
              onOpen={() => setSelectedDocType(row.docType)}
              onDownload={() =>
                row.latest
                  ? void handleDownload(row.latest)
                  : row.checklist && void handleDownload(row.checklist)
              }
              downloading={downloadingId === (row.latest?.id ?? row.docType)}
              onVersionHistory={() =>
                row.latest &&
                setVersionTarget({ id: row.latest.id, label: row.label })
              }
              onReupload={() => setReuploadTarget(toReuploadTarget(row))}
              onReject={() => setRejectTarget(toRejectTarget(row))}
              onVerify={() => row.latest && void handleVerify(row.latest)}
              verifying={verifyingId === row.latest?.id}
            />
          ))}
        </ul>
      )}

      <ReuploadDialog
        open={Boolean(reuploadTarget)}
        onOpenChange={(open) => !open && setReuploadTarget(null)}
        token={token}
        applicationId={applicationId}
        document={reuploadTarget}
        onReuploaded={() => {
          setReuploadTarget(null);
          void applyResult();
        }}
      />
      <RejectDocumentDialog
        open={Boolean(rejectTarget)}
        onOpenChange={(open) => !open && setRejectTarget(null)}
        token={token}
        applicationId={applicationId}
        document={rejectTarget}
        onRejected={() => {
          setRejectTarget(null);
          void applyResult();
        }}
      />
      <DocumentVersionDrawer
        open={Boolean(versionTarget)}
        onOpenChange={(open) => !open && setVersionTarget(null)}
        token={token}
        applicationId={applicationId}
        documentId={versionTarget?.id ?? null}
        label={versionTarget?.label ?? ""}
      />
    </section>
  );
}

function DocumentRowCard({
  row,
  onOpen,
  onDownload,
  downloading,
  onVersionHistory,
  onReupload,
  onReject,
  onVerify,
  verifying,
}: {
  row: DocumentRow;
  onOpen: () => void;
  onDownload: () => void;
  downloading: boolean;
  onVersionHistory: () => void;
  onReupload: () => void;
  onReject: () => void;
  onVerify: () => void;
  verifying: boolean;
}) {
  const latest = row.latest;
  const actions = latest?.allowed_actions ?? [];
  const canReupload = actions.includes("reupload");
  const canReject = actions.includes("reject");
  const canVerify = actions.includes("verify");
  const showBlockReason =
    latest !== undefined &&
    !canReupload &&
    latest.replacement_block_reason !== null &&
    (latest.verification_status === "REJECTED" ||
      latest.verification_status === "FLAGGED" ||
      latest.verification_status === "VERIFIED");
  const resubmitted = latest !== undefined && latest.version > 1;

  return (
    <li className="rounded-input border border-line bg-surface p-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div className="flex min-w-0 gap-3">
          <span className="mt-0.5 flex size-9 shrink-0 items-center justify-center rounded-input bg-paper text-ink-500">
            <FileText aria-hidden="true" className="size-4" />
          </span>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <button
                type="button"
                onClick={onOpen}
                className="text-left text-13 font-medium text-ink hover:underline"
              >
                {row.label}
              </button>
              <span className="rounded-pill bg-paper px-2 py-0.5 text-11 text-ink-500">
                {row.mandatory ? "Mandatory" : "Optional"}
              </span>
              {resubmitted ? (
                <span className="rounded-pill bg-info-soft px-2 py-0.5 text-11 font-medium text-info-strong">
                  Resubmitted (v{latest?.version})
                </span>
              ) : null}
            </div>
            {latest ? (
              <p className="mt-1 break-all text-12 text-ink-500">
                {latest.filename} · {formatBytes(latest.size_bytes)} · version{" "}
                {latest.version} · uploaded {formatDateTime(latest.created_at)}
              </p>
            ) : (
              <p className="mt-1 text-12 text-ink-500">Not uploaded</p>
            )}
            {latest ? (
              <DocumentStatusChip
                status={latest.verification_status}
                rejectionReasonCode={latest.rejection_reason_code}
                rejectionComment={latest.rejection_comment}
                apHclause={latest.apH_clause}
                rejectedAt={latest.rejected_at}
                dueDate={latest.deficiency_due_date}
                className="mt-2"
              />
            ) : null}
            {latest?.verification_status === "FLAGGED" && latest.verification_reason ? (
              <p className="mt-1 text-12 text-ink-700">{latest.verification_reason}</p>
            ) : null}
            {showBlockReason ? (
              <p className="mt-2 text-12 text-ink-500">{latest?.replacement_block_reason}</p>
            ) : null}
          </div>
        </div>

        <div className="flex shrink-0 flex-wrap items-center gap-2 lg:justify-end">
          {canReject ? (
            <Button variant="secondary" size="sm" onClick={onReject}>
              <XCircle aria-hidden="true" className="size-4" />
              Reject
            </Button>
          ) : null}
          {canVerify && latest ? (
            <Button
              variant="primary"
              size="sm"
              onClick={onVerify}
              disabled={verifying}
            >
              {verifying ? (
                <Loader2 aria-hidden="true" className="size-4 animate-spin" />
              ) : (
                <ShieldCheck aria-hidden="true" className="size-4" />
              )}
              Verify
            </Button>
          ) : null}
          {canReupload ? (
            <Button variant="primary" size="sm" onClick={onReupload}>
              <UploadCloud aria-hidden="true" className="size-4" />
              Re-upload
            </Button>
          ) : null}
          {latest ? (
            <Button
              variant="quiet"
              size="sm"
              onClick={onDownload}
              disabled={downloading}
            >
              {downloading ? (
                <Loader2 aria-hidden="true" className="size-4 animate-spin" />
              ) : (
                <Download aria-hidden="true" className="size-4" />
              )}
              Download
            </Button>
          ) : null}
          {latest ? (
            <Button variant="quiet" size="sm" onClick={onVersionHistory}>
              <History aria-hidden="true" className="size-4" />
              Versions ({row.versions.length})
            </Button>
          ) : null}
        </div>
      </div>
    </li>
  );
}

function DocumentSplitView({
  row,
  onBack,
  onDownload,
  downloading,
  token,
}: {
  row: DocumentRow;
  onBack: () => void;
  onDownload: () => void;
  downloading: boolean;
  token: string;
}) {
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const document = row.latest;
  const downloadUrl = document?.download_url ?? row.checklist?.download_url ?? null;
  const contentType =
    document?.content_type ?? row.checklist?.content_type ?? "application/pdf";

  useEffect(() => {
    let revoked: string | null = null;
    let cancelled = false;
    setPreviewUrl(null);
    setPreviewError(null);

    const loadPreview = async () => {
      if (!downloadUrl) {
        setPreviewError("The document file is not available for preview.");
        return;
      }
      try {
        const response = await fetch(
          downloadUrl.startsWith("http") ? downloadUrl : `${API_BASE_URL}${downloadUrl}`,
          { headers: { Authorization: `Bearer ${token}` } },
        );
        if (!response.ok) {
          if (!cancelled) {
            setPreviewError("The document could not be opened for preview.");
          }
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
  }, [downloadUrl, token]);

  return (
    <div className="mt-4">
      <Button variant="quiet" size="sm" onClick={onBack}>
        <ArrowLeft aria-hidden="true" className="size-4" />
        All documents
      </Button>

      <div className="mt-3 grid min-w-0 gap-4 lg:grid-cols-2">
        <div className="min-w-0 rounded-input border border-line bg-paper p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h3 className="text-13 font-semibold text-ink">{row.label}</h3>
            <Button
              variant="secondary"
              size="sm"
              onClick={onDownload}
              disabled={downloading}
            >
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
              type={contentType}
              className="mt-3 h-96 w-full rounded-input border border-line bg-surface"
              aria-label={`Preview of ${row.label}`}
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
            <div>File {document?.filename ?? row.checklist?.filename ?? "—"}</div>
            <div>
              {formatBytes(document?.size_bytes ?? row.checklist?.size_bytes)} ·
              version {document?.version ?? row.checklist?.version ?? "—"} ·
              uploaded{" "}
              {formatDateTime(document?.created_at ?? row.checklist?.uploaded_at)}
            </div>
          </dl>
        </div>

        <div className="min-w-0 rounded-input border border-line bg-surface p-4">
          <h3 className="text-13 font-semibold text-ink">Review trail</h3>
          {document ? (
            <div className="mt-3 space-y-3">
              <DocumentStatusChip
                status={document.verification_status}
                rejectionReasonCode={document.rejection_reason_code}
                rejectionComment={document.rejection_comment}
                apHclause={document.apH_clause}
                rejectedAt={document.rejected_at}
                dueDate={document.deficiency_due_date}
              />
              <dl className="space-y-2 text-12 text-ink-700">
                <div>
                  <dt className="font-medium text-ink-500">Uploaded by</dt>
                  <dd>{document.uploaded_by_name ?? "Institution user"}</dd>
                </div>
                <div>
                  <dt className="font-medium text-ink-500">Digital signature</dt>
                  <dd>
                    {document.signed_with_dsc
                      ? `Signed${document.signer_name ? ` by ${document.signer_name}` : ""} (APH 1.4.3)`
                      : "Not signed — this upload cannot satisfy APH 1.4.3"}
                  </dd>
                </div>
                <div>
                  <dt className="font-medium text-ink-500">Valid until</dt>
                  <dd>{document.valid_until ? formatDate(document.valid_until) : "—"}</dd>
                </div>
                {document.deficiency_status ? (
                  <div>
                    <dt className="font-medium text-ink-500">Linked deficiency</dt>
                    <dd>
                      {document.deficiency_status}
                      {document.deficiency_due_date
                        ? ` · due ${formatDate(document.deficiency_due_date)}`
                        : ""}
                    </dd>
                  </div>
                ) : null}
                {document.rejected_by_name ? (
                  <div>
                    <dt className="font-medium text-ink-500">Rejected by</dt>
                    <dd>{document.rejected_by_name}</dd>
                  </div>
                ) : null}
                <div>
                  <dt className="font-medium text-ink-500">Replacement limit</dt>
                  <dd>
                    {document.reupload_count} of {document.max_reuploads} used
                  </dd>
                </div>
              </dl>
              {document.warnings.length > 0 ? (
                <ul className="rounded-input border border-watch bg-watch-soft p-3 text-12 text-watch-strong">
                  {document.warnings.map((warning) => (
                    <li key={warning}>{warning}</li>
                  ))}
                </ul>
              ) : null}
            </div>
          ) : (
            <p className="mt-2 text-13 text-ink-500">This document has not been uploaded yet.</p>
          )}
        </div>
      </div>
    </div>
  );
}
