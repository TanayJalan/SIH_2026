import {
  CheckCircle2,
  CircleHelp,
  Sparkles,
  TriangleAlert,
  XCircle,
} from "lucide-react";

import type { DocumentVerificationStatus } from "@/lib/api";
import { cn } from "@/lib/utils";

const STYLES: Record<
  DocumentVerificationStatus,
  { label: string; className: string; Icon: typeof CheckCircle2 }
> = {
  VERIFIED: {
    label: "AI verified",
    className: "border-ok bg-ok-soft text-ok-strong",
    Icon: CheckCircle2,
  },
  FLAGGED: {
    label: "AI flagged",
    className: "border-watch bg-watch-soft text-watch-strong",
    Icon: TriangleAlert,
  },
  REJECTED: {
    label: "AI rejected",
    className: "border-breach bg-breach-soft text-breach-strong",
    Icon: XCircle,
  },
  PENDING: {
    label: "AI check pending",
    className: "border-line bg-paper text-ink-500",
    Icon: CircleHelp,
  },
};

interface DocumentVerificationBadgeProps {
  status: DocumentVerificationStatus | null | undefined;
  reason?: string | null;
  compact?: boolean;
  className?: string;
}

export default function DocumentVerificationBadge({
  status,
  reason,
  compact = false,
  className,
}: DocumentVerificationBadgeProps) {
  if (!status) {
    return null;
  }
  const config = STYLES[status];
  const Icon = config.Icon;
  const showReason =
    !compact && Boolean(reason) && (status === "FLAGGED" || status === "REJECTED");

  return (
    <div className={cn("min-w-0", className)}>
      <span
        className={cn(
          "inline-flex items-center gap-1.5 rounded-pill border px-2 py-0.5 text-11 font-medium",
          config.className,
        )}
      >
        <Sparkles aria-hidden="true" className="size-3" />
        <Icon aria-hidden="true" className="size-3" />
        {config.label}
      </span>
      {showReason ? (
        <p className="mt-1 text-12 leading-5 text-ink-700">{reason}</p>
      ) : null}
    </div>
  );
}
