import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell, BellRing, Check, ChevronRight } from "lucide-react";
import { Link } from "react-router-dom";

import { useAuth } from "@/auth/AuthContext";
import { useToast } from "@/components/ui";
import {
  ApiError,
  acknowledgeAlert,
  getAlerts,
  getAlertSummary,
  type AlertRecord,
  type Severity,
} from "@/lib/api";
import { formatRelativeTime, humanizeEnum, shortId } from "@/lib/format";
import { cn } from "@/lib/utils";

const SEVERITY_DOT: Record<Severity, string> = {
  CRITICAL: "bg-breach",
  HIGH: "bg-breach",
  MEDIUM: "bg-watch",
  LOW: "bg-info",
};

function unreadAlert(alert: AlertRecord): boolean {
  return alert.status === "PENDING" || alert.status === "SENT";
}

const BELL_ANIMATION_MS = 900;

export default function NotificationBell() {
  const { user, token } = useAuth();
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [open, setOpen] = useState(false);
  const [ringing, setRinging] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const lastCountRef = useRef<number | null>(null);

  const summaryQuery = useQuery({
    queryKey: ["alerts", "summary", user?.id],
    queryFn: () => getAlertSummary(token ?? ""),
    enabled: Boolean(token && user),
    retry: false,
    staleTime: 30_000,
    refetchInterval: 30_000,
  });

  const recentQuery = useQuery({
    queryKey: ["alerts", "bell", user?.id],
    queryFn: () => getAlerts(token ?? "", { page: 1, pageSize: 8 }),
    enabled: Boolean(token && user),
    retry: false,
    staleTime: 30_000,
    refetchInterval: 30_000,
  });

  const ackMutation = useMutation({
    mutationFn: (alertId: string) => acknowledgeAlert(token ?? "", alertId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["alerts"] });
      toast({ title: "Alert acknowledged" });
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

  // Ring the bell once when the unread count grows (a live SSE alert arrived).
  useEffect(() => {
    const count = summaryQuery.data?.unread ?? 0;
    if (
      lastCountRef.current !== null &&
      count > lastCountRef.current
    ) {
      setRinging(true);
      const timer = setTimeout(() => setRinging(false), BELL_ANIMATION_MS);
      return () => clearTimeout(timer);
    }
    lastCountRef.current = count;
  }, [summaryQuery.data?.unread]);

  useEffect(() => {
    if (!open) {
      return;
    }
    void summaryQuery.refetch();
    void recentQuery.refetch();

    const handlePointerDown = (event: MouseEvent) => {
      if (!containerRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    };
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handlePointerDown);
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
      document.removeEventListener("keydown", handleKeyDown);
    };
    // The callbacks intentionally refetch only when the popover opens.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  if (!user) {
    return null;
  }

  const unread = summaryQuery.data?.unread ?? 0;
  const alerts = recentQuery.data?.items ?? [];

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((current) => !current)}
        aria-label={unread > 0 ? `${unread} unread alerts` : "Alerts"}
        aria-haspopup="dialog"
        aria-expanded={open}
        className={cn(
          "relative inline-flex size-9 items-center justify-center rounded-input text-ink-700 transition-colors hover:bg-paper hover:text-ink",
          open && "bg-paper text-ink",
          ringing && "ring-2 ring-breach animate-ping",
        )}
      >
        {ringing ? (
          <BellRing
            aria-hidden="true"
            className={cn("size-4", ringing && "text-breach-strong animate-bell")}
          />
        ) : (
          <Bell aria-hidden="true" className="size-4" />
        )}
        {unread > 0 ? (
          <span className="absolute -right-0.5 -top-0.5 grid min-w-4 place-items-center rounded-pill bg-breach px-1 py-0.5 text-12 font-semibold leading-none text-surface">
            {unread > 99 ? "99+" : unread}
          </span>
        ) : null}
      </button>

      {open ? (
        <div
          role="dialog"
          aria-label="Recent alerts"
          className="absolute right-0 top-full z-50 mt-2 w-[min(22rem,calc(100vw-1.5rem))] overflow-hidden rounded-panel border border-line bg-surface shadow-popover"
        >
          <div className="flex items-center justify-between gap-3 border-b border-line px-4 py-3">
            <div>
              <p className="text-14 font-semibold text-ink">Alerts</p>
              <p className="mt-0.5 text-12 text-ink-500">
                {unread > 0
                  ? `${unread} unread notification${unread === 1 ? "" : "s"}`
                  : "You are up to date"}
              </p>
            </div>
            {summaryQuery.data ? (
              <span className="rounded-pill bg-paper px-2 py-1 text-11 font-medium text-ink-700">
                {summaryQuery.data.total} total
              </span>
            ) : null}
          </div>

          {recentQuery.isPending ? (
            <div className="space-y-3 p-4" role="status">
              <div className="h-10 animate-pulse rounded-input bg-paper" />
              <div className="h-10 animate-pulse rounded-input bg-paper" />
              <span className="sr-only">Loading alerts</span>
            </div>
          ) : recentQuery.isError ? (
            <p className="p-4 text-13 text-breach-strong">
              Alerts could not be loaded. Check the API connection.
            </p>
          ) : alerts.length === 0 ? (
            <p className="p-4 text-13 leading-5 text-ink-700">
              No alerts are addressed to your account yet.
            </p>
          ) : (
            <ul className="max-h-96 divide-y divide-line overflow-y-auto">
              {alerts.map((alert) => (
                <li key={alert.id} className="px-4 py-3">
                  <div className="flex items-start gap-2.5">
                    <span
                      aria-hidden="true"
                      className={cn(
                        "mt-1.5 size-2 shrink-0 rounded-pill",
                        SEVERITY_DOT[alert.severity],
                      )}
                    />
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-1.5">
                        <p className="text-13 font-medium leading-5 text-ink">
                          {alert.title}
                        </p>
                        {alert.escalation_level > 0 ? (
                          <span className="rounded-pill bg-breach-soft px-1.5 py-0.5 text-11 font-medium text-breach-strong">
                            Escalated
                          </span>
                        ) : null}
                      </div>
                      <p className="mt-0.5 line-clamp-1 text-12 leading-4 text-ink-700">
                        {alert.message}
                      </p>
                      <div className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-11 text-ink-500">
                        <span>{humanizeEnum(alert.severity)}</span>
                        <span aria-hidden="true">·</span>
                        <span>{formatRelativeTime(alert.created_at)}</span>
                        {alert.application_id ? (
                          <>
                            <span aria-hidden="true">·</span>
                            <Link
                              to={`/applications/${alert.application_id}`}
                              onClick={() => setOpen(false)}
                              className="font-medium text-ink-700 underline-offset-4 hover:text-ink hover:underline"
                            >
                              App {shortId(alert.application_id)}
                            </Link>
                          </>
                        ) : null}
                      </div>
                    </div>
                    {unreadAlert(alert) ? (
                      <button
                        type="button"
                        onClick={() => ackMutation.mutate(alert.id)}
                        disabled={ackMutation.isPending}
                        aria-label={`Acknowledge ${alert.title}`}
                        title="Acknowledge"
                        className="mt-0.5 inline-flex size-7 shrink-0 items-center justify-center rounded-input text-ink-500 transition-colors hover:bg-ok-soft hover:text-ok-strong disabled:text-ink-300"
                      >
                        <Check aria-hidden="true" className="size-4" />
                      </button>
                    ) : null}
                  </div>
                </li>
              ))}
            </ul>
          )}

          <Link
            to="/alerts"
            onClick={() => setOpen(false)}
            className="flex items-center justify-between gap-2 border-t border-line bg-paper px-4 py-2.5 text-12 font-medium text-ink-700 transition-colors hover:bg-surface hover:text-ink"
          >
            View all alerts
            <ChevronRight aria-hidden="true" className="size-3.5" />
          </Link>
        </div>
      ) : null}
    </div>
  );
}
