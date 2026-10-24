import { useState, type FormEvent } from "react";
import { useQuery } from "@tanstack/react-query";
import { RefreshCw } from "lucide-react";

import { useAuth } from "../auth/AuthContext";
import PageHeader from "../components/PageHeader";
import {
  Button,
  EmptyState,
  Skeleton,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "../components/ui";
import { ApiError, getAuditLogs, type AuditLogRecord } from "../lib/api";
import { formatDateTime, shortId } from "../lib/format";
import { ROLE_LABELS, ROLE_SCOPE_DESCRIPTIONS } from "../lib/roles";

interface AuditFilters {
  entityType: string;
  entityId: string;
  actorId: string;
  startDate: string;
  endDate: string;
}

const EMPTY_FILTERS: AuditFilters = {
  entityType: "",
  entityId: "",
  actorId: "",
  startDate: "",
  endDate: "",
};

const inputClass =
  "mt-1.5 block h-10 w-full rounded-input border border-line bg-surface px-3 text-14 text-ink outline-none transition-colors placeholder:text-ink-500 focus-visible:border-focus focus-visible:ring-2 focus-visible:ring-focus";

const labelClass = "text-13 font-medium text-ink-700";

const PAGE_SIZE = 15;

function ActionChip({ action }: { action: string }) {
  return (
    <span className="inline-flex rounded-input bg-paper px-2 py-1 font-mono text-12 font-medium text-ink-700">
      {action}
    </span>
  );
}

function Actor({ record }: { record: AuditLogRecord }) {
  if (!record.actor) {
    return (
      <>
        <p className="text-13 font-medium text-ink-700">System</p>
        <p className="mt-0.5 text-12 text-ink-500">No actor</p>
      </>
    );
  }
  return (
    <>
      <p className="text-13 font-medium text-ink">{record.actor.name}</p>
      <p className="mt-0.5 truncate text-12 text-ink-500">{record.actor.email}</p>
      <p className="mt-0.5 text-12 text-ink-500">{ROLE_LABELS[record.actor.role]}</p>
    </>
  );
}

function Snapshots({ record }: { record: AuditLogRecord }) {
  if (!record.before && !record.after) {
    return <span className="text-12 text-ink-500">No snapshots</span>;
  }
  return (
    <details>
      <summary className="cursor-pointer text-12 font-medium text-ink-700 underline-offset-4 hover:text-ink hover:underline">
        View JSON
      </summary>
      <div className="mt-2 space-y-2">
        {record.before ? (
          <div>
            <p className="text-12 font-medium text-ink-500">Before</p>
            <pre className="mt-1 max-w-md overflow-x-auto rounded-input bg-ink p-2 text-12 leading-4 text-surface">
              {JSON.stringify(record.before, null, 2)}
            </pre>
          </div>
        ) : null}
        {record.after ? (
          <div>
            <p className="text-12 font-medium text-ink-500">After</p>
            <pre className="mt-1 max-w-md overflow-x-auto rounded-input bg-ink p-2 text-12 leading-4 text-surface">
              {JSON.stringify(record.after, null, 2)}
            </pre>
          </div>
        ) : null}
      </div>
    </details>
  );
}

function MobileAuditCard({ record }: { record: AuditLogRecord }) {
  return (
    <li className="px-4 py-4 sm:px-5">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <span className="text-12 text-ink-500">{formatDateTime(record.created_at)}</span>
        <ActionChip action={record.action} />
      </div>
      <div className="mt-3">
        <Actor record={record} />
      </div>
      <dl className="mt-3 grid grid-cols-2 gap-3 border-t border-line pt-3 text-12">
        <div>
          <dt className="text-ink-500">Entity</dt>
          <dd className="mt-0.5 text-ink">{record.entity_type}</dd>
        </div>
        <div>
          <dt className="text-ink-500">Entity ID</dt>
          <dd className="mt-0.5 font-mono text-ink">{shortId(record.entity_id)}</dd>
        </div>
        <div>
          <dt className="text-ink-500">Source IP</dt>
          <dd className="mt-0.5 font-mono text-ink">{record.ip ?? "—"}</dd>
        </div>
        <div>
          <dt className="text-ink-500">Record ID</dt>
          <dd className="mt-0.5 font-mono text-ink">{shortId(record.id)}</dd>
        </div>
      </dl>
      <div className="mt-3">
        <Snapshots record={record} />
      </div>
    </li>
  );
}

export default function AuditLogsPage() {
  const { user, token } = useAuth();
  const [draftFilters, setDraftFilters] = useState<AuditFilters>(EMPTY_FILTERS);
  const [filters, setFilters] = useState<AuditFilters>(EMPTY_FILTERS);
  const [page, setPage] = useState(1);

  const auditQuery = useQuery({
    queryKey: ["audit-logs", filters, page],
    queryFn: () =>
      getAuditLogs(token ?? "", {
        page,
        pageSize: PAGE_SIZE,
        entityType: filters.entityType,
        entityId: filters.entityId,
        actorId: filters.actorId,
        startDate: filters.startDate,
        endDate: filters.endDate,
      }),
    enabled: Boolean(token),
  });

  if (!user) {
    return null;
  }

  const records = auditQuery.data?.items ?? [];
  const firstRow =
    auditQuery.data && auditQuery.data.total > 0
      ? (auditQuery.data.page - 1) * auditQuery.data.page_size + 1
      : 0;
  const lastRow = auditQuery.data
    ? Math.min(auditQuery.data.page * auditQuery.data.page_size, auditQuery.data.total)
    : 0;
  const hasFilters = Object.values(filters).some(Boolean);

  const updateDraft = (field: keyof AuditFilters, value: string) => {
    setDraftFilters((current) => ({ ...current, [field]: value }));
  };

  const handleApply = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setFilters({ ...draftFilters });
    setPage(1);
  };

  const handleClear = () => {
    setDraftFilters({ ...EMPTY_FILTERS });
    setFilters({ ...EMPTY_FILTERS });
    setPage(1);
  };

  return (
    <>
      <PageHeader
        eyebrow="Oversight"
        title="Audit logs"
        description={`${ROLE_SCOPE_DESCRIPTIONS[user.role]} Filter by entity, actor or UTC date range.`}
        actions={
          <span className="inline-flex items-center rounded-pill border border-line bg-paper px-3 py-1.5 text-12 font-medium text-ink-700">
            {ROLE_LABELS[user.role]}
          </span>
        }
      />

      <form
        onSubmit={handleApply}
        className="rounded-panel border border-line bg-surface p-4 sm:p-5"
      >
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-5">
          <div>
            <label htmlFor="audit-entity-type" className={labelClass}>
              Entity type
            </label>
            <select
              id="audit-entity-type"
              value={draftFilters.entityType}
              onChange={(event) => updateDraft("entityType", event.target.value)}
              className={inputClass}
            >
              <option value="">All entities</option>
              <option value="Application">Application</option>
              <option value="Institution">Institution</option>
              <option value="User">User</option>
              <option value="Inspection">Inspection</option>
              <option value="Document">Document</option>
            </select>
          </div>

          <div>
            <label htmlFor="audit-entity-id" className={labelClass}>
              Entity ID
            </label>
            <input
              id="audit-entity-id"
              type="text"
              value={draftFilters.entityId}
              onChange={(event) => updateDraft("entityId", event.target.value)}
              placeholder="UUID (optional)"
              className={inputClass}
            />
          </div>

          <div>
            <label htmlFor="audit-actor-id" className={labelClass}>
              Actor ID
            </label>
            <input
              id="audit-actor-id"
              type="text"
              value={draftFilters.actorId}
              onChange={(event) => updateDraft("actorId", event.target.value)}
              placeholder="UUID (optional)"
              className={inputClass}
            />
          </div>

          <div>
            <label htmlFor="audit-start-date" className={labelClass}>
              From date (UTC)
            </label>
            <input
              id="audit-start-date"
              type="date"
              value={draftFilters.startDate}
              onChange={(event) => updateDraft("startDate", event.target.value)}
              className={inputClass}
            />
          </div>

          <div>
            <label htmlFor="audit-end-date" className={labelClass}>
              To date (UTC)
            </label>
            <input
              id="audit-end-date"
              type="date"
              value={draftFilters.endDate}
              onChange={(event) => updateDraft("endDate", event.target.value)}
              className={inputClass}
            />
          </div>
        </div>

        <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-line pt-4">
          <Button type="submit" size="sm">
            Apply filters
          </Button>
          <Button type="button" variant="secondary" size="sm" onClick={handleClear}>
            Clear
          </Button>
          {hasFilters ? (
            <span className="text-12 text-ink-500">Filtered results</span>
          ) : null}
          <Button
            type="button"
            variant="quiet"
            size="sm"
            className="ml-auto"
            onClick={() => void auditQuery.refetch()}
            disabled={auditQuery.isFetching}
          >
            <RefreshCw
              aria-hidden="true"
              className={auditQuery.isFetching ? "size-4 animate-spin" : "size-4"}
            />
            Refresh results
          </Button>
        </div>
      </form>

      <section className="mt-5 min-w-0" aria-label="Audit records">
        {auditQuery.isPending ? (
          <div className="space-y-3" role="status" aria-label="Loading audit logs">
            {[0, 1, 2, 3, 4].map((item) => (
              <Skeleton key={item} className="h-16 w-full" />
            ))}
            <span className="sr-only">Loading audit logs</span>
          </div>
        ) : auditQuery.isError ? (
          <div className="rounded-panel border border-line bg-surface p-6">
            <p className="rounded-input border border-breach bg-breach-soft p-4 text-14 text-breach-strong">
              {auditQuery.error instanceof ApiError
                ? auditQuery.error.message
                : "Audit logs could not be loaded. Check the API connection and try again."}
            </p>
            <Button
              variant="secondary"
              size="sm"
              className="mt-3"
              onClick={() => void auditQuery.refetch()}
            >
              Retry
            </Button>
          </div>
        ) : records.length === 0 ? (
          <EmptyState
            message={
              hasFilters
                ? "No audit records match these filters. Clear them to review the permitted trail."
                : "No audit records are available in your permitted scope."
            }
            action={
              hasFilters ? (
                <Button variant="secondary" size="sm" onClick={handleClear}>
                  Clear filters
                </Button>
              ) : (
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => void auditQuery.refetch()}
                >
                  Refresh
                </Button>
              )
            }
          />
        ) : (
          <>
            <div className="hidden min-w-0 min-[1400px]:block">
              <Table density="dense">
                <TableHeader>
                  <TableRow>
                    <TableHead>Time</TableHead>
                    <TableHead>Action</TableHead>
                    <TableHead>Actor</TableHead>
                    <TableHead>Entity</TableHead>
                    <TableHead>Source IP</TableHead>
                    <TableHead>Snapshots</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {records.map((record) => (
                    <TableRow key={record.id} className="align-top">
                      <TableCell className="whitespace-nowrap text-12 text-ink-500">
                        {formatDateTime(record.created_at)}
                      </TableCell>
                      <TableCell className="whitespace-nowrap">
                        <ActionChip action={record.action} />
                      </TableCell>
                      <TableCell className="min-w-48">
                        <Actor record={record} />
                      </TableCell>
                      <TableCell className="whitespace-nowrap">
                        <p className="text-13 font-medium text-ink">{record.entity_type}</p>
                        <p className="mt-0.5 font-mono text-12 text-ink-500">
                          {shortId(record.entity_id)}
                        </p>
                      </TableCell>
                      <TableCell className="whitespace-nowrap font-mono text-12 text-ink-500">
                        {record.ip ?? "—"}
                      </TableCell>
                      <TableCell className="min-w-36">
                        <Snapshots record={record} />
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>

            <ul className="divide-y divide-line rounded-panel border border-line bg-surface min-[1400px]:hidden">
              {records.map((record) => (
                <MobileAuditCard key={record.id} record={record} />
              ))}
            </ul>

            <div className="flex flex-col gap-3 border-t border-line px-1 py-4 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-12 text-ink-500">
                Showing {firstRow}–{lastRow} of {auditQuery.data?.total ?? 0} records
              </p>
              <div className="flex items-center gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => setPage((current) => Math.max(1, current - 1))}
                  disabled={page <= 1}
                >
                  Previous
                </Button>
                <span className="min-w-24 text-center text-12 text-ink-700">
                  Page {auditQuery.data?.page ?? page} of {auditQuery.data?.pages ?? 0}
                </span>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => setPage((current) => current + 1)}
                  disabled={!auditQuery.data || page >= auditQuery.data.pages}
                >
                  Next
                </Button>
              </div>
            </div>
          </>
        )}
      </section>
    </>
  );
}
