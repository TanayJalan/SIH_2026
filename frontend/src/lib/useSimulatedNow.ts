import { useQuery } from "@tanstack/react-query";

import { useAuth } from "@/auth/AuthContext";
import { getTimeSimulation } from "@/lib/api";

export const TIME_SIMULATION_QUERY_KEY = ["time-simulation"] as const;

const MS_PER_DAY = 86_400_000;

/**
 * The clock every client-side countdown should run on.
 *
 * The DEBUG demo control advances the backend `SimulatedClock`; the demo
 * control and the SSE `time` frames invalidate `["time-simulation"]`, so any
 * component using this hook re-renders with the new date within milliseconds.
 * Without a live demo state (DEBUG disabled, endpoint errors) it falls back to
 * the real browser clock.
 */
export function useSimulatedNow(): Date {
  const { token } = useAuth();
  const { data } = useQuery({
    queryKey: TIME_SIMULATION_QUERY_KEY,
    queryFn: () => getTimeSimulation(token ?? ""),
    enabled: Boolean(token),
    staleTime: 30_000,
    retry: false,
  });
  if (data === undefined || !data.enabled) {
    return new Date();
  }
  const parsed = new Date(data.simulated_now);
  return Number.isNaN(parsed.getTime()) ? new Date() : parsed;
}

/** Calendar days between now and a due timestamp, counting as a signed ceil. */
export function calendarDaysUntil(now: Date, dueAt: string | null | undefined): number | null {
  if (!dueAt) {
    return null;
  }
  const due = new Date(dueAt).getTime();
  if (Number.isNaN(due)) {
    return null;
  }
  return Math.ceil((due - now.getTime()) / MS_PER_DAY);
}
