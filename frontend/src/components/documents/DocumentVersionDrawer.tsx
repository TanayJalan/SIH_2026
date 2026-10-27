import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Download, History, Loader2 } from "lucide-react";

import {
  Button,
  Drawer,
  DrawerContent,
  DrawerDescription,
  DrawerHeader,
  DrawerTitle,
  Skeleton,
} from "../ui";
import DocumentStatusChip from "./DocumentStatusChip";
import {
  ApiError,
  downloadApplicationDocument,
  listDocumentVersions,
  type DocumentRecord,
} from "@/lib/api";
import { formatBytes } from "@/lib/application";
import { formatDateTime } from "@/lib/format";

interface DocumentVersionDrawerProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  token: string;
  applicationId: string;
  documentId: string | null;
  label: string;
}

/**
 * Every version of one document, newest first.
 *
 * Earlier files stay downloadable after a replacement so Re-Scrutiny can compare
 * the rejected version with its replacement (APH 1.4.3, 1.8g).
 */
export default function DocumentVersionDrawer({
  open,
  onOpenChange,
  token,
  applicationId,
  documentId,
  label,
}: DocumentVersionDrawerProps) {
  const [downloadingId, setDownloadingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const versionsQuery = useQuery({
    queryKey: ["document-versions", applicationId, documentId],
    queryFn: () => listDocumentVersions(token, applicationId, documentId ?? ""),
    enabled: Boolean(open && token && applicationId && documentId),
    retry: false,
  });

  const handleDownload = async (version: DocumentRecord) => {
    setDownloadingId(version.id);
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
      setDownloadingId(null);
    }
  };

  return (
    <Drawer open={open} onOpenChange={onOpenChange}>
      <DrawerContent aria-describedby={undefined}>
        <DrawerHeader>
          <DrawerTitle className="flex items-center gap-2 text-18">
            <History aria-hidden="true" className="size-4 text-ink-500" />
            Version history
          </DrawerTitle>
          <DrawerDescription>{label}</DrawerDescription>
        </DrawerHeader>

        {error ? (
          <p className="mt-3 rounded-input border border-breach bg-breach-soft p-3 text-13 text-breach-strong">
            {error}
          </p>
        ) : null}

        <div className="mt-4">
          {versionsQuery.isPending ? (
            <div className="space-y-3" role="status">
              {[0, 1, 2].map((item) => (
                <Skeleton key={item} className="h-20 w-full" />
              ))}
              <span className="sr-only">Loading version history</span>
            </div>
          ) : versionsQuery.isError ? (
            <p className="rounded-input border border-breach bg-breach-soft p-3 text-13 text-breach-strong">
              {versionsQuery.error instanceof ApiError
                ? versionsQuery.error.message
                : "The version history could not be loaded."}
            </p>
          ) : (versionsQuery.data ?? []).length === 0 ? (
            <p className="text-13 text-ink-500">This document has no uploaded versions.</p>
          ) : (
            <ul className="divide-y divide-line rounded-input border border-line">
              {(versionsQuery.data ?? []).map((version) => (
                <li key={version.id} className="space-y-2 p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="flex flex-wrap items-center gap-1.5 text-13 font-medium text-ink">
                      Version {version.version}
                      {version.is_latest ? (
                        <span className="rounded-pill bg-ok-soft px-1.5 py-0.5 text-10 font-semibold uppercase tracking-wide text-ok-strong">
                          Latest
                        </span>
                      ) : version.superseded_by ? (
                        <span className="rounded-pill bg-paper px-1.5 py-0.5 text-10 font-semibold uppercase tracking-wide text-ink-500">
                          Superseded
                        </span>
                      ) : null}
                    </p>
                    <Button
                      variant="quiet"
                      size="sm"
                      onClick={() => void handleDownload(version)}
                      disabled={downloadingId === version.id}
                    >
                      {downloadingId === version.id ? (
                        <Loader2 aria-hidden="true" className="size-3.5 animate-spin" />
                      ) : (
                        <Download aria-hidden="true" className="size-3.5" />
                      )}
                      Download
                    </Button>
                  </div>
                  <p className="break-all text-12 text-ink-500">
                    {version.filename} · {formatBytes(version.size_bytes)}
                  </p>
                  <p className="text-12 text-ink-500">
                    Uploaded by {version.uploaded_by_name ?? "an institution user"} ·{" "}
                    {formatDateTime(version.created_at)}
                  </p>
                  <DocumentStatusChip
                    status={version.verification_status}
                    rejectionReasonCode={version.rejection_reason_code}
                    rejectionComment={version.rejection_comment}
                    apHclause={version.apH_clause}
                    rejectedAt={version.rejected_at}
                    dueDate={version.deficiency_due_date}
                    compact
                  />
                </li>
              ))}
            </ul>
          )}
        </div>
      </DrawerContent>
    </Drawer>
  );
}
