import * as React from "react";

import { cn } from "@/lib/utils";

export interface EmptyStateProps {
  message: string;
  action: React.ReactNode;
  className?: string;
}

/** Icon-less empty state: one line of explanation and one clear action. */
export function EmptyState({ message, action, className }: EmptyStateProps) {
  return (
    <div
      className={cn(
        "rounded-panel border border-dashed border-line bg-paper px-6 py-10 text-center",
        className,
      )}
    >
      <p className="text-14 text-ink-700">{message}</p>
      <div className="mt-4 flex justify-center">{action}</div>
    </div>
  );
}
