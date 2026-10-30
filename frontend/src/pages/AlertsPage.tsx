import React, { useState, useCallback } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Bell,
  Check,
  FilterX,
  RefreshCw,
  Siren,
  User,
} from "lucide-react";
import { Link } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import PageHeader from "../components/PageHeader";
import {
  Button,
  EmptyState,
  Select,
  Skeleton,
  StatusPill,
  useToast,
  type StatusPillTone,
} from "../components/ui";
import {
  ApiError,
  acknowledgeAlert,
  getAlertSummary,
  getAlerts,
  type AlertRecord,
  type AlertStatus,
  type Severity,
} from "../lib/api";
import { formatRelativeTime, formatDateTime, humanizeEnum, shortId } from "../lib/format";
import { cn } from "../lib/utils";

const PAGE_SIZE = 20;
const UNREAD_STATUSES: AlertStatus[] = ["PENDING", "SENT"];

const SEVERITY_TONES: Record<Severity, StatusPillTone> = {
  LOW: "info",
  MEDIUM: "watch",
  HIGH: "breach",
  CRITICAL: "breach",
};

const SEVERITY_OPTIONS = [
  { value: "ALL", label: "All severities" },
  { value: "CRITICAL", label: "Critical" },
  { value: "HIGH", label: "High" },
  { value: "MEDIUM", label: "Medium" },
  { value: "LOW", label: "Low" },
];

const STATUS_OPTIONS = [
  { value: "ALL", label: "All statuses" },
  { value: "PENDING", label: "Pending" },
  { value: "SENT", label: "Sent" },
  { value: "ACKED", label: "Acknowledged" },
];

const TYPE_LABELS: Record<string, string> = {
  DEADLINE_APPROACHING: "Deadline approaching",
  SLA_BREACHED: "SLA breached",
  DEFICIENCY_DUE: "Deficiency response due",
  DEFICIENCY_OVERDUE: "Deficiency response overdue",
  DOCUMENT_EXPIRING: "Document expiring",
  COMPLIANCE_RED: "Compliance became RED",
  APPLICATION_STATUS_CHANGED: "Application status changed",
  INSPECTION_SCHEDULED: "Inspection scheduled",
  APPEAL_WINDOW_CLOSING: "Appeal window closing",
  APPEAL_EXPIRED: "Appeal expired",
  DEPOSIT_DUE: "Security Deposit due",
  DEPOSIT_OVERDUE: "Security Deposit overdue",
  LOA_EXPIRED: "LoA expired",
  ESCALATION: "Escalation",
};

function isUnread(alert: AlertRecord): boolean {
  return UNREAD_STATUSES.includes(alert.status);
}

function alertTypeLabel(alert: AlertRecord): string {
  if (alert.escalation_level > 0) {
    return `Escalation · level ${alert.escalation_level}`;
  }
  return TYPE_LABELS[alert.type] ?? humanizeEnum(alert.type);
}

function SummaryCard({
  label,
  value,
  tone = "ink",
}: {
  label: string;
  value: number;
  tone?: "ink" | "breach" | "watch" | "ok";
}) {
  const toneClass = {
    ink: "text-ink",
    breach: "text-breach-strong",
    watch: "text-watch-strong",
    ok: "text-ok-strong",
  }[tone];

  return (
    <div className="rounded-panel border border-line bg-surface p-4">
      <p className="text-12 font-medium text-ink-500">{label}</p>
      <p className={cn("mt-1 font-serif text-28 font-semibold tabular-nums", toneClass)}>
        {value}
      </p>
    </div>
  );
}

/** Mini escalation chain: a horizontal line of level nodes. The current
 *  alert's level is highlighted; a filled node means that level has been
 *  acknowledged. */
function EscalationChainMini({
  level,
  acknowledged,
  acknowledgedBy,
  acknowledgedAt,
}: {
  level: number;
  acknowledged: boolean;
  acknowledgedBy: string | null;
  acknowledgedAt: string | null;
}) {
  const nodes = Array.from({ length: Math.max(1, level + 1) }, (_, i) => i);
  const isCurrent = (node: number) => node === level;
  const isAcked = acknowledged && isCurrent(level);

  return (
    <div className="flex items-center gap-1.5 text-10">
      {nodes.map((node) => (
        <div key={node} className="flex flex-col items-center gap-0.5">
          <span
            className={cn(
              "size-5 shrink-0 rounded-full flex items-center justify-center font-semibold border",
              isAcked
                ? "bg-ok text-surface border-ok"
                : isCurrent(node)
                  ? "bg-paper text-ink border-ink"
                  : "bg-surface text-ink-400 border-line",
            )}
          >
            {node}
          </span>
          <span className="text-ink-500">{node === 0 ? "L0" : `L${node}`}</span>
        </div>
      ))}
      {level > 0 && (
        <span
          className={cn(
            "h-px flex-1",
            acknowledged ? "bg-ok" : "bg-line",
          )}
          aria-hidden="true"
        />
      )}
      {acknowledged ? (
        <span className="text-ok-strong font-semibold text-11">
          ✓ Acknowledged by {acknowledgedBy ?? "user"}
        </span>
      ) : (
        <span className="text-ink-500 text-11">Pending</span>
      )}
      {acknowledgedAt ? (
        <span className="text-ink-400 text-10">
          · {formatRelativeTime(acknowledgedAt)}
        </span>
      ) : null}
    </div>
  );
}

function dayKeyFor(createdAt: string): string {
  const date = new Date(createdAt);
  return date.toISOString().slice(0, 10);
}

function dayLabelFor(createdAt: string): string {
  const date = new Date(createdAt);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);
  const alertDay = new Date(date);
  alertDay.setHours(0, 0, 0, 0);

  if (alertDay.getTime() === today.getTime()) {
    return "Today";
  }
  if (alertDay.getTime() === yesterday.getTime()) {
    return "Yesterday";
  }
  return formatDateTime(createdAt).split(" · ")[0] ?? date.toLocaleDateString("en-IN");
}

function groupAlertsByDay(alerts: AlertRecord[]): Array<{ dayKey: string; dayLabel: string; alerts: AlertRecord[] }> {
  const groups = new Map<string, AlertRecord[]>();
  for (const alert of alerts) {
    const key = dayKeyFor(alert.created_at);
    if (!groups.has(key)) {
      groups.set(key, []);
    }
    groups.get(key)!.push(alert);
  }
  return Array.from(groups.entries()).map(([dayKey, items]) => ({
    dayKey,
    dayLabel: dayLabelFor(items[0].created_at),
    alerts: items,
  }));
}

function AlertCard({
  alert,
  acknowledging,
  onAcknowledge,
  selected,
  onToggleSelect,
}: {
  alert: AlertRecord;
  acknowledging: boolean;
  onAcknowledge: (alert: AlertRecord) => void;
  selected: Set<string>;
  onToggleSelect: (id: string) => void;
}) {
  const unread = isUnread(alert);
  const isSelected = selected.has(alert.id);

  return (
    <li
      className={cn(
        "px-5 py-5 sm:px-6 border-b border-line last:border-0",
        unread && "bg-paper/60",
        isSelected && "ring-1 ring-info bg-info-soft/40",
      )}
    >
      <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-3">
        <div className="flex min-w-0 items-start gap-3">
          <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-input">
            <input
              type="checkbox"
              checked={isSelected}
              onChange={() => onToggleSelect(alert.id)}
              aria-label={`Select ${alert.title}`}
              className="size-4 rounded border-line text-saffron focus-visible:ring-focus"
            />
          </div>
          <div className="flex min-w-0 items-start gap-3">
            <span
              className={cn(
                "mt-0.5 grid size-9 shrink-0 place-items-center rounded-input",
                unread ? "bg-breach-soft text-breach-strong" : "bg-paper text-ink-500",
              )}
            >
              <Bell aria-hidden="true" className="size-4" />
            </span>
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <p className="text-14 font-semibold text-ink">{alert.title}</p>
                {unread ? (
                  <span className="rounded-pill bg-breach-soft px-2 py-0.5 text-11 font-medium text-breach-strong">
                    Unread
                  </span>
                ) : null}
                {alert.escalation_level > 0 ? (
                  <StatusPill status="breach">
                    <Siren aria-hidden="true" className="size-3" />
                    Escalated · level {alert.escalation_level}
                  </StatusPill>
                ) : null}
              </div>
              <p className="mt-1 text-13 leading-5 text-ink-700">{alert.message}</p>
              {alert.apH_clause ? (
                <p className="mt-1.5 inline-flex items-center gap-1 text-11 font-medium text-ink-700">
                  <User aria-hidden="true" className="size-3.5" />
                  {alert.apH_clause}
                </p>
              ) : null}
              <EscalationChainMini
                level={alert.escalation_level}
                acknowledged={!unread}
                acknowledgedBy={alert.acknowledged_by_name}
                acknowledgedAt={alert.acknowledged_at}
              />
            </div>
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <StatusPill status={SEVERITY_TONES[alert.severity]}>
            {humanizeEnum(alert.severity)}
          </StatusPill>
          {unread ? (
            <Button
              variant="secondary"
              size="sm"
              onClick={() => onAcknowledge(alert)}
              disabled={acknowledging}
            >
              <Check aria-hidden="true" className="size-4" />
              {acknowledging ? "Acknowledging…" : "Acknowledge"}
            </Button>
          ) : null}
        </div>
      </div>

      <dl className="mt-4 grid grid-cols-2 gap-3 border-t border-line pt-3 text-12 sm:grid-cols-5">
        <div>
          <dt className="text-ink-500">Received</dt>
          <dd className="mt-0.5 text-ink">{formatRelativeTime(alert.created_at)}</dd>
        </div>
        <div>
          <dt className="text-ink-500">Channel</dt>
          <dd className="mt-0.5 text-ink">{humanizeEnum(alert.channel)}</dd>
        </div>
        <div>
          <dt className="text-ink-500">Status</dt>
          <dd className="mt-0.5 text-ink">{humanizeEnum(alert.status)}</dd>
        </div>
        <div>
          <dt className="text-ink-500">Alert type</dt>
          <dd className="mt-0.5 truncate text-ink">{alertTypeLabel(alert)}</dd>
        </div>
        <div className="sm:col-span-2">
          <dt className="text-ink-500">Clause</dt>
          <dd className="mt-0.5 text-ink">
            <span className="font-mono text-11">
              {alert.apH_clause ?? "—"}
            </span>
          </dd>
        </div>
      </dl>

      {alert.acknowledged_at ? (
        <p className="mt-2 text-12 text-ink-500">
          Acknowledged {formatDateTime(alert.acknowledged_at)}
          {alert.acknowledged_by_name
            ? ` by ${alert.acknowledged_by_name}`
            : ""}
        </p>
      ) : null}

      {alert.application_id ? (
        <Link
          to={`/applications/${alert.application_id}`}
          className="mt-3 inline-flex text-12 font-medium text-ink-700 underline-offset-4 hover:text-ink hover:underline"
        >
          Open application {shortId(alert.application_id)}
        </Link>
      ) : null}
    </li>
  );
}

export default function AlertsPage() {
  const { user, token } = useAuth();
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [page, setPage] = useState(1);
  const [severity, setSeverity] = useState<Severity | "ALL">("ALL");
  const [status, setStatus] = useState<AlertStatus | "ALL">("ALL");
  const [typeFilter, setTypeFilter] = useState<string | "ALL">("ALL");
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [bulkAckPending, setBulkAckPending] = useState(false);

  const alertsQuery = useQuery({
    queryKey: ["alerts", "list", { page, severity, status, typeFilter, unreadOnly }],
    queryFn: () =>
      getAlerts(token ?? "", {
        page,
        pageSize: PAGE_SIZE,
        severity: severity === "ALL" ? undefined : severity,
        status: status === "ALL" ? undefined : status,
        type: typeFilter === "ALL" ? undefined : typeFilter,
        unread: unreadOnly || undefined,
      }),
    enabled: Boolean(token),
  });

  const summaryQuery = useQuery({
    queryKey: ["alerts", "summary", user?.id],
    queryFn: () => getAlertSummary(token ?? ""),
    enabled: Boolean(token && user),
  });

  const ackMutation = useMutation({
    mutationFn: (alertId: string) => acknowledgeAlert(token ?? "", alertId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["alerts"] });
      setSelected((current) => {
        const next = new Set(current);
        // handled per-alert below
        return next;
      });
    },
    onError: (error) => {
      toast({
        title: "Alert could not be acknowledged",
        description:
          error instanceof ApiError
            ? error.message
            : "Check the API connection and try again.",
        variant: "error",
      });
    },
  });

  const acknowledgeOne = useCallback(
    (alert: AlertRecord) => {
      ackMutation.mutate(alert.id);
      setSelected((current) => {
        const next = new Set(current);
        next.delete(alert.id);
        return next;
      });
    },
    [ackMutation],
  );

  const bulkAcknowledge = async () => {
    const ids = [...selected];
    setBulkAckPending(true);
    try {
      await Promise.all(ids.map((id) => acknowledgeAlert(token ?? "", id)));
      void queryClient.invalidateQueries({ queryKey: ["alerts"] });
      setSelected(new Set());
      toast({
        title: "Alerts acknowledged",
        description: `${ids.length} alert${ids.length === 1 ? "" : "s"} acknowledged.`,
      });
    } catch (error) {
      toast({
        title: "Some alerts could not be acknowledged",
        description:
          error instanceof ApiError ? error.message : "Check the API connection and try again.",
        variant: "error",
      });
    } finally {
      setBulkAckPending(false);
    }
  };

  const toggleSelect = (id: string) => {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const clearFilters = () => {
    setSeverity("ALL");
    setStatus("ALL");
    setTypeFilter("ALL");
    setUnreadOnly(false);
    setPage(1);
  };

  const applyFilter = (action: () => void) => {
    action();
    setPage(1);
  };

  if (!user) {
    return null;
  }

  const data = alertsQuery.data;
  const alerts = data?.items ?? [];
  const summary = summaryQuery.data;
  const grouped = groupAlertsByDay(alerts);
  const firstRow = data && data.total > 0 ? (data.page - 1) * data.page_size + 1 : 0;
  const lastRow = data ? Math.min(data.page * data.page_size, data.total) : 0;
  const hasFilters = severity !== "ALL" || status !== "ALL" || typeFilter !== "ALL" || unreadOnly;
  const canBulkAck = selected.size > 0;

  const typeOptions = [
    { value: "ALL", label: "All types" },
    ...Object.entries(TYPE_LABELS).map(([value, label]) => ({ value, label })),
  ];

  return (
    <>
      <PageHeader
        eyebrow="Notifications"
        title="Alerts"
        description="Deadline, SLA, compliance and workflow notifications addressed to your account. Acknowledge an alert to stop its escalation chain. Alerts update live through the Server-Sent Events stream."
        actions={
          <Button
            variant="secondary"
            size="sm"
            onClick={() => void alertsQuery.refetch()}
            disabled={alertsQuery.isFetching}
          >
            <RefreshCw
              aria-hidden="true"
              className={alertsQuery.isFetching ? "size-4 animate-spin" : "size-4"}
            />
            Refresh
          </Button>
        }
      />

      <section
        aria-label="Alert summary"
        className="mb-5 grid grid-cols-2 gap-3 sm:grid-cols-4"
      >
        <SummaryCard label="Unread" value={summary?.unread ?? 0} tone="watch" />
        <SummaryCard
          label="Critical unread"
          value={summary?.unread_by_severity.CRITICAL ?? 0}
          tone="breach"
        />
        <SummaryCard
          label="High unread"
          value={summary?.unread_by_severity.HIGH ?? 0}
          tone="breach"
        />
        <SummaryCard label="Acknowledged" value={summary?.acknowledged ?? 0} tone="ok" />
      </section>

      <section
        aria-label="Filter alerts"
        className="mb-5 rounded-panel border border-line bg-surface p-4"
      >
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5 lg:items-end">
          <Select
            label="Severity"
            value={severity}
            onValueChange={(value) =>
              applyFilter(() => setSeverity(value as Severity | "ALL"))
            }
            options={SEVERITY_OPTIONS}
          />
          <Select
            label="Status"
            value={status}
            onValueChange={(value) =>
              applyFilter(() => setStatus(value as AlertStatus | "ALL"))
            }
            options={STATUS_OPTIONS}
          />
          <Select
            label="Type"
            value={typeFilter}
            onValueChange={(value) =>
              applyFilter(() => setTypeFilter(value as string | "ALL"))
            }
            options={typeOptions}
          />
          <label className="flex h-10 items-center gap-2 text-13 font-medium text-ink-700">
            <input
              type="checkbox"
              checked={unreadOnly}
              onChange={(event) =>
                applyFilter(() => setUnreadOnly(event.target.checked))
              }
              className="size-4 rounded border-line text-saffron focus-visible:ring-focus"
            />
            Unread only
          </label>
          <div className="flex lg:justify-end">
            <Button
              variant="quiet"
              size="sm"
              onClick={clearFilters}
              disabled={!hasFilters}
            >
              <FilterX aria-hidden="true" className="size-4" />
              Clear filters
            </Button>
          </div>
        </div>
      </section>

      {/* Bulk action toolbar */}
      {canBulkAck ? (
        <section className="mb-5 rounded-input border border-info bg-info-soft/40 p-3">
          <div className="flex flex-wrap items-center gap-3">
            <span className="text-12 font-medium text-info-strong">
              {selected.size} alert{selected.size === 1 ? "" : "s"} selected
            </span>
            <Button
              variant="secondary"
              size="sm"
              onClick={bulkAcknowledge}
              disabled={bulkAckPending}
            >
              {bulkAckPending ? "Acknowledging…" : "Acknowledge selected"}
            </Button>
            <Button
              variant="quiet"
              size="sm"
              onClick={() => setSelected(new Set())}
            >
              Clear selection
            </Button>
          </div>
        </section>
      ) : null}

      <section aria-label="Alerts" className="min-w-0">
        {alertsQuery.isPending ? (
          <div className="space-y-3" role="status" aria-label="Loading alerts">
            {[0, 1, 2].map((item) => (
              <Skeleton key={item} className="h-36 w-full" />
            ))}
            <span className="sr-only">Loading alerts</span>
          </div>
        ) : alertsQuery.isError ? (
          <div className="rounded-panel border border-line bg-surface p-6">
            <p className="rounded-input border border-breach bg-breach-soft p-4 text-14 text-breach-strong">
              {alertsQuery.error instanceof ApiError
                ? alertsQuery.error.message
                : "Alerts could not be loaded. Check the API connection and try again."}
            </p>
            <Button
              variant="secondary"
              size="sm"
              className="mt-3"
              onClick={() => void alertsQuery.refetch()}
            >
              Retry
            </Button>
          </div>
        ) : alerts.length === 0 ? (
          <EmptyState
            message={
              hasFilters
                ? "No alerts match these filters. Clear the filters to see the full inbox."
                : "No alerts are addressed to your account. Deadline and compliance notifications will appear here."
            }
            action={
              hasFilters ? (
                <Button variant="secondary" size="sm" onClick={clearFilters}>
                  Clear filters
                </Button>
              ) : (
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => void alertsQuery.refetch()}
                >
                  Refresh
                </Button>
              )
            }
          />
        ) : (
          <>
            <ul className="divide-y divide-line rounded-panel border border-line bg-surface">
              {grouped.map((group) => (
                <React.Fragment key={group.dayKey}>
                  <li className="px-5 py-3 bg-surface/40">
                    <p className="text-11 font-semibold uppercase tracking-wide text-ink-500">
                      {group.dayLabel}
                    </p>
                  </li>
                  {group.alerts.map((alert) => (
                    <AlertCard
                      key={alert.id}
                      alert={alert}
                      acknowledging={
                        ackMutation.isPending && ackMutation.variables === alert.id
                      }
                      onAcknowledge={acknowledgeOne}
                      selected={selected}
                      onToggleSelect={toggleSelect}
                    />
                  ))}
                </React.Fragment>
              ))}
            </ul>

            <div className="flex flex-col gap-3 border-t border-line px-1 py-4 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-12 text-ink-500">
                Showing {firstRow}–{lastRow} of {data?.total ?? 0} alerts
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
                  Page {data?.page ?? page} of {data?.pages ?? 0}
                </span>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={() => setPage((current) => current + 1)}
                  disabled={!data || page >= data.pages}
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
