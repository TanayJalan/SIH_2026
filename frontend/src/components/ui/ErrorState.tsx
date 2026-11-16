import { ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";

import { Button } from "./Button";

export interface ErrorStateProps {
  /** The query error. An `ApiError` message is shown verbatim. */
  error: unknown;
  /** Shown when the error is not an `ApiError` with a message. */
  message?: string;
  onRetry?: () => void;
  className?: string;
}

/** Failure state for a data region: what failed, and one clear way to retry. */
export function ErrorState({ error, message, onRetry, className }: ErrorStateProps) {
  const text =
    error instanceof ApiError && error.message
      ? error.message
      : (message ?? "This section could not be loaded. Check the API connection and try again.");

  return (
    <div className={cn("rounded-panel border border-line bg-surface p-6", className)}>
      <p role="alert" className="rounded-input border border-breach bg-breach-soft p-4 text-14 text-breach-strong">
        {text}
      </p>
      {onRetry ? (
        <Button variant="secondary" size="sm" className="mt-3" onClick={onRetry}>
          Retry
        </Button>
      ) : null}
    </div>
  );
}
