import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { CalendarClock, Check, Clock3, RotateCcw } from "lucide-react";

import { useToast } from "@/components/ui";
import { useAuth } from "../auth/AuthContext";
import {
  ApiError,
  getTimeSimulation,
  updateTimeSimulation,
  type TimeSimulation,
  type TimeSimulationUpdate,
} from "../lib/api";
import { formatDate } from "../lib/format";
import { cn } from "../lib/utils";

export default function DemoTimeControl() {
  const { token } = useAuth();
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const [open, setOpen] = useState(false);
  const [isUpdating, setIsUpdating] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const timeQuery = useQuery({
    queryKey: ["time-simulation"],
    queryFn: () => getTimeSimulation(token ?? ""),
    enabled: Boolean(token),
    retry: false,
    staleTime: 30_000,
  });

  useEffect(() => {
    if (!open) {
      return;
    }
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
  }, [open]);

  if (timeQuery.isError) {
    return null;
  }

  const time = timeQuery.data;
  if (!time?.enabled) {
    return null;
  }

  const applyUpdate = async (update: TimeSimulationUpdate, label: string) => {
    if (!token || isUpdating) {
      return;
    }
    setIsUpdating(true);
    try {
      const result = await updateTimeSimulation(token, update);
      queryClient.setQueryData<TimeSimulation>(["time-simulation"], result);
      void queryClient.invalidateQueries({ queryKey: ["applications"] });
      void queryClient.invalidateQueries({ queryKey: ["alerts"] });
      void queryClient.invalidateQueries({ queryKey: ["global-search"] });
      setOpen(false);
      toast({ title: label, description: `Simulated date is ${formatDate(result.simulated_now)}.` });
    } catch (error) {
      toast({
        title: "Demo time could not be updated",
        description:
          error instanceof ApiError ? error.message : "Check the API connection and try again.",
        variant: "error",
      });
    } finally {
      setIsUpdating(false);
    }
  };

  const offsetLabel = time.offset_days > 0 ? `+${time.offset_days} days` : "Real time";

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((current) => !current)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={`Demo time controls, simulated date ${formatDate(time.simulated_now)}`}
        title={`Demo time · ${formatDate(time.simulated_now)}`}
        className={cn(
          "inline-flex h-9 items-center gap-2 rounded-input border border-dashed border-line px-2.5 text-12 font-medium text-ink-700 transition-colors hover:border-ink-300 hover:bg-paper",
          open && "border-ink-300 bg-paper",
        )}
      >
        <Clock3 aria-hidden="true" className="size-3.5" />
        <span className="hidden sm:inline">Demo time</span>
        <span className="hidden text-ink-500 xl:inline">{formatDate(time.simulated_now)}</span>
      </button>

      {open ? (
        <div
          role="menu"
          aria-label="Demo time controls"
          className="absolute right-0 top-full z-50 mt-2 w-64 rounded-panel border border-line bg-surface p-2 shadow-popover"
        >
          <div className="border-b border-line px-2.5 pb-2.5 pt-1.5">
            <p className="text-12 font-semibold uppercase tracking-[0.12em] text-ink-500">
              Simulated clock
            </p>
            <p className="mt-1.5 font-serif text-20 font-semibold text-ink">
              {formatDate(time.simulated_now)}
            </p>
            <p className="mt-0.5 flex items-center gap-1.5 text-12 text-ink-500">
              <CalendarClock aria-hidden="true" className="size-3.5" />
              {offsetLabel}
              {time.offset_days > 0 ? <Check aria-hidden="true" className="size-3.5 text-ok" /> : null}
            </p>
          </div>
          <div className="mt-1 space-y-0.5">
            <button
              type="button"
              role="menuitem"
              disabled={isUpdating}
              onClick={() => void applyUpdate({ days: 1 }, "Demo clock advanced by 1 day")}
              className="flex w-full items-center rounded-input px-2.5 py-2 text-left text-13 text-ink transition-colors hover:bg-paper disabled:text-ink-300"
            >
              Advance 1 day
            </button>
            <button
              type="button"
              role="menuitem"
              disabled={isUpdating}
              onClick={() => void applyUpdate({ days: 7 }, "Demo clock advanced by 7 days")}
              className="flex w-full items-center rounded-input px-2.5 py-2 text-left text-13 text-ink transition-colors hover:bg-paper disabled:text-ink-300"
            >
              Advance 7 days
            </button>
            <button
              type="button"
              role="menuitem"
              disabled={isUpdating || time.offset_days === 0}
              onClick={() => void applyUpdate({ reset: true }, "Demo clock reset")}
              className="flex w-full items-center gap-2 rounded-input px-2.5 py-2 text-left text-13 text-ink transition-colors hover:bg-paper disabled:text-ink-300"
            >
              <RotateCcw aria-hidden="true" className="size-3.5" />
              Reset to real time
            </button>
          </div>
          <p className="border-t border-line px-2.5 pt-2 text-12 leading-4 text-ink-500">
            DEBUG only. Changes are audited and affect overdue calculations.
          </p>
        </div>
      ) : null}
    </div>
  );
}
