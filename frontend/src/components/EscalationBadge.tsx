import { Siren } from "lucide-react";

import { StatusPill } from "./ui";

/**
 * Overlay badge shown when an unacknowledged alert has escalated a case.
 * Escalation is stored separately from the workflow status so the case can
 * remain in scrutiny, inspection or review while oversight is notified.
 */
export default function EscalationBadge({ className }: { className?: string }) {
  return (
    <StatusPill status="breach" className={className}>
      <Siren aria-hidden="true" className="size-3" />
      Escalated
    </StatusPill>
  );
}
