import { useEffect, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { useAuth } from "@/auth/AuthContext";
import { useToast } from "@/components/ui";
import { API_BASE_URL } from "@/lib/api";

/** Query roots that depend on simulated time or alert delivery. */
const TIME_INVALIDATION_ROOTS = [
  "application",
  "applications",
  "application-deadlines",
  "application-fee",
  "case-decisions",
  "case-appeal",
  "case-letters",
  "workflow-timeline",
  "allowed-actions",
  "compliance-preview",
  "compliance-monitor",
  "compliance-trend",
  "deficiencies",
  "document-records",
  "document-versions",
  "document-checklist",
  "checklist",
  "inspections",
  "committees",
  "audit-logs",
  "security-deposit",
  "time-simulation",
];

/** Toast duration for persistent critical alerts (~24 days: effectively sticky). */
const PERSISTENT_DURATION_MS = 2_147_000_000;
/** Reconnect backoff after a dropped stream. */
const MAX_RETRY_DELAY_MS = 10_000;

interface LiveAlertPayload {
  id: string;
  type: string;
  severity: "CRITICAL" | "HIGH" | "MEDIUM" | "LOW";
  title: string;
  message: string;
  application_id: string | null;
  escalation_level: number;
}

/**
 * Subscribe to `GET /alerts/stream` (SSE) for the signed-in user.
 *
 * Frames:
 * - `alert`: one new committed in-app alert row → live toast (critical and
 *   high alerts persist) plus an `["alerts"]` refresh so the bell count and
 *   the Alerts page update without a reload.
 * - `time`: the demo clock advanced or reset → every deadline-driven query
 *   is invalidated, so SlaRing, StageTrack and countdowns refresh live.
 *
 * `EventSource` reconnects automatically, but only while the page stays on
 * the same URL; on error we close and re-open ourselves with exponential
 * backoff so a token change is picked up.
 */
export function useAlertStream() {
  const { token } = useAuth();
  const { toast } = useToast();
  const queryClient = useQueryClient();

  const toastRef = useRef(toast);
  toastRef.current = toast;

  useEffect(() => {
    if (!token) return;

    let closed = false;
    let source: EventSource | null = null;
    let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
    let retryDelay = 500;

    const invalidateTimeQueries = () => {
      for (const root of TIME_INVALIDATION_ROOTS) {
        void queryClient.invalidateQueries({ queryKey: [root] });
      }
    };

    const connect = () => {
      if (closed) return;
      const url = `${API_BASE_URL}/alerts/stream?token=${encodeURIComponent(token)}`;
      source = new EventSource(url);

      source.addEventListener("connected", () => {
        retryDelay = 500;
      });

      source.addEventListener("alert", (event) => {
        let payload: LiveAlertPayload;
        try {
          payload = JSON.parse((event as MessageEvent<string>).data);
        } catch {
          return;
        }
        const escalated =
          payload.escalation_level > 0
            ? ` · escalation level ${payload.escalation_level}`
            : "";
        const critical = payload.severity === "CRITICAL";
        toastRef.current({
          title: critical ? `Critical alert: ${payload.title}` : payload.title,
          description: `${payload.message}${escalated}`,
          variant: critical || payload.severity === "HIGH" ? "error" : "info",
          duration: critical ? PERSISTENT_DURATION_MS : undefined,
        });
        void queryClient.invalidateQueries({ queryKey: ["alerts"] });
      });

      source.addEventListener("time", () => {
        invalidateTimeQueries();
        void queryClient.invalidateQueries({ queryKey: ["alerts"] });
      });

      source.onerror = () => {
        source?.close();
        source = null;
        if (closed) return;
        reconnectTimer = setTimeout(connect, retryDelay);
        retryDelay = Math.min(retryDelay * 2, MAX_RETRY_DELAY_MS);
      };
    };

    connect();

    return () => {
      closed = true;
      if (reconnectTimer !== null) clearTimeout(reconnectTimer);
      source?.close();
    };
  }, [token, queryClient]);
}
